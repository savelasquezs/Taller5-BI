# Diseño y decisiones de la solución

## Usuarios y preguntas

| Usuario | Preguntas | Consumo |
| --- | --- | --- |
| Gerencia / jefatura de producción | ¿Cómo cambian producción y pérdidas por máquina y período? ¿Qué causas priorizar? | Power BI; análisis mensual y anual |
| Supervisión / mantenimiento | ¿Llegó la última carga? ¿Qué registro/estado se reportó? ¿Se superó el umbral? | Grafana; refresco de 5–30 segundos |
| Responsable de datos | ¿Qué se rechazó, convirtió o quedó pendiente? ¿Cuadran los totales? | Logs, consultas y DBeaver; cada carga |

## Modelo y granularidad

Se mantiene una estrella lógica mediante vistas en `bi`, respaldada por las tablas relacionales con PK, FK, controles y auditoría de `public`. Esto reutiliza el trabajo validado y evita otra copia del histórico. Las claves de hechos y dimensiones se comprueban por consulta; las vistas no tienen restricciones físicas propias.

| Entidad | Grano / clave | Origen |
| --- | --- | --- |
| FactProduccion | Una fila por registro de producción; `registro_id` | Producción y suma de sus paros |
| FactParos | Una fila por incidencia; `paro_id` | Detalle subordinado, no otra producción |
| DimFecha | Un día; `fecha_id` AAAAMMDD | Calendario construido: año, mes, período y día semanal |
| DimMaquina | Una máquina; ID sustituto de catálogo | Lista de cuatro líneas |
| DimReferencia | Una referencia literal; ID sustituto, 0 desconocida | Catálogos del Excel y R04 |
| DimOperador | Una persona de catálogo; ID sustituto, 0 desconocida | Lista `Tiempos!S2:S45`; etiqueta analítica `Operario NNN` |
| DimTurno | Un turno; ID sustituto, 0 desconocido | Catálogo del Excel |
| DimMotivo | Un código con un subcódigo, o sin subcódigo; clave natural compuesta serializada `código:subcódigo` | Catálogos de códigos/subcódigos; 65 combinaciones únicas |

Código y subcódigo se aplanan en DimMotivo para formar una jerarquía de dos niveles. Los paros se unen por `motivo_id`, evitando multiplicarlos al unir únicamente por código. Los subcódigos desconocidos conservan su texto en observaciones de origen y se consumen como sin detalle catalogado. `bi.dim_causa` permanece como compatibilidad para los tableros por código.

Jerarquía temporal: año → mes/período → fecha. Las otras dimensiones permiten filtros por máquina, referencia, turno y operador seudonimizado. El diccionario CSV describe 80 columnas de las diez vistas `bi`, con tipos consultados de la base Docker desplegada, origen y transformación. Incluye también las vistas auxiliares `dim_causa` y `estado_lineas`. Las llaves se indican como lógicas: la nulabilidad reportada por PostgreSQL para una vista no reemplaza las restricciones de sus tablas base. No se relacionan los hechos entre sí: comparten dimensiones.

### Matriz de bus

| Proceso | Fecha | Máquina | Referencia | Operador | Turno | Motivo |
| --- | --- | --- | --- | --- | --- | --- |
| Producción | Sí | Sí | Sí | Sí | Sí | No |
| Paros | Sí | Sí | Sí | Sí | Sí | Sí |

Las PK y FK originales evitan referencias inexistentes; los índices de fecha/máquina y registro/código soportan filtros y agregaciones. La exclusión GiST controla solapamientos cuando existen horarios, no en los eventos históricos sin inicio/fin. No se añaden particiones ni otro motor para este volumen.

## Indicadores

Todos se filtran por máquina/período y, cuando existe el dato, referencia y turno. Una cantidad ausente se mantiene ausente. Sin un objetivo documentado de planta, no se inventa una meta de eficiencia.

| Indicador | Fórmula y unidad | Grano / fuente | Meta o umbral | Usuario |
| --- | --- | --- | --- | --- |
| Producción | Suma de pacas originales; pacas | Registro, agregado por máquina/mes/año; Excel J | Sin meta aprobada; no sumar como unidades homogéneas | Gerencia |
| Horas registradas | Suma de horas; h | Excel K | Sin meta aprobada | Producción |
| Duración y participación de paros | Suma de minutos; minutos / total de minutos | Incidencia/código/máquina; columnas de minutos | Pareto para priorizar; no prueba causa raíz | Mantenimiento |
| Productividad original | 1 − paros / (horas × 60); % | Razón de sumas; campo calculado original del Excel | Sin meta aprobada; incluye inconsistencias | Gerencia |
| Disponibilidad reconstruida | Operación / plan; % | Plan = horas × 60 − descansos 16/17; operación = horas × 60 − paros | Solo tiempos válidos; sin meta aprobada | Producción |
| Cobertura de disponibilidad | Registros válidos / registros; % | FactProduccion | Mostrar junto a disponibilidad | Responsable de datos |
| Rendimiento nominal diagnóstico | Suma de unidades nominales / velocidad, dividido por operación de las mismas filas; % | Empaque/velocidad del catálogo sin vigencia | >100 % es inconsistencia visible; no se recorta | Responsable de datos |
| Rendimiento OEE | Tiempo ideal / operación; % | Solo parámetros confirmados | Pendiente en esta fuente | Gerencia |
| Calidad | Unidades buenas / totales; % | Misma población, datos de calidad reales | Pendiente; vacío no significa 100 % | Calidad |
| OEE | Minutos buenos ideales / plan; % | Registros completos con parámetros confirmados | Pendiente; no sustituir por productividad | Gerencia |
| Cambio interanual | Pacas del año / año anterior − 1; % | DimFecha y DAX SAMEPERIODLASTYEAR | Requiere un año y comparativo existente | Gerencia |
| Referencias ausentes | Conteo con referencia desconocida; registros | R01 | Señal de calidad de datos, no producto nuevo | Responsable de datos |
| Edad del ETL | Ahora − última finalización; min | estado_etl | >15 min, espera 2 min: tres intervalos sin carga | Supervisión |
| Paro abierto | Ahora − inicio real; min | Solo paros con inicio y sin fin | >15 min, espera 2 min; no se infiere del histórico | Mantenimiento |
| DEMO: paro del último registro reproducido | Minutos originales del registro; min | demo.v_eventos, hora de emisión separada de fecha original | >60 min, espera 10 s; pérdida demostrativa de una hora | Sustentación |

Las coberturas, anomalías nominales, comparación interanual y salud del ETL amplían los gráficos existentes y explican qué decisiones pueden respaldar los datos. Los porcentajes de códigos sobre horas del Excel se distinguen del Pareto, cuyo denominador son todos los minutos de paro.

## ETL, linaje y conciliación

Python reutiliza las reglas R01–R10: producción y sus detalles se agrupan sin duplicar el registro; se contrasta la copia de subcódigos sin cargarla otra vez. Los datos numéricos se validan con Decimal. Cada grupo se guarda de manera atómica y la huella permite cargas incrementales. La lista autorizada de operadores se lee del Excel al arrancar, no de nombres personales publicados en SQL.

La conciliación compara hechos, origen y logs: 4.809 producciones, 16.452 paros, 378.727 pacas y 502.924,10 minutos. Las unidades convertidas son nominales y cubren solo parte del histórico; no se presentan como un total de unidades reales verificadas. Los 70 errores y 3.392 avisos permanecen disponibles para revisión. No se borran registros dudosos para mejorar un indicador.

## Grafana frente a Power BI

| Aspecto | Grafana | Power BI |
| --- | --- | --- |
| Pregunta | ¿Qué acaba de llegar y qué alerta requiere atención? | ¿Qué cambió y qué causas o máquinas conviene priorizar? |
| Usuario | Supervisión y mantenimiento | Gerencia y producción |
| Actualización | Consulta cada 5–30 s; ETL cada 5 min, demo cada 60 s | Importación al pulsar Actualizar; sin Power BI Service |
| Interacción | Series, estados, variables y alertas | Segmentaciones, jerarquía, comparación anual y Pareto |

Un refresco frecuente de Grafana no hace actual al Excel de 2022–2025. La reproducción está etiquetada y separada en `demo`; no crea una medición de planta. Power BI mantiene el histórico fuera de esa demostración.

## Seguridad, SCD y evolución

Acceso local autenticado: administrador para DBeaver, ETL con permisos de carga y BI de solo lectura. Nombres originales y observaciones quedan en la fuente/base privada; DimOperador usa etiquetas técnicas. Esto es seudonimización, no anonimización irreversible. `.env`, Excel, PBIX con datos, Word, PDF y logs no se publican en Git. No se utiliza publicación anónima de Power BI.

Para velocidades y empaques se propone SCD tipo 2 cuando planta entregue fechas de vigencia: versión por máquina/referencia con inicio y fin reales. No se crean versiones históricas a partir de contradicciones sin fecha. Actualmente los parámetros se muestran solo como referencia nominal.

Con PLC/SCADA se sustituiría la extracción manual por eventos con ID estable, timestamp, máquina, estado y contadores de producción/calidad. Se conservarían las dimensiones y contratos de consumo, añadiendo control de eventos tardíos y validación de relojes. No se necesitan Kafka ni una plataforma adicional para el taller actual.

## Límites de la entrega

La fuente no permite demostrar OEE real completo. La alerta DEMO demuestra el mecanismo, no una condición industrial actual. El documento pegado perdió algunas cantidades de la rúbrica; deben contrastarse con el original. El informe final y los aportes de cada integrante son responsabilidad de sus autores; las capturas sirven de soporte, sin fabricar evidencias o participación.
