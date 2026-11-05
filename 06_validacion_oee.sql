\set ON_ERROR_STOP on
BEGIN;

INSERT INTO maquinas (nombre) VALUES ('PRUEBA OEE NO PRODUCTIVA') RETURNING id AS maquina_prueba \gset
INSERT INTO registros_produccion (fecha, maquina_id, horas_trabajadas, pacas_producidas,
    tiempo_planificado_minutos, unidades_ideales_por_minuto, unidades_producidas, unidades_buenas)
VALUES (CURRENT_DATE, :maquina_prueba, 8, 1, 480, 2, 600, 570)
RETURNING id AS registro_prueba \gset

SELECT set_config('taller.prueba_oee', :'registro_prueba', true) AS contexto \gset
UPDATE codigos_paro SET excluye_tiempo_planificado = FALSE WHERE codigo = 1;
INSERT INTO detalle_paros_produccion (registro_produccion_id,codigo_paro,duracion_minutos)
VALUES (:registro_prueba,1,60);

DO $$
DECLARE r RECORD;
BEGIN
    SELECT * INTO r FROM bi.fact_produccion WHERE registro_id=current_setting('taller.prueba_oee')::BIGINT;
    IF NOT r.oee_valido OR abs(r.disponibilidad-0.875) > 0.000001
       OR abs(r.rendimiento-0.7142857142857143) > 0.000001
       OR abs(r.calidad-0.95) > 0.000001 OR abs(r.oee-0.59375) > 0.000001 THEN
        RAISE EXCEPTION 'Falló el cálculo de OEE';
    END IF;
END $$;

SELECT 'Caso sintético aislado' AS prueba, round(disponibilidad*100,3) AS disponibilidad,
       round(rendimiento*100,3) AS rendimiento, round(calidad*100,3) AS calidad,
       round(oee*100,3) AS oee FROM bi.fact_produccion WHERE registro_id=:registro_prueba;

UPDATE registros_produccion SET unidades_buenas=NULL WHERE id=:registro_prueba;
DO $$ BEGIN
    IF EXISTS (SELECT FROM bi.fact_produccion WHERE registro_id=current_setting('taller.prueba_oee')::BIGINT AND oee IS NOT NULL)
    THEN RAISE EXCEPTION 'Un dato faltante produjo OEE'; END IF;
END $$;

UPDATE registros_produccion SET unidades_producidas=NULL, unidades_por_display=6, displays_por_paca=100
WHERE id=:registro_prueba;
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM bi.fact_produccion
        WHERE registro_id=current_setting('taller.prueba_oee')::BIGINT
          AND unidades_producidas=600 AND unidades_buenas IS NULL AND oee IS NULL)
    THEN RAISE EXCEPTION 'Conversión de pacas incorrecta o calidad inventada'; END IF;
END $$;

UPDATE registros_produccion SET unidades_producidas=600, unidades_buenas=570, tiempo_planificado_minutos=0 WHERE id=:registro_prueba;
DO $$ BEGIN
    IF EXISTS (SELECT FROM bi.fact_produccion WHERE registro_id=current_setting('taller.prueba_oee')::BIGINT AND disponibilidad IS NOT NULL)
    THEN RAISE EXCEPTION 'Tiempo cero produjo disponibilidad'; END IF;
END $$;

UPDATE registros_produccion SET tiempo_planificado_minutos=480, unidades_ideales_por_minuto=0.1 WHERE id=:registro_prueba;
DO $$ BEGIN
    IF EXISTS (SELECT FROM bi.fact_produccion WHERE registro_id=current_setting('taller.prueba_oee')::BIGINT AND rendimiento IS NOT NULL)
    THEN RAISE EXCEPTION 'Rendimiento imposible fue aceptado'; END IF;
END $$;

UPDATE registros_produccion SET tiempo_planificado_minutos=NULL, unidades_ideales_por_minuto=2,
    observaciones='ETL R08: parámetro nominal sin vigencia' WHERE id=:registro_prueba;
INSERT INTO detalle_paros_produccion (registro_produccion_id,codigo_paro,duracion_minutos)
VALUES (:registro_prueba,16,40),(:registro_prueba,17,3);
DO $$
DECLARE r RECORD;
BEGIN
    SELECT * INTO r FROM bi.fact_produccion WHERE registro_id=current_setting('taller.prueba_oee')::BIGINT;
    IF r.tiempo_planificado_minutos<>437 OR r.minutos_operativos<>377
       OR abs(r.disponibilidad-377.0/437)>0.000001 OR r.rendimiento IS NOT NULL
       OR r.oee IS NOT NULL OR r.parametros_confirmados
       OR abs(r.rendimiento_nominal-300.0/377)>0.000001 THEN
        RAISE EXCEPTION 'Reconstrucción temporal o separación del nominal incorrecta';
    END IF;
END $$;

UPDATE registros_produccion SET unidades_ideales_por_minuto=0.1 WHERE id=:registro_prueba;
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM bi.fact_produccion WHERE registro_id=current_setting('taller.prueba_oee')::BIGINT
                   AND rendimiento_nominal>1 AND rendimiento IS NULL AND oee IS NULL) THEN
        RAISE EXCEPTION 'El diagnóstico nominal ocultó un valor superior al 100 por ciento';
    END IF;
END $$;

UPDATE registros_produccion SET horas_trabajadas=1 WHERE id=:registro_prueba;
DO $$ BEGIN
    IF EXISTS (SELECT FROM bi.fact_produccion WHERE registro_id=current_setting('taller.prueba_oee')::BIGINT
               AND (disponibilidad IS NOT NULL OR rendimiento_nominal IS NOT NULL)) THEN
        RAISE EXCEPTION 'Paros superiores a horas produjeron indicadores válidos';
    END IF;
END $$;

ROLLBACK;
