import io
import re
from collections import defaultdict
from xml.etree import ElementTree
from zipfile import ZipFile

from openpyxl.utils.cell import range_boundaries

from helpers.excel import entero, etiqueta, numero, opcional


TABLAS = {"Tabla8": "Vinilos_1", "Tabla14": "Vinilos_2", "Tabla15": "Vinilos_3", "Tabla16": "Vinilos_4"}


def leer_parametros(libro, contenido):
    hoja = "Tablas Desplegables"
    if hoja not in libro.sheetnames:
        return {}, []
    candidatos = defaultdict(list)
    incidencias = []
    with ZipFile(io.BytesIO(contenido)) as archivo:
        for nombre in archivo.namelist():
            if not nombre.startswith("xl/tables/") or not nombre.endswith(".xml"):
                continue
            tabla = ElementTree.fromstring(archivo.read(nombre))
            nombre_tabla = tabla.get("name")
            if nombre_tabla not in TABLAS:
                continue
            maquina = TABLAS[nombre_tabla]
            izquierda, arriba, derecha, abajo = range_boundaries(tabla.get("ref"))
            filas = libro[hoja].iter_rows(min_row=arriba, max_row=abajo,
                                         min_col=izquierda, max_col=derecha, values_only=True)
            cabecera = next(filas)
            if etiqueta(cabecera[0]) != "maquina" or etiqueta(cabecera[1]) != "nombre de referencia":
                raise ValueError(f"La estructura del catálogo {nombre_tabla} cambió")
            for indice, fila in enumerate(filas, arriba + 1):
                referencia = opcional(fila[1])
                if referencia is None:
                    continue
                try:
                    if etiqueta(fila[0]) != etiqueta(maquina):
                        raise ValueError("máquina distinta de la tabla utilizada por la calculadora")
                    unidades = entero(fila[2], "unidades por display")
                    displays = entero(fila[4], "displays por paca")
                    if unidades is None or displays is None or numero(fila[3], "pacas") != 1:
                        raise ValueError("empaque sin equivalencia válida por una paca")
                    colores = re.search(r"\((\d+)\s*col", referencia, re.IGNORECASE)
                    if colores and int(colores[1]) != unidades:
                        raise ValueError("cantidad de colores incompatible con el nombre de la referencia")
                    velocidad = numero(fila[6], "velocidad nominal del catálogo")
                    if velocidad is not None and velocidad <= 0:
                        raise ValueError("velocidad nominal no positiva")
                    if fila[5] is not None and numero(fila[5], "unidades por paca") != unidades * displays:
                        raise ValueError("unidades por paca incompatibles con el empaque")
                    candidatos[(etiqueta(maquina), etiqueta(referencia))].append({
                        "unidades_por_display": unidades, "displays_por_paca": displays,
                        "velocidad": velocidad, "fuente": f"{hoja}!E{indice}:I{indice} ({nombre_tabla})",
                        "fila": indice,
                    })
                except ValueError as error:
                    incidencias.append({"nivel": "ADVERTENCIA", "hoja": hoja, "fila": indice,
                                        "motivo": f"ETL R08: parámetro omitido: {error}"})
    parametros = {}
    for clave, opciones in candidatos.items():
        valores = {(p["unidades_por_display"], p["displays_por_paca"], p["velocidad"]) for p in opciones}
        if len(valores) == 1:
            parametros[clave] = opciones[0]
        else:
            incidencias.append({"nivel": "ADVERTENCIA", "hoja": hoja, "fila": opciones[0]["fila"],
                                "motivo": "ETL R08: parámetros contradictorios para la misma máquina y referencia"})
    return parametros, incidencias
