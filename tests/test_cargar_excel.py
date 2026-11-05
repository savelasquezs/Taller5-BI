import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from openpyxl import Workbook
from openpyxl import load_workbook
from openpyxl.worksheet.table import Table
from psycopg import sql

from cargar_excel import BASE, SUBCODIGOS, cargar, leer_excel


@pytest.fixture
def conexion():
    dsn = os.environ.get("ETL_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Se requiere ETL_TEST_DATABASE_URL para una base de pruebas")
    esquema = "test_etl_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(esquema)))
        conn.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(esquema)))
        try:
            raiz = Path(__file__).resolve().parents[1]
            conn.execute((raiz / "01_esquema_produccion.sql").read_text(encoding="utf-8"))
            conn.execute((raiz / "02_catalogos.sql").read_text(encoding="utf-8"))
            conn.execute("INSERT INTO operadores(nombre) VALUES ('Diana') ON CONFLICT DO NOTHING")
            yield conn
        finally:
            conn.execute("SET search_path TO public")
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(esquema)))


def produccion(pacas=10, minutos=20):
    fila = [None] * 58
    for columna, valor in {
        0: datetime(2025, 3, 28), 3: "Vinilos_3", 4: "Diana",
        5: "Pintorcitos 22cc (6 col)", 9: pacas, 10: 8,
        11: "6am-2pm (Turno 1)", 25: minutos,
        26: "5.8 Banda de sujeción y roscadores",
    }.items():
        fila[columna] = valor
    return fila


def detalle(minutos=15):
    fila = produccion(minutos=minutos)
    fila[9] = fila[10] = None
    return fila


def archivo(tmp_path, filas, copia=False):
    ruta = tmp_path / "fuente.xlsx"
    libro = Workbook()
    hoja = libro.active
    hoja.title = BASE
    for c, nombre in {1: "Fecha", 4: "Maquina", 10: "Pacas producidas", 11: "Horas trabajadas", 26: "Codigo de paro 5"}.items():
        hoja.cell(9, c, nombre)
    for indice, fila in enumerate(filas, 10):
        for columna, valor in enumerate(fila, 1):
            if valor is not None:
                hoja.cell(indice, columna, valor)
    if copia:
        secundaria = libro.create_sheet(SUBCODIGOS)
        secundaria.cell(8, 1, "Fecha")
        secundaria.cell(8, 15, "Codigo de paro 5")
        for columna, valor in {1: filas[1][0], 4: filas[1][3], 5: filas[1][4], 6: filas[1][5], 8: filas[1][11], 15: filas[1][25], 16: filas[1][26]}.items():
            secundaria.cell(9, columna, valor)
    libro.save(ruta)
    return ruta


def ejecutar(conexion, ruta, simular=False):
    errores = []
    grupos, contrastados = leer_excel(ruta, errores)
    resumen = cargar(conexion, grupos, "prueba", errores, simular)
    return grupos, resumen, errores, contrastados


def test_detalles_y_copia_historica_no_duplican_produccion(tmp_path, conexion):
    ruta = archivo(tmp_path, [produccion(), detalle()], copia=True)
    grupos, resumen, errores, contrastados = ejecutar(conexion, ruta)
    assert not errores
    assert len(grupos) == 1 and contrastados == 1
    assert resumen["insertados"] == 1
    assert conexion.execute("SELECT count(*), sum(duracion_minutos) FROM detalle_paros_produccion").fetchone() == (2, Decimal(35))
    auditoria = conexion.execute("SELECT count(*) FROM auditoria_cambios").fetchone()[0]
    assert ejecutar(conexion, ruta)[1] == {"sin_cambios": 1}
    assert conexion.execute("SELECT count(*) FROM auditoria_cambios").fetchone()[0] == auditoria


def test_insercion_al_principio_y_correccion_de_cantidades(tmp_path, conexion):
    ejecutar(conexion, archivo(tmp_path, [produccion(10)]))
    ejecutar(conexion, archivo(tmp_path, [produccion(30), produccion(10)]))
    assert conexion.execute("SELECT count(*) FROM registros_produccion").fetchone()[0] == 2
    conexion.execute("UPDATE registros_produccion SET unidades_producidas=10, unidades_buenas=9")
    manual = conexion.execute("INSERT INTO detalle_paros_produccion (registro_produccion_id,codigo_paro,duracion_minutos) SELECT min(id),2,5 FROM registros_produccion RETURNING id").fetchone()[0]
    _, resumen, errores, _ = ejecutar(conexion, archivo(tmp_path, [produccion(31), produccion(10)]))
    assert not errores and resumen["actualizados"] == 1 and resumen["sin_cambios"] == 1
    assert conexion.execute("SELECT sum(pacas_producidas), sum(unidades_buenas) FROM registros_produccion").fetchone() == (Decimal(41), 18)
    assert conexion.execute("SELECT count(*) FROM detalle_paros_produccion WHERE id=%s", (manual,)).fetchone()[0] == 1


def test_reordenamiento_ambiguo_y_eliminacion_se_rechazan(tmp_path, conexion):
    ejecutar(conexion, archivo(tmp_path, [produccion(20), produccion(10)]))
    with pytest.raises(ValueError, match="reordenaron"):
        ejecutar(conexion, archivo(tmp_path, [produccion(10), produccion(20)]))
    with pytest.raises(ValueError, match="Faltan registros"):
        ejecutar(conexion, archivo(tmp_path, [produccion(20)]))
    assert conexion.execute("SELECT count(*) FROM registros_produccion").fetchone()[0] == 2


def test_paros_huerfanos_no_crean_produccion(tmp_path, conexion):
    grupos, resumen, errores, _ = ejecutar(conexion, archivo(tmp_path, [detalle()]))
    assert not grupos and resumen == {}
    assert len(errores) == 1 and "inequívoca" in errores[0]["motivo"]
    assert conexion.execute("SELECT count(*) FROM registros_produccion").fetchone()[0] == 0


def test_simulacion_no_guarda_datos_ni_control(tmp_path, conexion):
    _, resumen, errores, _ = ejecutar(conexion, archivo(tmp_path, [produccion()]), simular=True)
    assert not errores and resumen["insertados"] == 1
    assert conexion.execute("SELECT count(*) FROM registros_produccion").fetchone()[0] == 0
    assert conexion.execute("SELECT to_regclass(quote_ident(current_schema()) || '.control_carga_excel')").fetchone()[0] is None


def test_subcodigo_desconocido_preserva_tiempo_y_texto(tmp_path, conexion):
    fila = produccion()
    fila[26] = "4.4 Clasificación anterior"
    _, _, errores, _ = ejecutar(conexion, archivo(tmp_path, [fila]))
    subcodigo, minutos, observaciones = conexion.execute("SELECT subcodigo,duracion_minutos,observaciones FROM detalle_paros_produccion").fetchone()
    assert subcodigo is None and minutos == 20 and "4.4" in observaciones
    assert errores[0]["nivel"] == "ADVERTENCIA"


def test_error_de_bd_revierte_registro_completo_y_permite_siguiente(tmp_path, conexion):
    mala = produccion()
    mala[9] = Decimal("1000000000")
    buena = produccion(15)
    _, resumen, errores, _ = ejecutar(conexion, archivo(tmp_path, [mala, buena]))
    assert resumen["insertados"] == 1
    assert sum(e["nivel"] == "ERROR" for e in errores) == 1
    assert conexion.execute("SELECT pacas_producidas FROM registros_produccion").fetchall() == [(Decimal(15),)]
    assert conexion.execute("SELECT count(*) FROM control_carga_excel").fetchone()[0] == 1


def test_precision_de_excel_no_rechaza_minutos_validos(tmp_path, conexion):
    fila = produccion(minutos=219.60000000000002)
    _, resumen, errores, _ = ejecutar(conexion, archivo(tmp_path, [fila]))
    assert not errores and resumen["insertados"] == 1
    assert conexion.execute("SELECT duracion_minutos FROM detalle_paros_produccion").fetchone()[0] == Decimal("219.60")


def test_detalle_con_varios_padres_posibles_no_se_asigna(tmp_path, conexion):
    otra = produccion(30)
    otra[3] = "Vinilos_2"
    _, _, errores, _ = ejecutar(conexion, archivo(tmp_path, [produccion(10), produccion(20), otra, detalle()]))
    assert len(errores) == 1 and "inequívoca" in errores[0]["motivo"]
    assert conexion.execute("SELECT count(*),sum(duracion_minutos) FROM detalle_paros_produccion").fetchone() == (3, Decimal(60))


@pytest.mark.parametrize("referencia", [None, "No aplica"])
def test_referencia_ausente_conserva_produccion_sin_inventar_oee(tmp_path, conexion, referencia):
    fila = produccion()
    fila[5] = referencia
    ruta = archivo(tmp_path, [fila])
    _, resumen, errores, _ = ejecutar(conexion, ruta)
    assert resumen["insertados"] == 1
    registro = conexion.execute("SELECT referencia_id,pacas_producidas,horas_trabajadas,unidades_buenas,tiempo_planificado_minutos,observaciones FROM registros_produccion").fetchone()
    assert registro[:5] == (None, Decimal(10), Decimal(8), None, None)
    assert (referencia or "<vacía>") in registro[5]
    assert errores[0]["nivel"] == "ADVERTENCIA" and "R01" in errores[0]["motivo"]
    assert ejecutar(conexion, ruta)[1] == {"sin_cambios": 1}


def test_operador_no_solo_se_normaliza_en_periodos_sin_programacion(tmp_path, conexion):
    inactiva = produccion(0)
    inactiva[4], inactiva[10], inactiva[14] = "No", 0, "No se programo por demanda"
    activa = produccion(10)
    activa[4] = "No"
    _, resumen, errores, _ = ejecutar(conexion, archivo(tmp_path, [activa, inactiva]))
    assert resumen["insertados"] == 1
    operador, observaciones = conexion.execute("SELECT operador_id,observaciones FROM registros_produccion").fetchone()
    assert operador is None and "operador original: No" in observaciones
    assert sum(e["nivel"] == "ERROR" for e in errores) == 1


@pytest.mark.parametrize("campo", [4, 11])
def test_enlace_unico_por_campos_disponibles_conserva_criterio(tmp_path, conexion, campo):
    adicional = detalle()
    adicional[campo] = None
    _, resumen, errores, _ = ejecutar(conexion, archivo(tmp_path, [produccion(), adicional]))
    assert resumen["insertados"] == 1
    assert conexion.execute("SELECT count(*),sum(duracion_minutos) FROM detalle_paros_produccion").fetchone() == (2, Decimal(35))
    assert conexion.execute("SELECT count(*) FROM detalle_paros_produccion WHERE observaciones LIKE '%ETL R03%'").fetchone()[0] == 1
    assert errores[0]["nivel"] == "ADVERTENCIA" and "R03" in errores[0]["motivo"]


def test_campos_incompletos_no_se_rellenan_con_cero(tmp_path, conexion):
    fila = produccion()
    fila[9] = None
    _, resumen, errores, _ = ejecutar(conexion, archivo(tmp_path, [fila]))
    assert resumen == {} and "Producción incompleta" in errores[0]["motivo"]
    assert conexion.execute("SELECT count(*) FROM registros_produccion").fetchone()[0] == 0


def test_nombre_literal_stilo_no_se_fusiona_con_estilo(tmp_path, conexion):
    fila = produccion()
    fila[5] = "Stilo Kids 22cc (6 col)"
    _, resumen, errores, _ = ejecutar(conexion, archivo(tmp_path, [fila]))
    assert not errores and resumen["insertados"] == 1
    assert conexion.execute("SELECT r.nombre FROM registros_produccion p JOIN referencias r ON r.id=p.referencia_id").fetchone()[0] == fila[5]
    assert conexion.execute("SELECT count(*) FROM referencias WHERE nombre IN ('Stilo Kids 22cc (6 col)','Estilo Kids 22cc (6 col)')").fetchone()[0] == 2


def test_nuevas_reglas_no_asocian_detalles_con_dos_candidatos(tmp_path, conexion):
    adicional = detalle()
    adicional[4] = None
    _, resumen, errores, _ = ejecutar(conexion, archivo(tmp_path, [produccion(10), produccion(20), adicional]))
    assert resumen["insertados"] == 2
    assert len(errores) == 1 and "inequívoca" in errores[0]["motivo"]
    assert conexion.execute("SELECT count(*) FROM detalle_paros_produccion").fetchone()[0] == 2


def test_migracion_actualiza_esquema_anterior_y_puede_repetirse(tmp_path, conexion):
    conexion.execute("ALTER TABLE registros_produccion ALTER COLUMN referencia_id SET NOT NULL")
    fila = produccion()
    fila[5] = None
    ruta = archivo(tmp_path, [fila])
    with pytest.raises(ValueError, match="04_ajustes_calidad_etl"):
        ejecutar(conexion, ruta)
    migracion = (Path(__file__).resolve().parents[1] / "04_ajustes_calidad_etl.sql").read_text(encoding="utf-8")
    conexion.execute(migracion)
    conexion.execute(migracion)
    assert ejecutar(conexion, ruta)[1]["insertados"] == 1
    assert conexion.execute("SELECT count(*) FROM referencias WHERE nombre='Stilo Kids 22cc (6 col)'").fetchone()[0] == 1


def agregar_parametros(ruta, filas):
    libro = load_workbook(ruta)
    hoja = libro.create_sheet("Tablas Desplegables")
    cabecera = ["maquina", "Nombre de referencia", "# colores", "Pacas", "Display", "Unidades * paca",
                "unidades *minuto", "horas", "minutos", "ideal", "pacas ideales"]
    for i, fila in enumerate([cabecera, *filas], 1):
        for j, valor in enumerate(fila, 3):
            hoja.cell(i, j, valor)
    hoja.add_table(Table(displayName="Tabla15", ref=f"C1:M{len(filas) + 1}"))
    libro.save(ruta)


def test_catalogo_completa_empaque_y_velocidad_sin_inventar_calidad(tmp_path, conexion):
    ruta = archivo(tmp_path, [produccion()])
    agregar_parametros(ruta, [["Vinilos_3", "Pintorcitos 22cc (6 col)", 6, 1, 100, 600, 80]])
    _, resumen, errores, _ = ejecutar(conexion, ruta)
    assert not errores and resumen["insertados"] == 1
    fila = conexion.execute("SELECT unidades_por_display,displays_por_paca,unidades_ideales_por_minuto,"
                            "unidades_producidas,unidades_buenas,tiempo_planificado_minutos,observaciones FROM registros_produccion").fetchone()
    assert fila[:6] == (6, 100, Decimal(80), None, None, None)
    assert "ETL R08" in fila[6] and "E2:I2" in fila[6]
    assert ejecutar(conexion, ruta)[1] == {"sin_cambios": 1}


def test_parametros_ambiguos_no_se_eligen_por_primera_coincidencia(tmp_path, conexion):
    ruta = archivo(tmp_path, [produccion()])
    agregar_parametros(ruta, [["Vinilos_3", "Pintorcitos 22cc (6 col)", 6, 1, 100, 600, 80],
                            ["Vinilos_3", "Pintorcitos 22cc (6 col)", 6, 1, 50, 300, 80]])
    _, _, errores, _ = ejecutar(conexion, ruta)
    assert any("contradictorios" in e["motivo"] for e in errores)
    assert conexion.execute("SELECT unidades_por_display,displays_por_paca,unidades_ideales_por_minuto FROM registros_produccion").fetchone() == (None, None, None)


def test_parametros_de_fila_prevalecen_sobre_catalogo(tmp_path, conexion):
    fila = produccion()
    fila[6], fila[7], fila[8] = 90, 6, 50
    ruta = archivo(tmp_path, [fila])
    agregar_parametros(ruta, [["Vinilos_3", "Pintorcitos 22cc (6 col)", 6, 1, 100, 600, 80]])
    ejecutar(conexion, ruta)
    assert conexion.execute("SELECT unidades_por_display,displays_por_paca,unidades_ideales_por_minuto FROM registros_produccion").fetchone() == (6, 50, Decimal(90))
