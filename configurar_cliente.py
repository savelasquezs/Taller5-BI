import json
from pathlib import Path

from helpers.configuracion import leer_entorno


def main():
    import winreg

    config = leer_entorno()
    driver = Path.home() / "Taller5Datos/ODBC/podbc35w.dll"
    if not driver.exists():
        raise SystemExit("Instale PostgreSQL ODBC Unicode x64 antes de crear el DSN.")
    valores = {"Driver": str(driver), "Servername": "127.0.0.1", "Port": config.get("DB_PORT", "55440"),
               "Database": "taller5", "Username": "taller5_bi", "Password": config["BI_PASSWORD"],
               "SSLmode": "disable", "ReadOnly": "1"}
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\ODBC\ODBC.INI\Taller5Docker") as clave:
        for nombre, valor in valores.items():
            winreg.SetValueEx(clave, nombre, 0, winreg.REG_SZ, valor)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\ODBC\ODBC.INI\ODBC Data Sources") as clave:
        winreg.SetValueEx(clave, "Taller5Docker", 0, winreg.REG_SZ, "PostgreSQL Unicode(x64)")
    print(json.dumps({"dsn": "Taller5Docker", "host": "127.0.0.1", "puerto": config.get("DB_PORT", "55440")}))


if __name__ == "__main__":
    main()
