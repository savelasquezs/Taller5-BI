# Evidencias para el informe

Las capturas de las partes 1–3 siguientes corresponden a la instalación local anterior a Docker. Los nuevos pantallazos del despliegue se añaden por separado: una comprobación por API o un log no se presenta como captura de pantalla.

## Parte 1 · 1. Esquema relacional

Se creó la base de PostgreSQL con las tablas de producción, detalle de paros y sus catálogos. Las claves primarias, relaciones y restricciones mantienen los registros organizados y evitan datos inconsistentes.

![Esquema](evidencias/parte1/01_esquema.jpg)

## Parte 1 · 2. Catálogos

Se cargaron máquinas, referencias, operadores, turnos y motivos de paro a partir de los archivos del taller. Estos catálogos permiten usar los mismos nombres y códigos en todas las cargas.

![Catálogos](evidencias/parte1/02_catalogos.jpg)

## Parte 1 · 3. Integridad

Se verificaron el procedimiento para registrar paros, los triggers de validación y la auditoría. Las pruebas comprueban duraciones y solapamientos cuando existen horarios; los datos históricos sin horas de inicio y fin conservan esa limitación.

![Integridad](evidencias/parte1/03_integridad.jpg)

## Parte 2 · Carga automática

Python lee el Excel y carga producción y paros en PostgreSQL cada cinco minutos. La captura del registro real de ejecución muestra 4.809 producciones reconocidas sin cambios: la repetición no generó duplicados. La captura corresponde a la validación inicial, con 70 errores y 3.390 advertencias. Tras recuperar parámetros con R08, la repetición sigue sin duplicados y registra 3.392 advertencias en `logs/ultima_ejecucion.json`.

![Ejecución automática](evidencias/parte2/01_carga_automatica.png)

## Parte 3 · Grafana

El tablero supervisa la última carga, las incidencias y el estado disponible por máquina. Como el Excel termina en marzo de 2025, informa que no hay telemetría actual; tampoco muestra un OEE inventado. Las alertas son locales y no envían mensajes externos.

![Supervisión](evidencias/parte3/02_grafana_supervision.jpg)

El tablero histórico conserva los totales de producción y ordena las causas por minutos de paro. Las seis primeras reúnen aproximadamente el 83,7 % de los minutos registrados y sirven como punto de partida para revisar las pérdidas.

![Pareto](evidencias/parte3/01_grafana_historico.jpg)

## Parte 3 · Power BI: producción

Se importaron las vistas de PostgreSQL y se guardó `powerbi/Taller5.pbix` con datos reales. La página permite filtrar producción por máquina, año y referencia, y revisar su evolución mensual. Los totales coinciden con la base y el filtro Vinilos_1 devuelve 994 producciones y 100.046 pacas.

![Producción histórica](<evidencias/parte3/powerbi/Producción histórica.png>)

## Parte 3 · Power BI: Pareto

El gráfico ordena los motivos de paro de mayor a menor duración y muestra su porcentaje acumulado. Ayuda a priorizar la revisión de las pérdidas; no demuestra por sí solo la causa raíz. Los 16.452 paros conservan sus 502.924,10 minutos registrados.

![Paros y Pareto](<evidencias/parte3/powerbi/Paros y Pareto.png>)

## Parte 3 · Power BI: OEE

La disponibilidad reconstruida del Excel es 84,13 %, con 4.752 registros válidos y 98,8 % de cobertura. El 77,97 % corresponde a tiempo sin paros sobre horas registradas, con la fórmula original. Calidad y OEE completo siguen pendientes: no se inventaron unidades buenas ni se confirmó la vigencia del catálogo.

![OEE y calidad de datos](<evidencias/parte3/powerbi/OEE y calidad de datos.png>)

## Parte 3 · Power BI: parámetros por período

Se revisaron 142 combinaciones de mes y máquina. La página muestra los parámetros nominales y los 626 registros cuyo rendimiento diagnóstico supera el 100 %. Se conservan para revisión, sin recortar valores ni usarlos como OEE. El modelo antiguo y el catálogo discrepan sin fechas de vigencia.

![Parámetros por período](<evidencias/parte3/powerbi/Parámetros por período.png>)

Las decisiones y cifras completas están en `DECISIONES_ETL.md`, `PUESTA_EN_MARCHA.md` y `PARTE3.md`. Las comprobaciones están en `logs/`.

## Docker · comprobaciones registradas

El arranque limpio recuperó 4.809 producciones y 16.452 paros; la carga repetida reconoció todo sin cambios. Las 21 pruebas del ETL pasaron. `logs/docker/verificacion.json` registra 28 consultas de paneles válidas, 65 motivos únicos y acceso BI sin escritura; `logs/docker/prueba_desde_cero/` conserva la prueba independiente. Estos son registros técnicos; las nuevas capturas deben mostrar el despliegue y la reproducción/alerta observados.

La arquitectura compacta está en `docs/arquitectura.svg`; representa Docker, las aplicaciones del host y la reproducción separada. No corresponde a una captura de una aplicación.
