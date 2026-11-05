\set ON_ERROR_STOP on
\pset pager off
BEGIN;

CREATE TEMP TABLE resultados_validacion (prueba TEXT, resultado TEXT);

INSERT INTO registros_produccion (
    fecha, maquina_id, referencia_id, operador_id, turno_id,
    horas_trabajadas, pacas_producidas
) VALUES (
    CURRENT_DATE, (SELECT min(id) FROM maquinas),
    (SELECT min(id) FROM referencias), (SELECT min(id) FROM operadores),
    (SELECT min(id) FROM turnos), 8, 10
) RETURNING id AS registro_prueba \gset

SELECT set_config('taller.registro_prueba', :'registro_prueba', true) AS registro_configurado \gset

DO $$
DECLARE
    registro BIGINT := current_setting('taller.registro_prueba')::BIGINT;
    paro BIGINT;
    historico BIGINT;
BEGIN
    CALL registrar_paro(registro, 1::SMALLINT,
        '2026-10-29 10:00-05', '2026-10-29 10:30-05');
    IF NOT EXISTS (
        SELECT FROM detalle_paros_produccion
        WHERE registro_produccion_id = registro AND duracion_minutos = 30
    ) THEN
        RAISE EXCEPTION 'Fallo en el cálculo de duración';
    END IF;
    INSERT INTO resultados_validacion VALUES ('Duración calculada automáticamente', 'OK');

    BEGIN
        CALL registrar_paro(registro, 1::SMALLINT,
            '2026-10-29 10:15-05', '2026-10-29 10:45-05');
        RAISE EXCEPTION 'Se permitió un solapamiento';
    EXCEPTION WHEN exclusion_violation THEN
        INSERT INTO resultados_validacion VALUES ('Paro solapado rechazado', 'OK');
    END;

    BEGIN
        CALL registrar_paro(registro, 1::SMALLINT,
            '2026-10-29 12:00-05', '2026-10-29 12:30-05', 20);
        RAISE EXCEPTION USING ERRCODE = 'ZX001', MESSAGE = 'Se permitió una duración incorrecta';
    EXCEPTION WHEN raise_exception THEN
        INSERT INTO resultados_validacion VALUES ('Duración contradictoria rechazada', 'OK');
    END;

    BEGIN
        CALL registrar_paro(registro, 2::SMALLINT,
            p_duracion_minutos => 10, p_subcodigo => '1.1');
        RAISE EXCEPTION 'Se permitió un subcódigo de otra causa';
    EXCEPTION WHEN foreign_key_violation THEN
        INSERT INTO resultados_validacion VALUES ('Subcódigo de otra causa rechazado', 'OK');
    END;

    BEGIN
        UPDATE registros_produccion
        SET unidades_producidas = 10, unidades_buenas = 11 WHERE id = registro;
        RAISE EXCEPTION 'Se permitieron unidades buenas mayores al total';
    EXCEPTION WHEN check_violation THEN
        INSERT INTO resultados_validacion VALUES ('Unidades buenas mayores al total rechazadas', 'OK');
    END;

    INSERT INTO detalle_paros_produccion (
        registro_produccion_id, codigo_paro, inicio
    ) VALUES (registro, 1, '2026-10-29 11:00-05') RETURNING id INTO paro;
    UPDATE detalle_paros_produccion SET fin = '2026-10-29 11:15-05' WHERE id = paro;
    IF (SELECT duracion_minutos FROM detalle_paros_produccion WHERE id = paro) <> 15 THEN
        RAISE EXCEPTION 'Fallo al cerrar el paro';
    END IF;
    INSERT INTO resultados_validacion VALUES ('Cierre de paro abierto y cálculo de minutos', 'OK');

    INSERT INTO detalle_paros_produccion (
        registro_produccion_id, codigo_paro, duracion_minutos
    ) VALUES (registro, 1, 20) RETURNING id INTO historico;
    IF NOT EXISTS (SELECT FROM detalle_paros_produccion
        WHERE id = historico AND inicio IS NULL AND duracion_minutos = 20) THEN
        RAISE EXCEPTION 'Fallo en el registro histórico';
    END IF;
    INSERT INTO resultados_validacion VALUES ('Histórico sin horarios aceptado', 'OK');

    DELETE FROM detalle_paros_produccion WHERE id = paro;
    IF NOT EXISTS (SELECT FROM auditoria_cambios WHERE tabla = 'registros_produccion'
        AND registro_id = registro AND operacion = 'INSERT' AND datos_nuevos IS NOT NULL)
       OR (SELECT count(DISTINCT operacion) FROM auditoria_cambios
           WHERE tabla = 'detalle_paros_produccion' AND registro_id = paro) <> 3 THEN
        RAISE EXCEPTION 'Fallo en la auditoría';
    END IF;
    INSERT INTO resultados_validacion VALUES ('Auditoría de creación cambio y eliminación', 'OK');

    IF (SELECT count(*) FROM resultados_validacion) <> 8 THEN
        RAISE EXCEPTION 'Validación incompleta';
    END IF;
END;
$$;

TABLE resultados_validacion;

ROLLBACK;
