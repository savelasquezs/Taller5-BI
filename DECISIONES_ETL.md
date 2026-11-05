# Decisiones del ETL

Registrar cada cambio con fecha, regla, motivo y efecto. Las reglas determinan qué datos entran y cómo se interpretan los resultados.

## Base del proceso 2026-10-29

- **Fuente:** `Base De Datos`; la hoja de subcódigos sirve como contraste histórico y no se carga otra vez. El Excel no se modifica.
- **Granularidad:** una fila con pacas y horas genera producción; sus filas adicionales generan paros. Se usan los minutos originales, sin sumar también las conversiones a horas.
- **Carga incremental:** fecha, máquina, operador, referencia y turno, más aparición desde el final y huella del contenido. Permite nuevas filas al principio; cambiar identificadores, borrar o reordenar eventos equivalentes requiere revisión. No se fusionan filas idénticas sin un ID que pruebe duplicidad.
- **Integridad:** cada producción y sus paros se guardan juntos o se revierten. Se conservan las correcciones manuales de calidad y los paros ajenos al ETL. Duraciones con dos decimales; tolerancia de `0.00000001` minuto solo para errores de representación numérica.

## Cambios aprobados 2026-11-04

| Regla | Tratamiento y motivo | Efecto |
| --- | --- | --- |
| R01 Referencia ausente | Vacío o `No aplica` pasa a `NULL`, con original en observaciones y advertencia. No se deduce el producto; otros nombres desconocidos siguen rechazados. | Recupera 2.256 producciones; mostrar `Sin referencia`. |
| R02 Operador No | Solo pasa a `NULL` si pacas y horas son cero y la observación empieza por `No se programo por demanda`. Se conserva el original y no se cambia el código de paro. | Recupera 8 períodos sin asignar una persona. |
| R03 Enlace de paros | Si falta operador o turno, se enlaza únicamente con una producción compatible: fecha, máquina y referencia informadas y coincidentes; los demás campos presentes también coinciden. El criterio queda registrado. | Recupera 3 filas de detalle sin repetir producción. |
| R04 Nombre literal | Agregar `Stilo Kids 22cc (6 col)` al catálogo sin fusionarlo con `Estilo Kids`, cuya equivalencia no está confirmada. | Recupera 1 producción; mantiene ambos nombres separados. |
| R05 Datos pendientes | No convertir faltantes a cero ni elegir entre asociaciones dudosas. | Quedan 4 producciones incompletas y 66 detalles rechazados. |
| R06 Subcódigos antiguos | Conservar código principal, minutos y texto original; subcódigo desconocido como `NULL` y advertencia. No reinterpretar clasificaciones. | 1.120 casos sin subcódigo catalogado; 3 diferencias con la copia histórica no generan otra carga. |
| R07 OEE | No suponer tiempos planificados, velocidad, horarios, unidades ni calidad del 100 %. Cada componente exige sus datos y denominador válido. No equiparar pacas de productos distintos ni promediar OEE por fila. | Datos insuficientes se muestran como no calculables; horas trabajadas no equivalen automáticamente a tiempo planificado. |
| R08 Parámetros reales | Cruce exacto máquina/referencia con Tabla8, Tabla14, Tabla15 y Tabla16 de `Tablas Desplegables`. Prevalece la fila original; se registra la celda fuente. Se excluyen dos filas contradictorias. | Recupera empaque y velocidad nominal en 2.448 producciones. La vista convierte pacas a unidades con ese empaque; no deduce unidades buenas ni vigencia histórica. |
| R09 Tiempos reconstruidos | Si no existe plan explícito, usar horas × 60 menos descansos 16/17, según G12 del libro; operación = horas × 60 menos todos los paros. Plan explícito, incluso cero, prevalece. No sumar horas sin programación. | Disponibilidad en 4.752 registros (98,8 %): 84,13 %. Excluir tiempos imposibles, no corregirlos con ceros. |
| R10 Vigencia de parámetros | Matiza R08: sus empaques y velocidades son nominales, no históricos confirmados. La revisión mensual encontró 643 discrepancias con la copia antigua; no hay fechas de vigencia. | Conservar conversiones como diagnóstico, sin alimentar rendimiento OEE. Mostrar los 626 valores nominales >100 %, sin recortarlos. Calidad sigue faltante. |
| R11 Despliegue y privacidad | Docker reutiliza las reglas, sin otra copia de negocio. Roles separados: administración, carga y BI de lectura. Los operadores se cargan de `Tiempos!S2:S45`; el SQL público no incluye nombres y la vista usa `Operario NNN`. | Mismos totales; secretos y datos privados fuera de Git. La seudonimización no elimina los nombres de la fuente/base privada. |
| R12 Reproducción en vivo | El perfil opcional reproduce registros reales normal → paro >60 min → normal, con ID/fecha original y hora virtual/emisión separadas. Solo escribe metadatos en `demo.eventos`. | Permite demostrar actualización y alerta sin inventar producción, calidad ni telemetría; no altera los hechos históricos ni el OEE. |

## Validación local

| Resultado | Antes | Después |
| --- | ---: | ---: |
| Producciones | 2.544 | 4.809 |
| Paros | 11.116 | 16.452 |
| Errores | 2.338 | 70 |
| Advertencias | 4 | 3.392 |

Pasaron 21 pruebas. La segunda ejecución reconoció las 4.809 producciones sin insertar ni actualizar registros. Menos errores significa mayor cobertura, no que se hayan completado los datos ausentes.

- **Migración de bases existentes:** `04_ajustes_calidad_etl.sql`; instalaciones nuevas usan los scripts 01 y 02 actualizados.
- **Evidencia:** `logs/carga_errores.csv` y reporte anterior `logs/incidencias_antes_2026-11-04.csv`.
- **Entrada:** `SEGUIMIENTO TEMPERAS Y VINILOS Actividad.xlsm`; SHA-256 `c7d7eabbd55844757c2be07bd61efcee9eb5e0b03aaf9fd76b798737a92d5c55`.

Para futuros cambios, añadir una fila con fecha, regla, motivo y efecto; indicar qué regla reemplaza y actualizar la validación sin borrar decisiones previas.

**Capa analítica (2026-11-04):** aplica la conversión nominal de R08 con la limitación de R10. Las decisiones sobre dimensiones, OEE, supervisión y agregación se registran brevemente en `PARTE3.md`.
