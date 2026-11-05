-- 1. Producción mensual: pacas originales y unidades solo como referencia nominal.
SELECT to_char(fecha,'YYYY-MM') AS periodo,m.maquina,count(*) AS registros,
       sum(pacas_producidas) AS pacas,sum(horas_trabajadas) AS horas,
       sum(unidades_producidas) AS unidades_nominales,
       count(unidades_producidas) AS registros_con_conversion
FROM bi.fact_produccion p JOIN bi.dim_maquina m USING(maquina_id)
GROUP BY 1,2 ORDER BY 1,2;

-- 2. Pareto de causas, calculado sobre minutos y no sobre número de eventos.
WITH causas AS (
    SELECT c.causa,sum(p.duracion_minutos) AS minutos
    FROM bi.fact_paros p JOIN bi.dim_causa c USING(codigo_paro) GROUP BY 1
)
SELECT causa,minutos,round(100*minutos/sum(minutos) OVER(),2) AS porcentaje,
       round(100*sum(minutos) OVER(ORDER BY minutos DESC,causa ROWS UNBOUNDED PRECEDING)
                 /sum(minutos) OVER(),2) AS acumulado
FROM causas ORDER BY minutos DESC,causa;

-- 3. Comparativo interanual; un año ausente no equivale a producción cero.
WITH anual AS (
    SELECT extract(year FROM fecha)::INTEGER AS anio,maquina_id,sum(pacas_producidas) AS pacas
    FROM bi.fact_produccion GROUP BY 1,2
)
SELECT a.anio,m.maquina,a.pacas,b.pacas AS pacas_anio_anterior,
       round(100*(a.pacas-b.pacas)/nullif(b.pacas,0),2) AS variacion_porcentaje
FROM anual a JOIN bi.dim_maquina m USING(maquina_id)
LEFT JOIN anual b ON b.maquina_id=a.maquina_id AND b.anio=a.anio-1 ORDER BY 1,2;

-- 4. Disponibilidad ponderada y su cobertura por máquina.
SELECT m.maquina,count(*) AS registros,count(*) FILTER(WHERE disponibilidad_valida) AS validos,
       round(100*count(*) FILTER(WHERE disponibilidad_valida)/count(*)::NUMERIC,2) AS cobertura,
       round(100*sum(minutos_operativos) FILTER(WHERE disponibilidad_valida)
          /nullif(sum(tiempo_planificado_minutos) FILTER(WHERE disponibilidad_valida),0),2) AS disponibilidad
FROM bi.fact_produccion p JOIN bi.dim_maquina m USING(maquina_id) GROUP BY 1 ORDER BY 1;

-- 5. Código y subcódigo: conserva los paros sin detalle catalogado.
SELECT m.causa,m.subcausa,count(*) AS paros,sum(p.duracion_minutos) AS minutos
FROM bi.fact_paros p JOIN bi.dim_motivo m USING(motivo_id)
GROUP BY 1,2 ORDER BY minutos DESC;

-- 6. Evolución mensual; LAG identifica el período observado anterior.
WITH mensual AS (
    SELECT date_trunc('month',fecha)::DATE AS mes,maquina_id,sum(pacas_producidas) AS pacas
    FROM bi.fact_produccion GROUP BY 1,2
)
SELECT m.*,lag(mes) OVER w AS mes_observado_anterior,lag(pacas) OVER w AS pacas_periodo_anterior
FROM mensual m WINDOW w AS (PARTITION BY maquina_id ORDER BY mes) ORDER BY mes,maquina_id;

-- 7. Incidencias de parámetros por período, sin recortar rendimientos superiores al 100 %.
SELECT to_char(fecha,'YYYY-MM') AS periodo,m.maquina,count(*) AS registros,
       count(*) FILTER(WHERE rendimiento_nominal IS NOT NULL) AS nominales_evaluables,
       count(*) FILTER(WHERE rendimiento_nominal>1) AS nominales_superiores_100,
       count(*) FILTER(WHERE parametros_confirmados) AS vigencia_confirmada,
       count(*) FILTER(WHERE oee_valido) AS oee_calculable
FROM bi.fact_produccion p JOIN bi.dim_maquina m USING(maquina_id) GROUP BY 1,2 ORDER BY 1,2;


-- 8. Minutos de cada código sobre horas registradas; distinto del Pareto.
WITH horas AS (
    SELECT sum(horas_trabajadas)*60 AS minutos_base FROM bi.fact_produccion
), causas AS (
    SELECT c.codigo_paro,c.causa,sum(p.duracion_minutos) AS minutos_paro
    FROM bi.fact_paros p JOIN bi.dim_causa c USING(codigo_paro)
    GROUP BY c.codigo_paro,c.causa
)
SELECT c.codigo_paro,c.causa,c.minutos_paro,h.minutos_base,
       round(100*c.minutos_paro/nullif(h.minutos_base,0),2) AS porcentaje_sobre_horas
FROM causas c CROSS JOIN horas h ORDER BY porcentaje_sobre_horas DESC,c.codigo_paro;
