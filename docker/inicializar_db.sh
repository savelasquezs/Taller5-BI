#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=etl_password="$ETL_PASSWORD" --set=bi_password="$BI_PASSWORD" <<'SQL'
CREATE ROLE taller5_etl LOGIN PASSWORD :'etl_password';
CREATE ROLE taller5_bi LOGIN PASSWORD :'bi_password';
SQL
for archivo in /sql/01.sql /sql/02.sql /sql/05.sql /sql/07.sql; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$archivo"
done
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
GRANT CONNECT ON DATABASE taller5 TO taller5_etl,taller5_bi;
GRANT USAGE,CREATE ON SCHEMA public TO taller5_etl;
GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO taller5_etl;
GRANT REFERENCES ON registros_produccion TO taller5_etl;
GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO taller5_etl;
GRANT USAGE ON SCHEMA bi,demo TO taller5_etl,taller5_bi;
GRANT SELECT ON ALL TABLES IN SCHEMA bi TO taller5_etl,taller5_bi;
GRANT SELECT ON estado_etl TO taller5_bi;
GRANT SELECT,INSERT ON demo.eventos TO taller5_etl;
GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA demo TO taller5_etl;
GRANT SELECT ON demo.eventos,demo.v_eventos TO taller5_bi;
SQL
