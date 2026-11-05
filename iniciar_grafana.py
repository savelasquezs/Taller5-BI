import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


def main():
    estado = Path.home() / "Taller5Datos"
    try:
        with urllib.request.urlopen("http://127.0.0.1:3001/api/health", timeout=3) as respuesta:
            if json.load(respuesta).get("database") == "ok":
                return 0
    except OSError:
        pass
    configuracion = json.loads((estado / "grafana_conexion.json").read_text(encoding="utf-8"))
    bi = json.loads((estado / "bi_conexion.json").read_text(encoding="utf-8"))
    entorno = os.environ.copy()
    entorno.update(GF_SECURITY_ADMIN_USER=configuracion["user"],
                   GF_SECURITY_ADMIN_PASSWORD=configuracion["password"],
                   GF_SECURITY_SECRET_KEY=configuracion["secret_key"],
                   TALLER5_BI_PASSWORD=bi["password"])
    carpeta = estado / "Grafana"
    (carpeta / "data").mkdir(exist_ok=True)
    (carpeta / "logs").mkdir(exist_ok=True)
    with (carpeta / "consola.log").open("a", encoding="utf-8") as salida:
        subprocess.Popen([r"C:\Program Files\GrafanaLabs\grafana\bin\grafana.exe", "server",
                          "--homepath", r"C:\Program Files\GrafanaLabs\grafana",
                          "--config", str(carpeta / "grafana.ini")], env=entorno,
                         stdout=salida, stderr=salida, creationflags=subprocess.CREATE_NO_WINDOW)
    return 0


if __name__ == "__main__":
    sys.exit(main())
