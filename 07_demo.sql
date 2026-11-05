BEGIN;
CREATE SCHEMA IF NOT EXISTS demo;
CREATE TABLE IF NOT EXISTS demo.eventos (
    evento_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ejecucion UUID NOT NULL,
    paso INTEGER NOT NULL CHECK (paso > 0),
    registro_id_origen BIGINT NOT NULL REFERENCES registros_produccion(id),
    emitido_en TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    hora_virtual TIMESTAMPTZ NOT NULL,
    UNIQUE (ejecucion,paso)
);
CREATE INDEX IF NOT EXISTS ix_demo_emitido ON demo.eventos(emitido_en);
CREATE OR REPLACE VIEW demo.v_eventos AS
SELECT e.*,p.fecha AS fecha_original,m.maquina,p.pacas_producidas,
       p.horas_trabajadas,p.minutos_paro_registrados,
       p.disponibilidad,p.limitaciones
FROM demo.eventos e
JOIN bi.fact_produccion p ON p.registro_id=e.registro_id_origen
JOIN bi.dim_maquina m USING(maquina_id);
COMMIT;
