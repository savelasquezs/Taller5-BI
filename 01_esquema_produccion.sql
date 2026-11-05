BEGIN;

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE maquinas (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE referencias (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE turnos (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    hora_inicio TIME,
    hora_fin TIME,
    CHECK ((hora_inicio IS NULL) = (hora_fin IS NULL))
);

CREATE TABLE operadores (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE codigos_paro (
    codigo SMALLINT PRIMARY KEY CHECK (codigo > 0),
    descripcion TEXT NOT NULL,
    area_responsable VARCHAR(100),
    excluye_tiempo_planificado BOOLEAN
);

CREATE TABLE subcodigos_paro (
    codigo_paro SMALLINT NOT NULL REFERENCES codigos_paro (codigo),
    codigo VARCHAR(30) NOT NULL,
    descripcion TEXT NOT NULL,
    PRIMARY KEY (codigo_paro, codigo)
);

CREATE TABLE registros_produccion (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha DATE NOT NULL,
    maquina_id INTEGER NOT NULL REFERENCES maquinas (id),
    referencia_id INTEGER REFERENCES referencias (id),
    operador_id INTEGER REFERENCES operadores (id),
    turno_id INTEGER REFERENCES turnos (id),
    horas_trabajadas NUMERIC(8, 2) NOT NULL CHECK (horas_trabajadas >= 0),
    horas_no_trabajadas NUMERIC(8, 2) CHECK (horas_no_trabajadas >= 0),
    pacas_producidas NUMERIC(12, 3) NOT NULL CHECK (pacas_producidas >= 0),
    unidades_por_display INTEGER CHECK (unidades_por_display > 0),
    displays_por_paca INTEGER CHECK (displays_por_paca > 0),
    unidades_ideales_por_minuto NUMERIC(12, 4) CHECK (unidades_ideales_por_minuto > 0),
    tiempo_planificado_minutos NUMERIC(12, 2) CHECK (tiempo_planificado_minutos >= 0),
    unidades_producidas BIGINT CHECK (unidades_producidas >= 0),
    unidades_buenas BIGINT CHECK (unidades_buenas >= 0),
    tipo_paro_reportado TEXT,
    observaciones_paro TEXT,
    observaciones TEXT,
    CHECK (unidades_buenas IS NULL OR (
        unidades_producidas IS NOT NULL AND unidades_buenas <= unidades_producidas
    ))
);

CREATE TABLE detalle_paros_produccion (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    registro_produccion_id BIGINT NOT NULL REFERENCES registros_produccion (id),
    codigo_paro SMALLINT NOT NULL REFERENCES codigos_paro (codigo),
    subcodigo VARCHAR(30),
    inicio TIMESTAMPTZ,
    fin TIMESTAMPTZ,
    duracion_minutos NUMERIC(12, 2) CHECK (duracion_minutos > 0),
    area_involucrada VARCHAR(150),
    personal_involucrado TEXT,
    observaciones TEXT,
    CHECK (fin IS NULL OR (inicio IS NOT NULL AND fin > inicio)),
    CHECK (
        (inicio IS NULL AND fin IS NULL AND duracion_minutos IS NOT NULL)
        OR (inicio IS NOT NULL AND fin IS NULL AND duracion_minutos IS NULL)
        OR (inicio IS NOT NULL AND fin IS NOT NULL AND duracion_minutos IS NOT NULL)
    ),
    FOREIGN KEY (codigo_paro, subcodigo)
        REFERENCES subcodigos_paro (codigo_paro, codigo),
    EXCLUDE USING gist (
        registro_produccion_id WITH =,
        tstzrange(inicio, fin, '[)') WITH &&
    ) WHERE (inicio IS NOT NULL)
);

CREATE TABLE auditoria_cambios (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tabla TEXT NOT NULL,
    registro_id BIGINT NOT NULL,
    operacion VARCHAR(6) NOT NULL CHECK (operacion IN ('INSERT', 'UPDATE', 'DELETE')),
    fecha TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    usuario TEXT NOT NULL DEFAULT session_user,
    datos_anteriores JSONB,
    datos_nuevos JSONB
);

CREATE FUNCTION validar_duracion_paro() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE
    minutos NUMERIC(12, 2);
BEGIN
    IF TG_OP = 'UPDATE'
       AND (NEW.inicio IS DISTINCT FROM OLD.inicio OR NEW.fin IS DISTINCT FROM OLD.fin)
       AND NEW.duracion_minutos IS NOT DISTINCT FROM OLD.duracion_minutos THEN
        NEW.duracion_minutos := NULL;
    END IF;

    IF NEW.inicio IS NOT NULL AND NEW.fin IS NOT NULL THEN
        minutos := round(EXTRACT(EPOCH FROM (NEW.fin - NEW.inicio)) / 60, 2);
        IF NEW.duracion_minutos IS NOT NULL
           AND NEW.duracion_minutos <> minutos THEN
            RAISE EXCEPTION 'La duración no coincide con el inicio y fin del paro';
        END IF;
        NEW.duracion_minutos := minutos;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validar_duracion_paro
BEFORE INSERT OR UPDATE ON detalle_paros_produccion
FOR EACH ROW EXECUTE FUNCTION validar_duracion_paro();

CREATE FUNCTION auditar_cambios_produccion() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND NEW IS NOT DISTINCT FROM OLD THEN
        RETURN NULL;
    END IF;

    INSERT INTO auditoria_cambios (
        tabla, registro_id, operacion, datos_anteriores, datos_nuevos
    ) VALUES (
        TG_TABLE_NAME,
        CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END,
        TG_OP,
        CASE WHEN TG_OP <> 'INSERT' THEN to_jsonb(OLD) END,
        CASE WHEN TG_OP <> 'DELETE' THEN to_jsonb(NEW) END
    );
    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_auditar_registros_produccion
AFTER INSERT OR UPDATE OR DELETE ON registros_produccion
FOR EACH ROW EXECUTE FUNCTION auditar_cambios_produccion();

CREATE TRIGGER trg_auditar_detalle_paros
AFTER INSERT OR UPDATE OR DELETE ON detalle_paros_produccion
FOR EACH ROW EXECUTE FUNCTION auditar_cambios_produccion();

CREATE PROCEDURE registrar_paro (
    p_registro_produccion_id BIGINT,
    p_codigo_paro SMALLINT,
    p_inicio TIMESTAMPTZ DEFAULT NULL,
    p_fin TIMESTAMPTZ DEFAULT NULL,
    p_duracion_minutos NUMERIC DEFAULT NULL,
    p_subcodigo VARCHAR DEFAULT NULL,
    p_observaciones TEXT DEFAULT NULL
)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO detalle_paros_produccion (
        registro_produccion_id, codigo_paro, inicio, fin,
        duracion_minutos, subcodigo, observaciones
    ) VALUES (
        p_registro_produccion_id, p_codigo_paro, p_inicio, p_fin,
        p_duracion_minutos, p_subcodigo, p_observaciones
    );
END;
$$;

CREATE INDEX idx_registros_produccion_fecha ON registros_produccion (fecha);
CREATE INDEX idx_registros_produccion_maquina_fecha ON registros_produccion (maquina_id, fecha);
CREATE INDEX idx_registros_produccion_referencia ON registros_produccion (referencia_id);
CREATE INDEX idx_registros_produccion_operador ON registros_produccion (operador_id);
CREATE INDEX idx_registros_produccion_turno ON registros_produccion (turno_id);
CREATE INDEX idx_detalle_paros_registro ON detalle_paros_produccion (registro_produccion_id);
CREATE INDEX idx_detalle_paros_codigo_subcodigo ON detalle_paros_produccion (codigo_paro, subcodigo);

COMMIT;
