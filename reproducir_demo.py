import json
import os
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg


def main():
    intervalo = max(20, int(os.environ.get("DEMO_INTERVAL_SECONDS", "60")))
    ejecucion = uuid4()
    inicio = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    paso = 0
    while True:
        try:
            with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as db:
                normales = db.execute("""SELECT registro_id FROM bi.fact_produccion
                    WHERE disponibilidad_valida AND minutos_paro_registrados<=60
                    ORDER BY fecha,registro_id LIMIT 1""").fetchone()
                altos = db.execute("""SELECT registro_id FROM bi.fact_produccion
                    WHERE disponibilidad_valida AND minutos_paro_registrados>60
                    ORDER BY fecha,registro_id LIMIT 1""").fetchone()
                if not normales or not altos:
                    time.sleep(5)
                    continue
                registros = [normales[0], altos[0], normales[0]]
                registro = registros[paso % 3]
                paso += 1
                db.execute("""INSERT INTO demo.eventos
                    (ejecucion,paso,registro_id_origen,hora_virtual) VALUES (%s,%s,%s,%s)""",
                           (ejecucion, paso, registro, inicio + timedelta(hours=paso - 1)))
                print(json.dumps({"reproduccion": True, "paso": paso, "registro_original": registro}), flush=True)
            time.sleep(intervalo)
        except psycopg.Error as error:
            print(json.dumps({"error": type(error).__name__, "reintento_segundos": 5}), flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
