SELECT 'Producciones' AS indicador, count(*)::numeric AS valor FROM bi.fact_produccion
UNION ALL SELECT 'Paros', count(*) FROM bi.fact_paros
UNION ALL SELECT 'Pacas', sum(pacas_producidas) FROM bi.fact_produccion
UNION ALL SELECT 'Horas registradas', sum(horas_trabajadas) FROM bi.fact_produccion
UNION ALL SELECT 'Minutos de paro', sum(duracion_minutos) FROM bi.fact_paros
UNION ALL SELECT 'Disponibilidad reconstruida %',
    round(100 * sum(minutos_operativos) FILTER (WHERE disponibilidad_valida)
        / nullif(sum(tiempo_planificado_minutos) FILTER (WHERE disponibilidad_valida), 0), 2)
    FROM bi.fact_produccion
UNION ALL SELECT 'Registros con OEE completo', count(*) FILTER (WHERE oee_valido)
    FROM bi.fact_produccion;

SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('public', 'bi', 'demo')
ORDER BY table_schema, table_name;

SELECT routine_name, routine_type
FROM information_schema.routines
WHERE specific_schema = 'public'
  AND routine_name IN ('registrar_paro', 'validar_duracion_paro', 'auditar_cambios_produccion')
ORDER BY routine_name;

SELECT trigger_name, event_manipulation, event_object_table, action_timing
FROM information_schema.triggers
WHERE trigger_schema = 'public'
ORDER BY trigger_name, event_manipulation;

SELECT m.maquina, count(*) AS registros,
       sum(p.pacas_producidas) AS pacas,
       round(100 * sum(p.minutos_operativos) FILTER (WHERE disponibilidad_valida)
          / nullif(sum(p.tiempo_planificado_minutos) FILTER (WHERE disponibilidad_valida), 0), 2)
          AS disponibilidad_reconstruida
FROM bi.fact_produccion p
JOIN bi.dim_maquina m USING (maquina_id)
GROUP BY m.maquina
ORDER BY m.maquina;
