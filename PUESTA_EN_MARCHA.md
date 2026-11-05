# Puesta en marcha de las partes 1 y 2

Fecha: 2026-11-04. El despliegue vigente usa Docker; los apartados iniciales conservan la evidencia de la instalación anterior en 55439/3001. Para repetir el despliegue, seguir `README.md`.

## Parte 1 Base permanente

PostgreSQL 17.6 guarda los datos en `%USERPROFILE%\Taller5Datos\PostgreSQL17`, fuera de la carpeta temporal de pruebas. Se ejecutaron los scripts 01 y 02, la migración 04 y las ocho validaciones del script 03; los datos de esas pruebas se revirtieron.

| Conexión | Valor |
| --- | --- |
| Servidor | `127.0.0.1` |
| Puerto | `55439` |
| Base | `taller5` |
| Usuario | `taller5` |

La configuración está en `%USERPROFILE%\Taller5Datos\conexion.json` y la contraseña en `pgpass.conf` de esa misma carpeta. El ejecutor configura `DATABASE_URL` y `PGPASSFILE` para cada carga. La instancia acepta conexiones locales y usa autenticación con contraseña.

## Parte 2 Carga automática

Se creó `.venv` con Python 3.14.7, openpyxl 3.1.5 y psycopg 3.3.8. La tarea de Windows `Taller5-CargaExcel` ejecuta `ejecutar_carga.py` cada cinco minutos y al iniciar sesión, sin abrir ventanas. Si PostgreSQL está detenido, el ejecutor lo inicia primero.

La tarea funciona mientras el equipo esté encendido, activo y el usuario tenga sesión abierta. Evita ejecuciones simultáneas y permite dos reintentos ante un fallo operativo. Las 70 incidencias de datos conocidas se informan como carga completada con incidencias; no se confunden con un fallo de conexión o del programa.

## Evidencia y seguimiento

- `logs/despliegue_sql.log`: ejecución del esquema, catálogos y validaciones.
- `logs/ultima_ejecucion.json`: estado, horario y resumen de la última carga.
- `logs/ejecuciones_etl.log`: historial de ejecuciones, con rotación de tamaño.
- `logs/carga_errores.csv`: filas pendientes y advertencias de calidad.
- `logs/verificacion_despliegue.json`: comprobación de la tarea y conteos finales.

Las reglas de transformación y sus motivos siguen en `DECISIONES_ETL.md`. Esta puesta en marcha conserva los datos faltantes como faltantes; no completa los valores necesarios para OEE.

## Resultado comprobado

La ejecución por horario del 4 de noviembre, a las 08:37 de Colombia, inició PostgreSQL detenido y cargó 4.809 producciones y 16.452 paros. Se verificaron 10 tablas, 9 claves foráneas, 3 triggers y el procedimiento `registrar_paro`.

Una segunda ejecución desde el Programador de tareas terminó con código operativo `0` y reconoció las 4.809 producciones sin cambios. Los conteos y las 21.261 entradas de auditoría permanecieron iguales. Continúan documentados 70 errores de origen y 3.390 advertencias.

## Continuación: parte 3

Se ejecutó `05_modelo_analitico.sql` antes de habilitar la publicación del estado del ETL. Agrega las vistas analíticas y la tabla técnica `estado_etl`: ahora hay 11 tablas físicas, sin cambiar las relaciones del modelo de producción. `06_validacion_oee.sql` prueba las fórmulas sin conservar datos sintéticos.

Los tableros, las medidas DAX, las decisiones analíticas y los límites de los datos se describen en `PARTE3.md`. Grafana usa el puerto local `3001`; PostgreSQL conserva el `55439`. Las credenciales de lectura y de Grafana están fuera de la carpeta del taller, en `%USERPROFILE%\Taller5Datos`.

En la instalación anterior, Power BI quedó guardado en `powerbi/Taller5.pbix`; se conserva como antecedente. La entrega final Docker es `powerbi/Taller5_Docker.pbix`. La conexión usa el controlador PostgreSQL Unicode x64 17 y el DSN de usuario `Taller5BI`. Las ocho vistas se importaron y verificaron contra PostgreSQL; los resultados están en `logs/verificacion_powerbi.json`. Las descripciones y capturas para el informe se reúnen en `EVIDENCIAS.md`.

## Recuperación de parámetros, 4 de noviembre

R08 recuperó empaque y velocidad nominal en 2.448 producciones; la vista analítica convierte sus pacas a unidades. Se conservaron los totales originales. La siguiente ejecución programada reconoció las 4.809 producciones sin cambios: 70 errores de origen y 3.392 advertencias. Pasaron 21 pruebas del ETL y las validaciones SQL con reversión. El respaldo previo está fuera de la entrega, en `Taller5Datos`. No existen datos reales suficientes de planificación ni calidad para calcular OEE.

## Ajuste del modelo por períodos

Se volvió a aplicar `05_modelo_analitico.sql` y se ampliaron las validaciones de `06_validacion_oee.sql`. No se añadieron tablas ni se modificaron los registros de planta: la reconstrucción ocurre en la vista. Disponibilidad: 84,13 % con 4.752 registros; productividad original: 77,97 %. El catálogo queda como referencia nominal, sin confirmar vigencia histórica. La revisión de 142 combinaciones mes/máquina está en `logs/revision_parametros_periodo.csv`. El reporte incorpora una cuarta página y Grafana muestra los nuevos indicadores históricos. OEE completo continúa pendiente de calidad y parámetros confirmados; ver `PARTE3.md`.

## Despliegue vigente: Docker

`docker compose up -d --build` levanta PostgreSQL 17.6 (puerto local 55440), ETL Python y Grafana 13.2.3 (3002), con volúmenes persistentes y aprovisionamiento de tableros/alertas. La fuente se monta de solo lectura. Las instalaciones anteriores permanecen independientes. Power BI y DBeaver corren en Windows; el proyecto usa el DSN `Taller5Docker`.

Se comprobó el arranque independiente desde volúmenes nuevos con el proyecto `taller5-prueba`: cargó 4.809 producciones y 16.452 paros sin configuración manual de SQL. Se detuvo sin borrar los volúmenes. En el despliegue principal la repetición reconoció las 4.809 producciones sin cambios; pasaron las 21 pruebas del ETL. Evidencia: `logs/docker/prueba_desde_cero/`, `logs/docker/pruebas_etl.log` y `logs/docker/ultima_ejecucion.json`.

La verificación de Docker contrastó totales, 65 claves únicas de motivo sin huérfanos, nombres analíticos seudonimizados y usuario BI sin escritura. Verificó 29 consultas de paneles y tres reglas de alerta saludables. La alerta DEMO se observó activa a las 23:15:47 y recuperada a las 23:16:37 (Colombia); muestras en `logs/docker/alerta_demo.json` y pantallazos en `evidencias/14_grafana_docker_alerta_activa.png` y `15_grafana_docker_alerta_recuperada.png`. Resultado general: `logs/docker/verificacion.json`.

Las claves están en `.env`, excluido de Git. Los permisos de carga incluyen referencias a producción, necesarias para la tabla de control incremental. `down` conserva datos; `down -v` los eliminaría. Instrucciones de respaldo/restauración y conexión están en `README.md`.

## Comprobación de los documentos actualizados

El Excel descargado nuevamente coincide byte a byte con la fuente del proyecto (SHA-256 `c7d7eabbd55844757c2be07bd61efcee9eb5e0b03aaf9fd76b798737a92d5c55`). Los PDF difieren en bytes, pero sus siete páginas tienen el mismo texto, imágenes decodificadas, contenido gráfico y tamaño; no hay anotaciones ni adjuntos. No se encontraron datos ni instrucciones nuevos en estos dos archivos.

La importación Docker quedó verificada en el motor nativo de Power BI: ocho tablas, 36 medidas, once relaciones y totales 4.809/16.452. También se comprobaron el filtro de máquina, el detalle por subcódigo y el comparativo anual; 2025 está identificado como parcial. Evidencia: `logs/docker/verificacion_powerbi.json`. El archivo final `powerbi/Taller5_Docker.pbix` ya se guardó y se verificó también leyendo su modelo binario. `Taller5.pbix` se conserva como antecedente de la instalación anterior.
