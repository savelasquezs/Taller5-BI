BEGIN;

CREATE SCHEMA IF NOT EXISTS bi;

CREATE TABLE IF NOT EXISTS estado_etl (
    id BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id),
    inicio TIMESTAMPTZ NOT NULL,
    fin TIMESTAMPTZ NOT NULL,
    estado TEXT NOT NULL,
    errores INTEGER NOT NULL,
    advertencias INTEGER NOT NULL,
    resumen JSONB NOT NULL
);

CREATE OR REPLACE VIEW bi.dim_fecha AS
SELECT to_char(d, 'YYYYMMDD')::INTEGER AS fecha_id,
       d::DATE AS fecha,
       extract(year FROM d)::INTEGER AS anio,
       extract(month FROM d)::INTEGER AS mes_numero,
       to_char(d, 'YYYY-MM') AS periodo,
       (ARRAY['Enero','Febrero','Marzo','Abril','Mayo','Junio',
              'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'])
              [extract(month FROM d)::INTEGER] AS mes,
       extract(isodow FROM d)::INTEGER AS dia_semana
FROM generate_series(
    date_trunc('year', (SELECT min(fecha) FROM registros_produccion)),
    date_trunc('year', greatest(CURRENT_DATE, (SELECT max(fecha) FROM registros_produccion))) + interval '1 year - 1 day',
    interval '1 day'
) AS calendario(d);

CREATE OR REPLACE VIEW bi.dim_maquina AS SELECT id AS maquina_id, nombre AS maquina FROM maquinas;
CREATE OR REPLACE VIEW bi.dim_referencia AS
SELECT id AS referencia_id, nombre AS referencia FROM referencias
UNION ALL SELECT 0, 'Sin referencia';
CREATE OR REPLACE VIEW bi.dim_operador AS
SELECT id AS operador_id, 'Operario ' || lpad(id::TEXT,3,'0') AS operador FROM operadores
UNION ALL SELECT 0, 'Sin identificar';
CREATE OR REPLACE VIEW bi.dim_turno AS
SELECT id AS turno_id, nombre AS turno FROM turnos
UNION ALL SELECT 0, 'Sin informar';
CREATE OR REPLACE VIEW bi.dim_causa AS
SELECT codigo AS codigo_paro, lpad(codigo::TEXT, 2, '0') || ' ' || descripcion AS causa,
       area_responsable AS area,
       CASE WHEN excluye_tiempo_planificado THEN 'Excluido del tiempo planificado'
            WHEN NOT excluye_tiempo_planificado THEN 'Dentro del tiempo planificado'
            ELSE 'Sin clasificar para OEE' END AS clasificacion_oee
FROM codigos_paro;

CREATE OR REPLACE VIEW bi.dim_motivo AS
SELECT c.codigo::TEXT || ':' || coalesce(s.codigo,'') AS motivo_id,
       c.codigo AS codigo_paro, lpad(c.codigo::TEXT,2,'0') || ' ' || c.descripcion AS causa,
       s.codigo AS subcodigo, coalesce(s.descripcion,'Sin subcódigo catalogado') AS subcausa,
       c.area_responsable AS area
FROM codigos_paro c JOIN subcodigos_paro s ON s.codigo_paro=c.codigo
UNION ALL
SELECT c.codigo::TEXT || ':',c.codigo,lpad(c.codigo::TEXT,2,'0') || ' ' || c.descripcion,
       NULL::VARCHAR(30),'Sin subcódigo catalogado',c.area_responsable
FROM codigos_paro c;

CREATE OR REPLACE VIEW bi.fact_produccion AS
WITH paros AS (
    SELECT d.registro_produccion_id,
           count(*)::INTEGER AS cantidad_paros,
           sum(d.duracion_minutos) AS minutos_paro_registrados,
           coalesce(sum(d.duracion_minutos) FILTER (WHERE d.codigo_paro IN (16,17)),0) AS minutos_descanso,
           sum(CASE WHEN c.excluye_tiempo_planificado = FALSE THEN d.duracion_minutos ELSE 0 END) AS minutos_paro_en_plan,
           count(*) FILTER (WHERE c.excluye_tiempo_planificado IS NULL)::INTEGER AS paros_sin_clasificar,
           count(*) FILTER (WHERE d.inicio IS NOT NULL AND d.fin IS NULL)::INTEGER AS paros_abiertos
    FROM detalle_paros_produccion d
    JOIN codigos_paro c ON c.codigo = d.codigo_paro
    GROUP BY d.registro_produccion_id
), base AS (
    SELECT p.id AS registro_id, p.fecha, to_char(p.fecha, 'YYYYMMDD')::INTEGER AS fecha_id,
           p.maquina_id, coalesce(p.referencia_id, 0) AS referencia_id,
           coalesce(p.operador_id, 0) AS operador_id, coalesce(p.turno_id, 0) AS turno_id,
           p.horas_trabajadas, p.pacas_producidas,
           coalesce(p.tiempo_planificado_minutos,
                    p.horas_trabajadas * 60 - coalesce(d.minutos_descanso,0))::NUMERIC(12,2) AS tiempo_planificado_minutos,
           p.unidades_ideales_por_minuto,
           coalesce(p.unidades_producidas,
               CASE WHEN p.unidades_por_display IS NOT NULL AND p.displays_por_paca IS NOT NULL
                     AND p.pacas_producidas * p.unidades_por_display * p.displays_por_paca
                         = trunc(p.pacas_producidas * p.unidades_por_display * p.displays_por_paca)
                     AND p.pacas_producidas * p.unidades_por_display * p.displays_por_paca <= 9223372036854775807
                    THEN (p.pacas_producidas * p.unidades_por_display * p.displays_por_paca)::BIGINT END
           ) AS unidades_producidas, p.unidades_buenas,
           coalesce(d.cantidad_paros, 0) AS cantidad_paros,
           coalesce(d.minutos_paro_registrados, 0) AS minutos_paro_registrados,
           CASE WHEN p.tiempo_planificado_minutos IS NULL
                THEN coalesce(d.minutos_paro_registrados,0) - coalesce(d.minutos_descanso,0)
                ELSE coalesce(d.minutos_paro_en_plan,0) END AS minutos_paro_en_plan,
           coalesce(d.paros_sin_clasificar, 0) AS paros_sin_clasificar,
           coalesce(d.paros_abiertos, 0) AS paros_abiertos,
           coalesce(d.minutos_descanso,0) AS minutos_descanso_registrados,
           CASE WHEN p.tiempo_planificado_minutos IS NULL THEN 'Reconstruido según Excel'
                ELSE 'Registrado' END AS origen_tiempo,
           (position('ETL R08:' IN coalesce(p.observaciones,'')) = 0
            AND p.unidades_ideales_por_minuto IS NOT NULL
            AND (p.unidades_producidas IS NOT NULL OR
                 (p.unidades_por_display IS NOT NULL AND p.displays_por_paca IS NOT NULL))) AS parametros_confirmados,
           (p.unidades_producidas IS NOT NULL) AS unidades_directas
    FROM registros_produccion p
    LEFT JOIN paros d ON d.registro_produccion_id = p.id
), tiempos AS (
    SELECT registro_id,fecha,fecha_id,maquina_id,referencia_id,operador_id,turno_id,
           horas_trabajadas,pacas_producidas,tiempo_planificado_minutos,unidades_ideales_por_minuto,
           unidades_producidas,unidades_buenas,cantidad_paros,minutos_paro_registrados,
           minutos_paro_en_plan,paros_sin_clasificar,paros_abiertos,
           CASE WHEN tiempo_planificado_minutos > 0
                     AND (origen_tiempo = 'Reconstruido según Excel' OR paros_sin_clasificar = 0)
                     AND paros_abiertos = 0 AND minutos_paro_en_plan <= tiempo_planificado_minutos
                THEN tiempo_planificado_minutos - minutos_paro_en_plan END AS minutos_operativos,
           CASE WHEN parametros_confirmados THEN unidades_producidas / nullif(unidades_ideales_por_minuto,0) END AS minutos_ideales,
           CASE WHEN parametros_confirmados THEN unidades_buenas / nullif(unidades_ideales_por_minuto,0) END AS minutos_buenos_ideales,
           minutos_descanso_registrados,origen_tiempo,parametros_confirmados,unidades_directas
    FROM base
), indicadores AS (
    SELECT *, minutos_operativos / nullif(tiempo_planificado_minutos, 0) AS disponibilidad,
           CASE WHEN minutos_ideales <= minutos_operativos AND unidades_producidas >= 0
                THEN minutos_ideales / nullif(minutos_operativos, 0) END AS rendimiento,
           CASE WHEN unidades_directas OR parametros_confirmados
                THEN unidades_buenas::NUMERIC / nullif(unidades_producidas,0) END AS calidad
    FROM tiempos
)
SELECT registro_id,fecha,fecha_id,maquina_id,referencia_id,operador_id,turno_id,
       horas_trabajadas,pacas_producidas,tiempo_planificado_minutos,unidades_ideales_por_minuto,
       unidades_producidas,unidades_buenas,cantidad_paros,minutos_paro_registrados,
       minutos_paro_en_plan,paros_sin_clasificar,paros_abiertos,minutos_operativos,
       minutos_ideales,minutos_buenos_ideales,disponibilidad,rendimiento,calidad,
       disponibilidad * rendimiento * calidad AS oee,
       (disponibilidad IS NOT NULL) AS disponibilidad_valida,
       (rendimiento IS NOT NULL) AS rendimiento_valido,
       (calidad IS NOT NULL) AS calidad_valida,
       (disponibilidad IS NOT NULL AND rendimiento IS NOT NULL AND calidad IS NOT NULL) AS oee_valido,
       nullif(concat_ws('; ',
           CASE WHEN tiempo_planificado_minutos IS NULL OR tiempo_planificado_minutos <= 0 THEN 'Falta tiempo planificado válido' END,
           CASE WHEN unidades_ideales_por_minuto IS NULL THEN 'Falta velocidad ideal' END,
           CASE WHEN unidades_producidas IS NULL THEN 'Faltan unidades producidas' END,
           CASE WHEN unidades_buenas IS NULL THEN 'Faltan unidades buenas' END,
           CASE WHEN paros_sin_clasificar > 0 AND origen_tiempo = 'Registrado' THEN 'Paros sin clasificación OEE' END,
           CASE WHEN unidades_ideales_por_minuto IS NOT NULL AND NOT parametros_confirmados
                THEN 'Parámetros nominales sin vigencia histórica confirmada' END,
           CASE WHEN paros_abiertos > 0 THEN 'Paros abiertos' END,
           CASE WHEN minutos_paro_en_plan > tiempo_planificado_minutos THEN 'Paros mayores al tiempo planificado' END,
           CASE WHEN minutos_ideales > minutos_operativos THEN 'Producción superior a velocidad ideal declarada' END,
           CASE WHEN unidades_producidas = 0 THEN 'Sin unidades para calcular calidad' END,
           CASE WHEN minutos_operativos = 0 THEN 'Sin tiempo operativo para calcular rendimiento' END
       ), '') AS limitaciones,
       minutos_descanso_registrados,origen_tiempo,parametros_confirmados,
       CASE WHEN minutos_operativos > 0
            THEN unidades_producidas / nullif(unidades_ideales_por_minuto,0) / minutos_operativos END AS rendimiento_nominal,
       CASE WHEN horas_trabajadas > 0
            THEN 1-minutos_paro_registrados/(horas_trabajadas*60) END AS productividad_registrada
FROM indicadores;

CREATE OR REPLACE VIEW bi.fact_paros AS
SELECT d.id AS paro_id, p.id AS registro_id, p.fecha,
       to_char(p.fecha, 'YYYYMMDD')::INTEGER AS fecha_id, p.maquina_id,
       coalesce(p.referencia_id, 0) AS referencia_id,
       coalesce(p.operador_id, 0) AS operador_id, coalesce(p.turno_id, 0) AS turno_id,
       d.codigo_paro, d.subcodigo, d.duracion_minutos,
       d.inicio, d.fin, d.observaciones,
       (d.inicio IS NOT NULL AND d.fin IS NOT NULL) AS horario_verificable,
       d.codigo_paro::TEXT || ':' || coalesce(d.subcodigo,'') AS motivo_id
FROM detalle_paros_produccion d
JOIN registros_produccion p ON p.id = d.registro_produccion_id;

CREATE OR REPLACE VIEW bi.estado_lineas AS
SELECT m.id AS maquina_id, m.nombre AS maquina, max(p.fecha) AS ultima_fecha,
       CASE WHEN EXISTS (
           SELECT 1 FROM detalle_paros_produccion d
           JOIN registros_produccion r ON r.id = d.registro_produccion_id
           WHERE r.maquina_id = m.id AND d.fin IS NULL AND d.inicio >= now() - interval '24 hours'
       ) THEN 'Paro abierto reportado'
       WHEN max(p.fecha) = CURRENT_DATE THEN 'Existen registros del día'
       ELSE 'Sin telemetría actual' END AS estado
FROM maquinas m LEFT JOIN registros_produccion p ON p.maquina_id = m.id
GROUP BY m.id, m.nombre;

COMMIT;
