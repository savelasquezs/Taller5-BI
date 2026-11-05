import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


RAIZ = Path(__file__).resolve().parent
CONFIGURACION = Path.home() / "Taller5Datos" / "conexion.json"
SIN_VENTANA = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def main():
    logs = Path(os.environ.get("LOG_DIR", RAIZ / "logs"))
    logs.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("taller5.etl")
    logger.setLevel(logging.INFO)
    manejador = RotatingFileHandler(logs / "ejecuciones_etl.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(manejador)
    estado = {"inicio": datetime.now().astimezone().isoformat(timespec="seconds")}
    config = None
    codigo = 2
    try:
        if os.environ.get("DATABASE_URL"):
            config = {"database_url": os.environ["DATABASE_URL"]}
        else:
            config = json.loads(CONFIGURACION.read_text(encoding="utf-8-sig"))
            pg_ctl = str(Path(config["pg_bin"]) / "pg_ctl.exe")
            datos = config["pg_data"]
            resultado = subprocess.run([pg_ctl, "-D", datos, "status"], capture_output=True, creationflags=SIN_VENTANA)
            if resultado.returncode:
                with (Path(datos).parent / "pg_ctl.log").open("a", encoding="utf-8") as salida:
                    arranque = subprocess.run([pg_ctl, "-D", datos, "-l", str(Path(datos).parent / "postgresql.log"), "-w", "start"],
                                             stdout=salida, stderr=salida, creationflags=SIN_VENTANA, timeout=90)
                if arranque.returncode:
                    raise RuntimeError("No se pudo iniciar PostgreSQL; revise postgresql.log en la carpeta de datos")
        entorno = os.environ.copy()
        entorno["DATABASE_URL"] = config["database_url"]
        if config.get("pgpass_file"):
            entorno["PGPASSFILE"] = config["pgpass_file"]
        entorno["PYTHONIOENCODING"] = "utf-8"
        python = Path(sys.executable).with_name("python.exe") if os.name == "nt" else Path(sys.executable)
        ruta_excel = Path(os.environ.get("EXCEL_PATH", RAIZ / "SEGUIMIENTO TEMPERAS Y VINILOS Actividad.xlsm"))
        if "EXCEL_PATH" in os.environ:
            import psycopg
            from helpers.catalogos import cargar_operadores

            with psycopg.connect(config["database_url"]) as conexion:
                cargar_operadores(conexion, ruta_excel)
        carga = subprocess.run([str(python), str(RAIZ / "cargar_excel.py"),
                                "--excel", str(ruta_excel), "--errores", str(logs / "carga_errores.csv")], cwd=RAIZ, env=entorno,
                               capture_output=True, encoding="utf-8", errors="replace", creationflags=SIN_VENTANA, timeout=240)
        if carga.stderr:
            logger.warning(carga.stderr.strip())
        if carga.returncode not in (0, 1):
            raise RuntimeError("La carga falló; revise ejecuciones_etl.log y carga_errores.csv")
        resumen = json.loads(carga.stdout.strip().splitlines()[-1])
        estado.update(estado="completada_con_incidencias" if resumen["errores"] else "completada", resumen=resumen)
        logger.info(json.dumps(resumen, ensure_ascii=False))
        codigo = 0
    except Exception as error:
        estado.update(estado="fallida", error=str(error))
        logger.exception("Fallo de ejecución")
    finally:
        estado["fin"] = datetime.now().astimezone().isoformat(timespec="seconds")
        if config:
            try:
                import psycopg
                from psycopg.types.json import Jsonb

                if config.get("pgpass_file"):
                    os.environ["PGPASSFILE"] = config["pgpass_file"]
                resumen = estado.get("resumen", {})
                with psycopg.connect(config["database_url"], autocommit=True, connect_timeout=10) as conexion:
                    conexion.execute("""
                        INSERT INTO estado_etl (id,inicio,fin,estado,errores,advertencias,resumen)
                        VALUES (TRUE,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (id) DO UPDATE SET inicio=EXCLUDED.inicio,fin=EXCLUDED.fin,
                            estado=EXCLUDED.estado,errores=EXCLUDED.errores,
                            advertencias=EXCLUDED.advertencias,resumen=EXCLUDED.resumen
                    """, (datetime.fromisoformat(estado["inicio"]), datetime.fromisoformat(estado["fin"]),
                          estado["estado"], resumen.get("errores", 0), resumen.get("advertencias", 0),
                          Jsonb(resumen or {"error": estado.get("error")})))
            except Exception:
                logger.exception("No se pudo publicar el estado del ETL en PostgreSQL")
                estado["error_estado_db"] = "No se pudo publicar la salud del ETL"
                codigo = 2
        temporal = logs / "ultima_ejecucion.json.tmp"
        temporal.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporal.replace(logs / "ultima_ejecucion.json")
        manejador.close()
        logger.removeHandler(manejador)
    return codigo


if __name__ == "__main__":
    if "--continuo" in sys.argv:
        while True:
            main()
            time.sleep(max(10, int(os.environ.get("ETL_INTERVAL_SECONDS", "300"))))
    else:
        sys.exit(main())
