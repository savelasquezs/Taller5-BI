# Guía de sustentación · 5–8 minutos

## 1. Levantar la solución · 30 segundos

Desde la carpeta del proyecto, con Docker Desktop iniciado:

```powershell
docker compose --profile demo up -d --build
docker compose ps
```

Mostrar PostgreSQL, ETL, Grafana y demo. Explicar: «Los servicios de servidor están en Docker; los datos persisten en volúmenes y Grafana se configura automáticamente». No usar `down -v`.

## 2. DBeaver y modelo · 1 minuto

Abrir la conexión PostgreSQL del taller: `localhost`, puerto `55440`, base `taller5`, usuario `taller5`. Si solicita clave, usar `POSTGRES_PASSWORD` de `.env` sin mostrarla en pantalla. La contraseña no queda almacenada en el perfil; puede solicitarse otra vez al reiniciar DBeaver. La prueba de conexión ya confirmó PostgreSQL 17.6 y JDBC 42.7.13.

Expandir `public` para mostrar producción, detalles y catálogos; después `bi` para las vistas analíticas. Explicar: «Una producción puede tener varios paros; las vistas forman una estrella lógica sin duplicar el histórico».

## 3. Consultas · 1 minuto

Abrir `09_sustentacion.sql` en el editor conectado al taller. Seleccionar una consulta y pulsar **Ctrl+Enter**. Mostrar los conteos y la conciliación: **4.809 producciones, 16.452 paros, 378.727 pacas y 502.924,10 minutos**. La primera consulta ya se ejecutó en DBeaver y mostró siete cifras, incluida disponibilidad 84,13 % y cero registros con OEE completo; la captura está en `evidencias/docker/17_dbeaver_conciliacion.png`. Las otras cuatro consultas se validaron por backend. En `08_consultas_analiticas.sql`, ejecutar el Pareto o el comparativo anual y señalar la función de ventana. No volver a ejecutar el DDL sobre la base existente.

## 4. Carga incremental · 30 segundos

```powershell
docker compose exec -T etl python ejecutar_carga.py
```

Mostrar `sin_cambios: 4809` al terminar. Explicar: «La huella evita volver a insertar lo ya cargado; los errores de origen se registran y los faltantes no se inventan». Si coincide con otra carga, esperar su finalización y repetir la demostración.

## 5. Power BI · 1–2 minutos

Abrir **`powerbi/Taller5_Docker.pbix`**, pulsar **Actualizar** y revisar las cuatro páginas. Filtrar una máquina y después 2025: **25.496 pacas**, marcado como año parcial hasta el 28 de marzo; no se compara como período equivalente con 2024 completo. En Pareto, profundizar de código a subcódigo y ordenar motivos por minutos. El acumulado conserva la selección externa; expandir padres agrupa la presentación.

Mostrar disponibilidad **84,13 %** y cobertura **98,8 %**. Explicar: «Calidad y OEE completo quedan sin calcular porque faltan unidades buenas/rechazadas y parámetros con vigencia confirmada. El rendimiento nominal es diagnóstico y conserva las anomalías».

## 6. Grafana y alerta · 1–2 minutos

Abrir [Grafana](http://localhost:3002), usuario `admin`, clave `GRAFANA_PASSWORD` de `.env`. Mostrar histórico, supervisión y **Reproducción histórica en vivo**. Elegir todas las máquinas para la demostración. Esperar la secuencia normal → registro con más de 60 minutos de paro → normal; cada paso tarda 60 segundos. La alerta DEMO evalúa cada diez segundos y requiere diez segundos sobre el umbral; luego se recupera.

Aclarar: «Son registros históricos reales con ID y fecha originales. La emisión es actual y la hora virtual avanza una hora por paso; las cantidades pertenecen al registro completo. No es telemetría actual de planta». En estado de líneas, **Sin telemetría actual** es coherente con la fuente; el refresco de pantalla no crea datos nuevos.

Para comenzar la secuencia desde el primer paso durante el ensayo, ejecutar `docker compose restart demo`. No reiniciar el resto de servicios durante la exposición.

## 7. Cierre · 30 segundos

Las seis primeras causas reúnen **83,67 %** de los minutos; separar descansos de averías y revisar ajustes, derrames y cambios de referencia. Recomendar a gerencia separar captura, catálogos y reportes; exigir IDs, horarios, unidades buenas/rechazadas y versiones de empaque/velocidad. Mostrar el [repositorio público](https://github.com/savelasquezs/Taller5-BI) y `BI_ProyectoFinal_Velasquez_Serna.pdf`.

## Tres preguntas probables

| Pregunta | Respuesta breve |
| --- | --- |
| ¿Cuál es el grano? | FactProduccion: un registro de producción. FactParos: una incidencia asociada. Por eso no se suman horas después de unir directamente todos los detalles. |
| ¿Por qué once relaciones? | Producción comparte cinco dimensiones; paros usa esas cinco y Motivo. Son relaciones de muchos a uno, sin unir directamente los hechos. |
| ¿Por qué no hay OEE completo? | No hay calidad por unidades ni parámetros históricos confirmados. Excluir filas no crea esos datos. Se informa disponibilidad reconstruida y diagnóstico nominal con su cobertura. |
