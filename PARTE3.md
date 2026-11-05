# Parte 3: visualización y OEE

## Modelo y conexión

`05_modelo_analitico.sql` publica seis dimensiones y dos hechos: una fila por producción y una por paro. Power BI usa once relaciones de muchos a uno, sin unir los hechos directamente. El proyecto vigente usa la conexión ODBC `Taller5Docker`, PostgreSQL en 55440 y usuario de lectura. `powerbi/Taller5.pbip` permite editar el proyecto; **`powerbi/Taller5_Docker.pbix`** es la entrega privada actual, guardada y verificada también en su modelo binario. `Taller5.pbix` es el antecedente de la instalación anterior. La definición vigente de medidas y relaciones está en `powerbi/Taller5.SemanticModel/model.bim`.

Hay cuatro páginas: producción, Pareto, OEE/calidad y parámetros por período. Los filtros de máquina, año y referencia se aplican a las métricas. La nueva tabla mensual muestra únicamente períodos con registros. **Actualizar** consulta PostgreSQL; no se configuró Power BI Service.

## Decisiones aplicadas

| Decisión | Tratamiento |
| --- | --- |
| Reconstruir tiempos | Seguir `Calculadora de tiempos!G12`: plan = horas × 60 − descansos 16/17. Operación = horas × 60 − todos los paros; no restar descansos dos veces. Un plan explícito prevalece. La vista indica el origen del tiempo y no rellena la tabla original. |
| Validar disponibilidad | Usar solo plan positivo, operación no negativa y sin paros abiertos. Es disponibilidad reconstruida según el registro; faltan horarios para verificar omisiones o solapamientos históricos. Se agregan sumas de operación y plan del mismo conjunto válido. |
| Conservar productividad original | `(horas × 60 − paros) / (horas × 60)`, razón de sumas sobre todos los registros. Describe tiempo sin paros registrados e incluye inconsistencias; tiene un denominador distinto de disponibilidad y no se llama OEE. |
| Revisar parámetros por período | Se revisaron 142 combinaciones de mes/máquina. La copia antigua se enlaza por fila histórica inequívoca, no se asigna a años completos ni se carga como producción adicional. Los 643 contrastes con catálogo discrepan y no informan vigencia. Detalle: `logs/revision_parametros_periodo.csv`. |
| Separar nominal de confirmado | R08 conserva empaque/velocidad y conversiones con procedencia. Se usan solo en diagnóstico nominal mientras no exista respaldo de vigencia. Los valores >100 % permanecen visibles y no se recortan ni se ocultan seleccionando solo resultados favorables. |
| Conservar calidad desconocida | Los paros por calidad son minutos, no unidades rechazadas. No se supone calidad del 100 %. Los totales derivados de empaque no confirmado tampoco validan por sí solos calidad por unidades. |
| Agregar OEE correctamente | Cada componente tiene su cobertura. OEE utiliza exclusivamente registros completos con parámetros confirmados: minutos buenos ideales / plan. No se multiplican tarjetas con poblaciones distintas. |

## Resultados actuales

- 4.809 producciones, 16.452 paros, 378.727 pacas, 38.047,35 horas y 502.924,10 minutos de paro: totales conservados.
- Disponibilidad reconstruida: **84,13 %**, con 4.752 registros y **98,8 %** de cobertura.
- Tiempo sin paros / horas, fórmula original: **77,97 %**. No equivale a OEE.
- 2.448 registros con parámetros nominales; 2.423 con tiempo operativo para diagnóstico; 626 superan el 100 %. No hay parámetros históricos confirmados ni rendimiento OEE validado en esta fuente.
- No hay unidades buenas/rechazadas documentadas: calidad y OEE completo continúan sin calcularse. Las 2.256 referencias ausentes se conservan sin inventar productos.
- SQL validado con transacciones revertidas: cálculo completo de prueba, datos ausentes, plan cero, tiempo imposible, conversión de empaques y separación del diagnóstico nominal. Los casos de prueba no permanecen en producción.
- PostgreSQL y el motor DAX coinciden; se verifican filtros, Pareto, 142 filas mensuales con datos y once relaciones sin huérfanos. Evidencias: `logs/ajuste_modelo_periodos.json`, `logs/verificacion_powerbi.json`, `logs/verificacion_analitica.json` y `logs/validacion_oee.log`.

## Grafana y automatización

Grafana de Docker `http://127.0.0.1:3002` conserva supervisión del ETL y análisis histórico; la instalación anterior en 3001 queda como antecedente. El histórico muestra disponibilidad reconstruida, productividad original, anomalías nominales y revisión por mes. Las 24 consultas históricas y operativas, más cinco de reproducción, se verificaron con el usuario de lectura en Docker. Las métricas del día siguen vacías porque no hay telemetría actual: la última fecha de planta es 2025-03-28.

Los tableros históricos/operativos refrescan cada 30 segundos; la reproducción, cada cinco. El ETL carga cada cinco minutos mientras Docker está activo. Las alertas de ETL atrasado y paro abierto, más la alerta DEMO, se aprovisionan al arrancar y no envían mensajes externos. Claves en `.env` privado.

## Alcance frente al taller

Partes 1 y 2 implementadas: esquema, catálogos, integridad, auditoría y carga incremental. Parte 3 implementa modelo estrella, DAX, tendencias, Pareto y componentes respaldados por el registro. La demostración de OEE real completo permanece limitada por calidad y vigencia histórica de parámetros; la actualización de pantallas no sustituye una HMI actual.

Antecedentes y contraste de fuentes: `INVESTIGACION_OEE.md`. Reglas resumidas: `DECISIONES_ETL.md`. Capturas y descripciones breves: `EVIDENCIAS.md`.

Referencias: [cálculo de OEE](https://www.oee.com/calculating-oee/), [proyectos Power BI](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview), [ODBC](https://learn.microsoft.com/en-us/power-query/connectors/odbc), [Grafana](https://grafana.com/docs/grafana/latest/administration/provisioning/).

## Jerarquía, tiempo y reproducción en Docker

`bi.dim_motivo` aplana código/subcódigo en 65 claves únicas y `FactParos.motivo_id` evita multiplicar minutos en las uniones. Sustituye a DimCausa en Power BI; `bi.dim_causa` se conserva para compatibilidad de Grafana. La dimensión fecha es un calendario continuo, con clave única y jerarquía temporal. El proyecto incorpora comparación anual con `SAMEPERIODLASTYEAR` y variación porcentual: requiere un año seleccionado y muestra ausencia de comparativo cuando corresponde. La versión Docker ya se verificó en el motor nativo de Power BI: ocho tablas, 36 medidas y once relaciones; coinciden 4.809 producciones y 16.452 paros. Se comprobaron filtro por máquina, acumulados por subcódigo y comparación anual. Evidencia: `logs/docker/verificacion_powerbi.json`.

El perfil `demo` reproduce registros reales con sus IDs y fecha original en secuencia normal → paro mayor de 60 minutos → normal. Hora virtual y hora de emisión están identificadas. Es una demostración del flujo y del mecanismo de alerta, sin modificar producción ni atribuir a una hora real las cantidades de un registro histórico. La regla DEMO se evalúa cada diez segundos, espera diez segundos y exige una emisión de los últimos tres minutos; el umbral es didáctico, no una meta industrial aprobada.


El histórico de Grafana incluye el porcentaje de cada código sobre las horas registradas: `100 × minutos del código / (horas × 60)`. El denominador se suma desde producción por separado, con los mismos filtros, para no repetir horas al unir incidencias. Es distinto del Pareto y del OEE. La consulta 8 reproduce ese cálculo. La tabla DEMO muestra la fecha original como texto para evitar cambios por huso horario y conserva IDs/pacas como enteros completos.

El comparativo anual de 2025 está marcado como parcial: los registros terminan el 28 de marzo de 2025 y la medida compara contra 2024 completo. No representa una comparación entre períodos de igual duración.

La alerta DEMO se observó activa a las 23:15:47 y recuperada a las 23:16:37 del 4 de noviembre de 2026 (Colombia). `logs/docker/alerta_demo.json` conserva las muestras de la API; las capturas 14 y 15 muestran ambos estados. La demostración acredita el mecanismo con datos reproducidos, sin convertirlos en telemetría actual.

En el nivel de subcódigo, el acumulado se calcula sobre la selección y conserva los filtros externos. Para interpretar el Pareto se comparan motivos ordenados por minutos; expandir los códigos padre agrupa la presentación. Se verificaron los niveles de código, subcódigo y combinación código/subcódigo. El cambio de contexto no modifica los 16.452 paros ni sus 502.924,10 minutos conciliados con SQL.


DBeaver quedó conectado al PostgreSQL de Docker. La primera consulta de `09_sustentacion.sql` se ejecutó en su editor y mostró las siete cifras de conciliación; el pantallazo está en `evidencias/docker/17_dbeaver_conciliacion.png`. Las otras cuatro consultas se validaron por backend, sin atribuirles ejecución en la interfaz. El recorrido de sustentación está en `SUSTENTACION.md`.
