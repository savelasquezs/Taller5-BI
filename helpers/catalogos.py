import warnings

from openpyxl import load_workbook

from helpers.excel import opcional


def cargar_operadores(conexion, ruta):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        libro = load_workbook(ruta, read_only=True, data_only=True)
    try:
        nombres = sorted({nombre for fila in libro["Tiempos"].iter_rows(
            min_row=2, min_col=19, max_col=19, values_only=True)
                          if (nombre := opcional(fila[0])) is not None})
        if not nombres:
            raise ValueError("El catálogo de operadores de Tiempos está vacío")
        with conexion.cursor() as cursor:
            cursor.executemany("INSERT INTO operadores(nombre) VALUES(%s) ON CONFLICT(nombre) DO NOTHING",
                               [(nombre,) for nombre in nombres])
    finally:
        libro.close()
