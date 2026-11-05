FROM python:3.14.0-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY cargar_excel.py ejecutar_carga.py reproducir_demo.py ./
COPY helpers ./helpers
CMD ["python", "ejecutar_carga.py", "--continuo"]
