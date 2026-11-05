# Revisión de fuentes para OEE — 2026-11-04

La conclusión anterior fue demasiado tajante: la ausencia de una columna de tiempo planificado no prueba que ese tiempo sea irrecuperable. El libro contiene una regla para reconstruirlo. Sigue sin encontrarse un conteo de unidades buenas o rechazadas que permita demostrar OEE completo.

## Fuentes revisadas

- Excel original: las 21 hojas, incluidas las cuatro ocultas; valores, fórmulas, nombres definidos, tablas, cachés de tablas dinámicas, 24 módulos VBA y consultas Power Query. Se leyeron sin ejecutar macros ni guardar el libro.
- Modelo Power Pivot incrustado en `xl/model/item.data`: se extrajeron sus dos tablas y metadatos. Es una copia antigua, no otra fuente independiente de producción.
- PDF: sus siete páginas, texto e imágenes; no contiene archivos adjuntos. El ejemplo físico de la página 2 tiene una columna de no conformes vacía.
- Word: contiene el informe de la Parte 1, sin registros adicionales ni una regla de cálculo de OEE.
- SQL, Python, Power BI, Grafana y logs: contienen transformaciones y resultados derivados de esas fuentes, no mediciones nuevas de calidad.

## Hallazgos y consecuencias

| Elemento | Evidencia | Consecuencia |
| --- | --- | --- |
| Tiempo programado | `Calculadora de tiempos!G12 = G6-SUM(G7:G8)`. G6 toma horas de `Registro!C8`; G7/G8 toman alimentación/aseo y pausa activa de I18/I19. Las macros guardan esos mismos campos como horas y códigos 16/17. | Podemos reconstruir el tiempo según la regla del libro, usando descansos históricos registrados, sin imponer descansos actuales a todos los años. Falta confirmar que las horas tienen la misma interpretación en todo el histórico. |
| Tiempo operativo | Las duraciones por código se conservan en producción y sus detalles. `Tiempo de Paro` es su suma en horas, no una duración adicional. | Para explorar: operativo = horas × 60 − todos los paros registrados; no volver a restar descansos después. Hace falta comprobar integridad y posibles duraciones duplicadas sin horarios. |
| Horas sin trabajar | Hay valores de 24, 16 y 13,5 horas y observaciones de falta de demanda. | No deben sumarse automáticamente al tiempo planificado: pueden representar tiempo sin programación. Tampoco se deben reemplazar horas registradas por ocho horas para todos los turnos. |
| Velocidad y empaque | El modelo antiguo tiene 787 filas de producción de 2023-10-23 a 2024-02-13, más 1.251 detalles. Guarda velocidad `72 und` en 653 filas y empaques distintos del catálogo actual. | R08 es una aplicación de parámetros nominales del catálogo, no una recuperación certificada de vigencia histórica. No dar prioridad automática al modelo antiguo ni al catálogo actual. |
| Contraste del modelo antiguo | 764 filas coinciden de forma única con fecha, máquina, operador, turno, pacas y horas del Excel actual. Ninguna recupera una referencia ausente. En 643 comparables con parámetros actuales, todas presentan alguna diferencia de empaque o velocidad. | La copia antigua sirve para detectar cambios o errores; no se carga como producción adicional. Ejemplo: Parchesitos 125 cc, Vinilos_2: empaque 1×1 y velocidad 72 en el modelo frente a 1×48 y velocidad 48 en el catálogo. |
| Eficiencia del formulario | `Tiempos!C8 = IF(C6=0,0,(C6/C5)*fProduccion)`; C5 es horas × meta por hora. No incluye un conteo de conformes. La macro no guarda meta ni eficiencia. | Es cumplimiento de una meta ajustada por un factor, no evidencia de OEE completo. Los factores 0,93/0,96 de otra calculadora tampoco están identificados como calidad. |
| Productividad de los gráficos | El campo calculado `% Productividad`, en `xl/pivotCache/pivotCacheDefinition2.xml`, usa `('Horas trabajadas'-'Tiempo de Paro')/'Horas trabajadas'`. Los gráficos del PDF presentan esta familia de porcentajes, incluido 76,3 % en su ejemplo por códigos. | Sí existe un indicador original reproducible: proporción de tiempo sin paros registrados. No utiliza producción ideal ni unidades conformes, por lo que no demuestra OEE. Su denominador incluye descansos; no confundirlo con disponibilidad neta de descansos. |
| Calidad | Códigos 11, 12 y 13 almacenan minutos de reproceso, materia prima defectuosa y espera de laboratorio. Las notas mencionan rechazos de bultos de insumos, sin conteo conciliable de producto terminado. El modelo incrustado tampoco tiene buenos/rechazados. | No convertir esos minutos o bultos en unidades defectuosas; ausencia de un paro de calidad no demuestra calidad del 100 %. Tampoco está definido que las pacas registradas sean exclusivamente producto bueno a la primera. |
| Contradicciones de fórmulas | `Tablas Desplegables!K125` resta `(code16-code17)`, mientras G12 y K185 restan la suma de ambos descansos. El formulario, catálogo y PDF también discrepan sobre el código 18. | Seguir una definición explícita y documentar la discrepancia; no mezclar fórmulas ni excluir todos los paros “programados” del OEE. Un cambio de referencia puede ser pérdida de disponibilidad. |
| Conexiones externas | Las dos consultas M apuntan a un archivo externo de personal de mantenimiento. | No contienen planificación ni cantidades de calidad. No se accedió a ese archivo externo. |

## Exploración numérica, sin modificar la base

Se aplicó únicamente como diagnóstico la regla `plan = horas × 60 − códigos 16/17` y `operativo = horas × 60 − suma de paros`. Se usaron los paros vinculados por el ETL; estos resultados no prueban que no haya omisiones o solapamientos en la fuente.

| Comprobación | Registros |
| --- | ---: |
| Total cargado | 4.809 |
| Plan reconstruido positivo | 4.755 |
| Plan positivo y operativo no negativo: candidatos a disponibilidad | 4.752 |
| Suma de paros superior a horas registradas, en todo el histórico | 46 |
| Plan y operativo positivos, con velocidad nominal: candidatos a revisar rendimiento | 2.423 |
| Producción positiva y rendimiento entre 0 y 100 % con el catálogo actual | 1.792 |
| Rendimiento superior al 100 % con el catálogo actual | 626 |

Los 1.792 y 626 no agotan los 2.423 candidatos: cinco tienen producción cero. No se recortaron porcentajes ni se seleccionaron únicamente resultados favorables. Los 626 casos requieren revisar unidades, velocidad y tiempos antes de publicar rendimiento. Ninguno de estos conteos equivale a registros con OEE completo.

Aplicando la fórmula original al histórico cargado (razón de sumas), el tiempo sin paros registrados representa: Vinilos_1 **74,23 %**, Vinilos_2 **67,53 %**, Vinilos_3 **80,84 %** y Vinilos_4 **80,73 %**. Son resultados descriptivos del registro completo; incluyen sus inconsistencias y no son OEE ni disponibilidad neta de descansos.

## Recomendación

1. Calcular disponibilidad reconstruida siguiendo la regla del libro, con su cobertura y excepciones visibles, una vez validada la interpretación temporal.
   Como contraste inmediato, reproducir también `% Productividad` con su fórmula original y un nombre que indique lo que mide: tiempo sin paros registrados / horas registradas.
2. Revisar rendimiento por máquina, referencia y período; conservar ambas versiones de parámetros como evidencia y resolver discrepancias antes de usarlas como valores históricos.
3. Mantener calidad y OEE completo pendientes de una definición respaldada del conteo bueno. Un OEE simplificado puede calcularse con conteo bueno, velocidad ideal y tiempo planificado, sin exigir toda la clasificación de paros; ese conteo bueno todavía no está demostrado aquí.

La solicitud académica de OEE justifica investigar estas derivaciones, pero no establece que una celda vacía signifique cero rechazos. Para cumplir el cálculo completo con datos reales sigue faltando evidencia de calidad, no una fórmula adicional. Esta investigación no cambió el Excel, Word, base de producción ni reporte.

Evidencia técnica: `logs/inventario_fuentes_oee.json`, `logs/auditoria_vba_oee.txt`, `logs/auditoria_modelo_excel.txt`, `logs/auditoria_enlace_modelo.json`, `logs/auditoria_textos_oee.json`, `logs/auditoria_formulas_pivote_oee.json` y `logs/investigacion_oee_profunda.json`. Los extractos intermedios grandes se conservan fuera de la entrega en `%USERPROFILE%/Taller5Datos`.

Referencias: [cálculo de OEE y fórmula simplificada](https://www.oee.com/calculating-oee/), [pérdidas de programación y disponibilidad](https://www.oee.com/oee-factors/).

## Aplicación posterior

Se implementaron R09 y R10 en la vista y los reportes. Resultados y validaciones actuales en `PARTE3.md`; revisión mensual en `logs/revision_parametros_periodo.csv`. Se mantienen sin confirmar los parámetros históricos y la calidad.
