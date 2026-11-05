import argparse
import csv
import io
import json
import os
import re
import sys
import warnings
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from zipfile import BadZipFile

import psycopg
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from psycopg import sql

from helpers.excel import etiqueta, entero, fecha, huella, numero, opcional, texto
from helpers.parametros import leer_parametros


BASE = "Base De Datos"
SUBCODIGOS = "Base de datos de Sub codigos"
COLUMNAS_PARO = {
    1: (15, 16), 2: (18, None), 3: (20, 21), 4: (23, None),
    5: (25, 26), 6: (30, None), 7: (32, None), 8: (34, None),
    9: (36, None), 10: (38, None), 11: (40, None), 12: (42, None),
    13: (44, None), 14: (46, None), 15: (48, None), 16: (50, None),
    17: (52, None), 18: (54, None),
}
CONTROL_SQL = """
CREATE TABLE IF NOT EXISTS control_carga_excel (
    origen TEXT NOT NULL,
    clave TEXT NOT NULL,
    fila_origen INTEGER NOT NULL,
    huella_fila TEXT NOT NULL,
    huella_grupo TEXT NOT NULL,
    registro_id BIGINT NOT NULL REFERENCES registros_produccion (id),
    paros_ids BIGINT[] NOT NULL DEFAULT '{}',
    actualizado TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (origen, clave)
)
"""
CAMPOS_PRODUCCION = (
    "fecha", "maquina_id", "referencia_id", "operador_id", "turno_id",
    "horas_trabajadas", "horas_no_trabajadas", "pacas_producidas",
    "unidades_por_display", "displays_por_paca", "unidades_ideales_por_minuto",
    "tipo_paro_reportado", "observaciones_paro", "observaciones",
)


def incidencia(errores, hoja, fila, motivo, nivel="ERROR"):
    errores.append({"nivel": nivel, "hoja": hoja, "fila": fila, "motivo": motivo})


def identidad(fila, secundaria=False):
    return (
        fecha(fila[0]).isoformat(), etiqueta(fila[3]), etiqueta(opcional(fila[4])),
        etiqueta(opcional(fila[5])), etiqueta(opcional(fila[7 if secundaria else 11])),
    )


def extraer_paros(fila, hoja, indice, secundaria=False):
    columnas = {1: (8, 9), 3: (11, 12), 5: (14, 15)} if secundaria else COLUMNAS_PARO
    paros = []
    for codigo, (columna, subcolumna) in columnas.items():
        duracion = numero(fila[columna], f"minutos del código {codigo}")
        if not duracion:
            continue
        redondeada = duracion.quantize(Decimal("0.01"))
        if abs(duracion - redondeada) > Decimal("0.00000001"):
            raise ValueError(f"Código {codigo}: duración con más de dos decimales")
        duracion = redondeada
        sub_original = opcional(fila[subcolumna]) if subcolumna is not None else None
        subcodigo = None
        if sub_original:
            coincidencia = re.match(r"^(\d+(?:\.[A-Za-z0-9]+)+)(?=\s|$)", sub_original)
            subcodigo = coincidencia[1] if coincidencia else None
        paros.append({
            "codigo": codigo, "subcodigo": subcodigo, "sub_original": sub_original,
            "minutos": duracion,
            "area": opcional(fila[17 if secundaria else 28]) if codigo == 5 else None,
            "personal": opcional(fila[18 if secundaria else 29]) if codigo == 5 else None,
            "hoja": hoja, "fila": indice,
        })
    return paros


def firma_paro(identificador, paro):
    return huella((identificador, paro["codigo"], paro["subcodigo"], paro["minutos"]))


def leer_excel(ruta, errores):
    antes = ruta.stat()
    contenido = ruta.read_bytes()
    despues = ruta.stat()
    if (antes.st_size, antes.st_mtime_ns) != (despues.st_size, despues.st_mtime_ns):
        raise ValueError("El Excel cambió durante la lectura; vuelva a ejecutar la carga")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Data Validation extension is not supported.*")
        libro = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    try:
        parametros, incidencias_parametros = leer_parametros(libro, contenido)
        errores.extend(incidencias_parametros)
        cabecera = next(libro[BASE].iter_rows(min_row=9, max_row=9, values_only=True))
        esperadas = {0: "fecha", 3: "maquina", 9: "pacas producidas", 10: "horas trabajadas", 25: "codigo de paro 5"}
        if any(etiqueta(cabecera[c]) != nombre for c, nombre in esperadas.items()):
            raise ValueError("La estructura de Base De Datos cambió")
        filas = list(libro[BASE].iter_rows(min_row=10, max_col=58, values_only=True))
        grupos = []
        por_identidad = defaultdict(list)
        por_fecha_maquina_referencia = defaultdict(list)
        filas_detalle = []
        vistos = Counter()
        firmas_base = Counter()
        actual = None
        for indice, fila in enumerate(filas, 10):
            if not any(texto(fila[c]) for c in (0, 3, 9, 10, *[p[0] for p in COLUMNAS_PARO.values()])):
                actual = None
                continue
            try:
                identificador = identidad(fila)
                paros = extraer_paros(fila, BASE, indice)
                firmas_base.update(firma_paro(identificador, paro) for paro in paros if paro["codigo"] in (1, 3, 5))
                completa = texto(fila[9]) is not None and texto(fila[10]) is not None
                parcial = (texto(fila[9]) is None) != (texto(fila[10]) is None)
                if parcial:
                    raise ValueError("Producción incompleta: falta cantidad de pacas u horas trabajadas")
                if completa:
                    if numero(fila[9], "pacas") == 0 and numero(fila[10], "horas") == 0 and opcional(fila[5]) is None and not paros:
                        actual = None
                        continue
                    grupo = {"identidad": identificador, "fila": indice, "datos": fila,
                             "paros": paros, "huella_fila": huella(tuple(texto(v) for v in fila[:30]) + tuple(texto(fila[c]) for c in list(range(30, 56, 2)) + [57]))}
                    grupo["parametros"] = parametros.get((identificador[1], identificador[3]))
                    grupos.append(grupo)
                    por_identidad[identificador].append(grupo)
                    por_fecha_maquina_referencia[(identificador[0], identificador[1], identificador[3])].append(grupo)
                    actual = grupo
                elif paros:
                    candidato = actual if actual and actual["identidad"] == identificador else None
                    filas_detalle.append((identificador, paros, indice, candidato))
                    if candidato is None:
                        actual = None
                elif actual and actual["identidad"] != identificador:
                    actual = None
            except (ValueError, ArithmeticError) as error:
                incidencia(errores, BASE, indice, str(error))
                actual = None
        for identificador, paros, indice, candidato in filas_detalle:
            candidatos = por_identidad[identificador]
            if candidato is None and len(candidatos) == 1:
                candidato = candidatos[0]
            if candidato is None and identificador[1] and identificador[3] and (not identificador[2] or not identificador[4]):
                compatibles = [g for g in por_fecha_maquina_referencia[
                    (identificador[0], identificador[1], identificador[3])
                ] if all(not valor or valor == g["identidad"][columna]
                         for columna, valor in enumerate(identificador))]
                if len(compatibles) == 1:
                    candidato = compatibles[0]
                    faltantes = ", ".join(nombre for nombre, valor in
                                         (("operador", identificador[2]), ("turno", identificador[4])) if not valor)
                    for paro in paros:
                        paro["criterio_enlace"] = f"ETL R03: enlace con producción única compatible; faltaba {faltantes} en el detalle"
                    incidencia(errores, BASE, indice,
                               f"ETL R03: paros asociados a producción de fila {candidato['fila']} por coincidencia de campos disponibles; faltaba {faltantes}", "ADVERTENCIA")
            if candidato is None:
                incidencia(errores, BASE, indice, "Paros sin producción asociada de forma inequívoca")
            else:
                candidato["paros"].extend(paros)
        for grupo in reversed(grupos):
            identificador = grupo["identidad"]
            vistos[identificador] += 1
            grupo["clave"] = huella((identificador, vistos[identificador]))
        contrastados = 0
        if SUBCODIGOS in libro.sheetnames:
            cabecera_sub = next(libro[SUBCODIGOS].iter_rows(min_row=8, max_row=8, values_only=True))
            if etiqueta(cabecera_sub[0]) != "fecha" or etiqueta(cabecera_sub[14]) != "codigo de paro 5":
                raise ValueError("La estructura de la hoja de subcódigos cambió")
            for indice, fila in enumerate(libro[SUBCODIGOS].iter_rows(min_row=9, max_col=19, values_only=True), 9):
                try:
                    if not any(texto(fila[c]) for c in (8, 11, 14)):
                        continue
                    identificador = identidad(fila, secundaria=True)
                    for paro in extraer_paros(fila, SUBCODIGOS, indice, secundaria=True):
                        firma = firma_paro(identificador, paro)
                        if firmas_base[firma]:
                            firmas_base[firma] -= 1
                            contrastados += 1
                        else:
                            incidencia(errores, SUBCODIGOS, indice,
                                       f"Código {paro['codigo']}: no coincide con la fuente principal; no se importa desde esta copia histórica", "ADVERTENCIA")
                except (ValueError, ArithmeticError) as error:
                    incidencia(errores, SUBCODIGOS, indice, str(error), "ADVERTENCIA")
        return grupos, contrastados
    finally:
        libro.close()


def catalogos(conexion):
    resultado = {}
    for tabla in ("maquinas", "referencias", "operadores", "turnos"):
        filas = conexion.execute(sql.SQL("SELECT id, nombre FROM {}").format(sql.Identifier(tabla))).fetchall()
        normalizados = {}
        for identificador, nombre in filas:
            clave = etiqueta(nombre)
            if clave in normalizados:
                raise ValueError(f"Catálogo {tabla}: nombres equivalentes duplicados")
            normalizados[clave] = identificador
        resultado[tabla] = normalizados
    resultado["codigos"] = {r[0] for r in conexion.execute("SELECT codigo FROM codigos_paro")}
    resultado["subcodigos"] = {(r[0], etiqueta(r[1])): r[1] for r in conexion.execute("SELECT codigo_paro, codigo FROM subcodigos_paro")}
    return resultado


def resolver_catalogo(catalogo, valor, nombre, obligatorio=False):
    valor = opcional(valor)
    if valor is None and not obligatorio:
        return None
    if etiqueta(valor) not in catalogo:
        raise ValueError(f"{nombre} no existe en el catálogo: {valor!r}")
    return catalogo[etiqueta(valor)]


def transformar(grupo, maestros, errores):
    fila = grupo["datos"]
    velocidad = numero(fila[6], "unidades ideales por minuto")
    if velocidad == 0:
        raise ValueError("La velocidad ideal debe ser positiva o estar vacía")
    notas_produccion = [opcional(fila[57])]
    unidades_display = entero(fila[7], "unidades por display")
    displays_paca = entero(fila[8], "displays por paca")
    parametro = grupo.get("parametros")
    if parametro:
        completados = []
        if unidades_display is None:
            unidades_display = parametro["unidades_por_display"]
            completados.append("unidades por display")
        if displays_paca is None:
            displays_paca = parametro["displays_por_paca"]
            completados.append("displays por paca")
        if velocidad is None and parametro["velocidad"] is not None:
            velocidad = parametro["velocidad"]
            completados.append("velocidad nominal")
        if completados:
            notas_produccion.append(f"ETL R08: {', '.join(completados)} recuperados de {parametro['fuente']}; "
                                    "coincidencia exacta máquina-referencia; catálogo sin vigencia histórica informada")
    referencia = opcional(fila[5])
    if referencia is None:
        notas_produccion.append(f"ETL R01: referencia original: {texto(fila[5]) or '<vacía>'}; producto sin identificar")
        incidencia(errores, BASE, grupo["fila"],
                   "ETL R01: referencia ausente; registro cargado con referencia NULL", "ADVERTENCIA")
    operador = fila[4]
    if (etiqueta(operador) == "no" and numero(fila[9], "pacas", True) == 0
            and numero(fila[10], "horas", True) == 0
            and etiqueta(fila[14]).startswith("no se programo por demanda")):
        operador = None
        notas_produccion.append("ETL R02: operador original: No; sin programación por demanda")
        incidencia(errores, BASE, grupo["fila"],
                   "ETL R02: operador original 'No' conservado como observación; operador NULL en período sin programación", "ADVERTENCIA")
    valores = (
        fecha(fila[0]), resolver_catalogo(maestros["maquinas"], fila[3], "Máquina", True),
        resolver_catalogo(maestros["referencias"], referencia, "Referencia"),
        resolver_catalogo(maestros["operadores"], operador, "Operador"),
        resolver_catalogo(maestros["turnos"], fila[11], "Turno"),
        numero(fila[10], "horas trabajadas", True), numero(fila[12], "horas no trabajadas"),
        numero(fila[9], "pacas producidas", True), unidades_display,
        displays_paca, velocidad, opcional(fila[13]),
        opcional(fila[14]), "\n".join(v for v in notas_produccion if v) or None,
    )
    paros = []
    for paro in grupo["paros"]:
        if paro["codigo"] not in maestros["codigos"]:
            raise ValueError(f"Código de paro inexistente: {paro['codigo']}")
        subcodigo = maestros["subcodigos"].get((paro["codigo"], etiqueta(paro["subcodigo"])))
        observaciones = None
        if paro["sub_original"]:
            observaciones = "Subcódigo en Excel: " + paro["sub_original"]
            if subcodigo is None:
                incidencia(errores, paro["hoja"], paro["fila"],
                           f"Subcódigo no catalogado {paro['sub_original']!r}; se conserva como observación", "ADVERTENCIA")
        if paro.get("criterio_enlace"):
            observaciones = "\n".join(v for v in (observaciones, paro["criterio_enlace"]) if v)
        paros.append((paro["codigo"], subcodigo, paro["minutos"], paro["area"], paro["personal"], observaciones))
    return valores, paros


def cargar(conexion, grupos, origen, errores, simular=False):
    resumen = Counter()
    with conexion.transaction():
        if not conexion.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0))", (origen,)).fetchone()[0]:
            raise ValueError("Ya hay otra carga ejecutándose para este origen")
        if conexion.execute("SELECT attnotnull FROM pg_attribute WHERE attrelid = 'registros_produccion'::regclass AND attname = 'referencia_id'").fetchone()[0]:
            raise ValueError("Ejecute 04_ajustes_calidad_etl.sql para permitir referencias ausentes antes de cargar")
        conexion.execute(CONTROL_SQL)
        maestros = catalogos(conexion)
        previos = {r[0]: r[1:] for r in conexion.execute(
            "SELECT clave, registro_id, huella_fila, huella_grupo, paros_ids, fila_origen FROM control_carga_excel WHERE origen = %s", (origen,))}
        actuales = {g["clave"]: g for g in grupos}
        if previos.keys() - actuales.keys():
            raise ValueError("Faltan registros cargados anteriormente o cambió su fecha/máquina/referencia/operador/turno; se requiere revisar el origen antes de cargar")
        posiciones = defaultdict(set)
        for grupo in grupos:
            posiciones[grupo["huella_fila"]].add(grupo["clave"])
        for clave, (_, huella_fila, _, _, _) in previos.items():
            if actuales[clave]["huella_fila"] != huella_fila and posiciones[huella_fila] - {clave}:
                raise ValueError("Se reordenaron registros de la misma combinación; se necesita un ID estable en Excel")
        for grupo in grupos:
            anterior = previos.get(grupo["clave"])
            try:
                valores, paros = transformar(grupo, maestros, errores)
                huella_grupo = huella((valores, sorted(paros, key=huella)))
                if anterior and anterior[2] == huella_grupo:
                    if anterior[4] != grupo["fila"] or anterior[1] != grupo["huella_fila"]:
                        conexion.execute("UPDATE control_carga_excel SET fila_origen = %s, huella_fila = %s WHERE origen = %s AND clave = %s",
                                         (grupo["fila"], grupo["huella_fila"], origen, grupo["clave"]))
                    resumen["sin_cambios"] += 1
                    continue
                with conexion.transaction():
                    if anterior:
                        identificador = anterior[0]
                        asignaciones = sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(c)) for c in CAMPOS_PRODUCCION)
                        registro = conexion.execute(sql.SQL("UPDATE registros_produccion SET {} WHERE id = %s RETURNING id").format(asignaciones), (*valores, identificador)).fetchone()
                        if registro is None:
                            raise ValueError("El registro importado ya no existe")
                        conexion.execute("DELETE FROM detalle_paros_produccion WHERE registro_produccion_id = %s AND id = ANY(%s)", (identificador, anterior[3]))
                    else:
                        registro = conexion.execute(sql.SQL("INSERT INTO registros_produccion ({}) VALUES ({}) RETURNING id").format(
                            sql.SQL(", ").join(map(sql.Identifier, CAMPOS_PRODUCCION)),
                            sql.SQL(", ").join(sql.Placeholder() for _ in valores)), valores).fetchone()
                        identificador = registro[0]
                    ids_paros = []
                    for paro in paros:
                        ids_paros.append(conexion.execute(
                            "INSERT INTO detalle_paros_produccion (registro_produccion_id, codigo_paro, subcodigo, duracion_minutos, area_involucrada, personal_involucrado, observaciones) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                            (identificador, *paro)).fetchone()[0])
                    conexion.execute("""
                        INSERT INTO control_carga_excel (origen, clave, fila_origen, huella_fila, huella_grupo, registro_id, paros_ids)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (origen, clave) DO UPDATE SET fila_origen = EXCLUDED.fila_origen,
                            huella_fila = EXCLUDED.huella_fila, huella_grupo = EXCLUDED.huella_grupo,
                            paros_ids = EXCLUDED.paros_ids, actualizado = clock_timestamp()
                    """, (origen, grupo["clave"], grupo["fila"], grupo["huella_fila"], huella_grupo, identificador, ids_paros))
                resumen["actualizados" if anterior else "insertados"] += 1
                resumen["paros_escritos"] += len(paros)
            except (ValueError, ArithmeticError, psycopg.DataError, psycopg.IntegrityError) as error:
                motivo = error.diag.message_primary if isinstance(error, psycopg.Error) else str(error)
                incidencia(errores, BASE, grupo["fila"], motivo)
        if simular:
            raise psycopg.Rollback()
    return dict(resumen)


def guardar_errores(ruta, errores):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    with temporal.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=("nivel", "hoja", "fila", "motivo"))
        escritor.writeheader()
        escritor.writerows(errores)
    temporal.replace(ruta)


def main():
    parser = argparse.ArgumentParser(description="Carga incremental a PostgreSQL usando DATABASE_URL. Requiere los scripts 01 y 02.")
    parser.add_argument("--excel", type=Path, default=Path(__file__).with_name("SEGUIMIENTO TEMPERAS Y VINILOS Actividad.xlsm"))
    parser.add_argument("--origen", default="seguimiento_temperas_vinilos", help="Identificador fijo del libro; conservarlo entre ejecuciones")
    parser.add_argument("--errores", type=Path, default=Path(__file__).parent / "logs" / "carga_errores.csv")
    parser.add_argument("--simular", action="store_true", help="Valida la carga en PostgreSQL y revierte todos los cambios")
    args = parser.parse_args()
    errores = []
    try:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise ValueError("Defina DATABASE_URL con la conexión a PostgreSQL")
        grupos, contrastados = leer_excel(args.excel, errores)
        with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as conexion:
            resumen = cargar(conexion, grupos, args.origen, errores, args.simular)
        guardar_errores(args.errores, errores)
        resumen.update(simulacion=args.simular, paros_contrastados=contrastados,
                       errores=sum(e["nivel"] == "ERROR" for e in errores),
                       advertencias=sum(e["nivel"] == "ADVERTENCIA" for e in errores))
        print(json.dumps(resumen, ensure_ascii=False))
        return 1 if resumen["errores"] else 0
    except (OSError, ValueError, KeyError, BadZipFile, InvalidFileException, psycopg.Error) as error:
        motivo = "Error de conexión o ejecución de PostgreSQL; revise DATABASE_URL y los scripts 01 y 02" if isinstance(error, psycopg.Error) else str(error)
        incidencia(errores, "ARCHIVO", "", motivo)
        guardar_errores(args.errores, errores)
        print(motivo, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
