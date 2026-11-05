import base64
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.conninfo import make_conninfo

from helpers.configuracion import leer_entorno


def verificar():
    config = leer_entorno()
    dsn = make_conninfo(host="127.0.0.1", port=config.get("DB_PORT", "55440"), dbname="taller5",
                        user="taller5_bi", password=config["BI_PASSWORD"])
    with psycopg.connect(dsn) as db:
        totales = db.execute("""SELECT count(*),sum(pacas_producidas),sum(horas_trabajadas),
            sum(minutos_paro_registrados),count(*) FILTER(WHERE disponibilidad_valida),
            count(*) FILTER(WHERE rendimiento_nominal>1),count(*) FILTER(WHERE oee_valido)
            FROM bi.fact_produccion""").fetchone()
        esperado = (4809, 378727, 38047.35, 502924.10, 4752, 626, 0)
        assert all(abs(float(a) - b) < 0.000001 for a, b in zip(totales, esperado)), totales
        assert db.execute("SELECT count(*) FROM bi.fact_paros").fetchone()[0] == 16452
        assert db.execute("""SELECT count(*) FROM bi.fact_paros p LEFT JOIN bi.dim_motivo m
            USING(motivo_id) WHERE m.motivo_id IS NULL""").fetchone()[0] == 0
        assert db.execute("SELECT count(*),count(DISTINCT motivo_id) FROM bi.dim_motivo").fetchone() == (65, 65)
        assert db.execute("SELECT count(*) FROM bi.dim_operador WHERE operador NOT LIKE 'Operario %%' AND operador_id<>0").fetchone()[0] == 0
        prueba = False
        try:
            db.execute("UPDATE estado_etl SET errores=errores WHERE FALSE")
        except psycopg.errors.InsufficientPrivilege:
            db.rollback()
            prueba = True
        assert prueba, "El usuario BI puede escribir"
    auth = base64.b64encode(("admin:" + config["GRAFANA_PASSWORD"]).encode()).decode()
    headers = {"Authorization": "Basic " + auth, "Content-Type": "application/json"}
    base = "http://127.0.0.1:" + config.get("GRAFANA_PORT", "3002")

    def api(path, data=None):
        request = urllib.request.Request(base + path, headers=headers,
                                         data=json.dumps(data).encode() if data is not None else None)
        return json.load(urllib.request.urlopen(request, timeout=60))

    consultas = 0
    for archivo in Path("grafana").glob("tablero_*.json"):
        tablero = json.loads(archivo.read_text(encoding="utf-8"))
        cargado = api("/api/dashboards/uid/" + tablero["uid"])
        assert cargado["meta"]["provisioned"], archivo
        for panel in tablero["panels"]:
            for target in panel.get("targets", []):
                query = dict(target, intervalMs=60000, maxDataPoints=1500)
                query["rawSql"] = query["rawSql"].replace("${maquina:csv}", "1,2,3,4")
                if tablero["uid"] == "taller5-demo":
                    desde, hasta = str(int((time.time() - 900) * 1000)), str(int(time.time() * 1000))
                else:
                    desde, hasta = "1640995200000", "1743224400000"
                result = api("/api/ds/query", {"from": desde, "to": hasta, "queries": [query]})
                assert not result["results"]["A"].get("error"), (panel["title"], result)
                consultas += 1
    reglas = api("/api/prometheus/grafana/api/v1/rules")
    alertas = [{"nombre": r["name"], "estado": r.get("state"), "salud": r.get("health")}
               for grupo in reglas["data"]["groups"] for r in grupo["rules"]]
    assert len(alertas) == 3 and all(r["salud"] == "ok" for r in alertas), alertas
    resultado = {"fecha": datetime.now().astimezone().isoformat(), "producciones": 4809, "paros": 16452,
                 "disponibilidad_validos": 4752, "nominal_superior_100": 626, "motivos": 65,
                 "consultas_grafana": consultas, "alertas": alertas, "usuario_bi_solo_lectura": True}
    carpeta = Path("logs/docker")
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "verificacion.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False))


if __name__ == "__main__":
    verificar()
