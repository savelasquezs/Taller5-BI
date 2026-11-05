from pathlib import Path


def leer_entorno(ruta=None):
    ruta = ruta or Path(__file__).resolve().parents[1] / ".env"
    return {clave.strip(): valor.strip().strip('"').strip("'")
            for linea in Path(ruta).read_text(encoding="utf-8-sig").splitlines()
            if linea.strip() and not linea.lstrip().startswith("#") and "=" in linea
            for clave, valor in [linea.split("=", 1)]}
