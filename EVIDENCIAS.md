# Evidencias para el informe

Las capturas de las partes 1–2 y los dos tableros Grafana iniciales conservan la instalación anterior. Las cuatro páginas Power BI siguientes y el apartado Docker muestran la entrega actual; los logs y comprobaciones por API se identifican por separado.

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

Se importaron las vistas de PostgreSQL Docker y se guardó **`powerbi/Taller5_Docker.pbix`** con datos reales. La página permite filtrar producción por máquina, año y referencia, y revisar su evolución mensual. Los totales coinciden con la base y el filtro Vinilos_1 devuelve 994 producciones y 100.046 pacas.

![Producción histórica en Docker](evidencias/docker/powerbi/01_produccion.png)

## Parte 3 · Power BI: Pareto

El gráfico ordena los motivos de paro de mayor a menor duración y muestra su porcentaje acumulado. Ayuda a priorizar la revisión de las pérdidas; no demuestra por sí solo la causa raíz. Los 16.452 paros conservan sus 502.924,10 minutos registrados.

![Paros y Pareto en Docker](evidencias/docker/powerbi/02_paros.png)

## Parte 3 · Power BI: OEE

La disponibilidad reconstruida del Excel es 84,13 %, con 4.752 registros válidos y 98,8 % de cobertura. El 77,97 % corresponde a tiempo sin paros sobre horas registradas, con la fórmula original. Calidad y OEE completo siguen pendientes: no se inventaron unidades buenas ni se confirmó la vigencia del catálogo.

![OEE y calidad de datos en Docker](evidencias/docker/powerbi/03_oee.png)

## Parte 3 · Power BI: parámetros por período

Se revisaron 142 combinaciones de mes y máquina. La página muestra los parámetros nominales y los 626 registros cuyo rendimiento diagnóstico supera el 100 %. Se conservan para revisión, sin recortar valores ni usarlos como OEE. El modelo antiguo y el catálogo discrepan sin fechas de vigencia.

![Parámetros por período en Docker](evidencias/docker/powerbi/04_parametros.png)

Las decisiones y cifras completas están en `DECISIONES_ETL.md`, `PUESTA_EN_MARCHA.md` y `PARTE3.md`. Las comprobaciones están en `logs/`.

## Docker · comprobaciones registradas

El arranque limpio recuperó 4.809 producciones y 16.452 paros; la carga repetida reconoció todo sin cambios. Las 21 pruebas del ETL pasaron. `logs/docker/verificacion.json` registra 29 consultas de paneles válidas, 65 motivos únicos y acceso BI sin escritura; `logs/docker/prueba_desde_cero/` conserva la prueba independiente. La importación se verificó también en el motor nativo de Power BI: ocho tablas, 36 medidas, once relaciones y totales coincidentes (`logs/docker/verificacion_powerbi.json`). Las capturas siguientes muestran el despliegue y la demostración observados.

La arquitectura compacta está en `docs/arquitectura.svg`; representa Docker, las aplicaciones del host y la reproducción separada. No corresponde a una captura de una aplicación.


## Docker · reproducción histórica

Grafana recibe cada minuto un registro histórico real, conservando su ID y fecha original. La hora virtual y la emisión están separadas; no se inventó producción ni calidad.

![Reproducción histórica en Docker](evidencias/13_grafana_docker_demo.png)

## Docker · alerta activa

El registro reproducido supera 60 minutos de paro y activa la regla DEMO. La API confirmó el estado activo a las 23:15:47 del 4 de noviembre de 2026 (Colombia); el umbral es didáctico.

![Alerta DEMO activa](evidencias/14_grafana_docker_alerta_activa.png)

## Docker · alerta recuperada

El siguiente registro queda bajo el umbral y la alerta se recupera. La API confirmó la recuperación a las 23:16:37; las muestras están en `logs/docker/alerta_demo.json`.

![Alerta DEMO recuperada](evidencias/15_grafana_docker_alerta_recuperada.png)

## Docker · contenedores

El despliegue reúne PostgreSQL, ETL y Grafana; el perfil opcional añade la reproducción. Power BI y DBeaver se ejecutan en Windows y consultan la base local de Docker.

![Contenedores del taller](evidencias/16_docker_contenedores.png)


## Power BI · comparativo 2025

El año 2025 tiene 25.496 pacas frente a 137.953 en 2024: −81,5 %. Se indica **2025 parcial** porque el histórico termina el 28 de marzo; no representa períodos de igual duración.

![Comparativo 2025 parcial](evidencias/docker/powerbi/06_comparativo_2025.png)


## Power BI · desglose por subcódigo

En el nivel de subcódigo, el acumulado se calcula sobre la selección y conserva los filtros externos. Para interpretar el Pareto se comparan motivos ordenados por minutos; expandir los códigos padre agrupa la presentación. Los totales permanecen conciliados con SQL.

![Desglose por subcódigo](evidencias/docker/powerbi/05_desglose_subcodigos.png)
