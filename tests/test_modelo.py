"""
test_modelo.py
Suite de pruebas unitarias automatizadas con pytest para el cálculo de vigas.
Valida el modelo analítico vectorizado (NumPy) y la integración numérica (SciPy)
frente a 5 soluciones canónicas exactas de la literatura de resistencia de materiales
(Beer & Johnston / Hibbeler).

Universidad Distrital Francisco José de Caldas - Facultad Tecnológica
Programación II
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile

from app.secciones import (
    crear_seccion_rectangular,
    crear_seccion_perfil_i,
    crear_seccion_bulb_tee
)
from app.modelo import VigaIsostatica, Apoyo, AccionTermicaReologica
from app.db import (
    inicializar_bd,
    guardar_calculo,
    listar_calculos,
    obtener_calculo_por_id,
    eliminar_calculo
)


# =========================================================================
# CASO 1: Viga Simplemente Apoyada con Carga Puntual Central
# Fórmulas canónicas:
#   R1 = R2 = P / 2
#   M_max = (P * L) / 4 en x = L / 2
#   delta_max = (P * L³) / (48 * E * I) en x = L / 2
# =========================================================================
def test_viga_simple_carga_puntual_central():
    L = 6.0         # [m]
    P = 24.0        # [kN]
    E_GPa = 200.0   # [GPa]
    b = 0.20        # [m]
    h = 0.40        # [m]

    seccion = crear_seccion_rectangular(base=b, altura=h)
    I_analitica = (b * (h ** 3)) / 12.0 # (1/12)*b*h³ = 0.001066667 m⁴

    assert np.isclose(seccion.inercia, I_analitica, rtol=1e-5)

    viga = VigaIsostatica(
        longitud=L,
        tipo="simplemente_apoyada",
        pos_apoyos=(0.0, L),
        seccion=seccion,
        E_GPa=E_GPa,
        incluir_peso_propio=False
    )
    viga.agregar_carga_puntual(P=P, x=L / 2.0)
    res = viga.resolver()

    # Reacciones teóricas
    assert np.isclose(res.reacciones["R1"], P / 2.0, rtol=1e-3)
    assert np.isclose(res.reacciones["R2"], P / 2.0, rtol=1e-3)

    # Momento máximo teórico = P*L/4 = 24*6/4 = 36 kN·m
    M_teorico = (P * L) / 4.0
    assert np.isclose(res.M_abs_max, M_teorico, rtol=1e-3)
    assert np.isclose(res.x_M_max, L / 2.0, atol=1e-2)

    # Deflexión máxima teórica = (P * L³) / (48 * E * I)
    # P en N (24000 N), E en Pa (200e9 Pa), I en m⁴ -> delta en m (*1000 a mm)
    delta_teorica_m = (P * 1000.0 * (L ** 3)) / (48.0 * (E_GPa * 1e9) * seccion.inercia)
    delta_teorica_mm = delta_teorica_m * 1000.0

    # Error relativo de SciPy cumulative_trapezoid con respecto a la fórmula cerrada
    assert np.isclose(res.v_abs_max, delta_teorica_mm, rtol=5e-3)


# =========================================================================
# CASO 2: Viga Simplemente Apoyada con Carga Distribuida Uniforme
# Fórmulas canónicas:
#   R1 = R2 = (w * L) / 2
#   M_max = (w * L²) / 8 en x = L / 2
#   delta_max = (5 * w * L⁴) / (384 * E * I) en x = L / 2
# =========================================================================
def test_viga_simple_carga_distribuida_uniforme():
    L = 8.0         # [m]
    w = 15.0        # [kN/m]
    E_GPa = 25.0    # [GPa]
    b = 0.30        # [m]
    h = 0.50        # [m]

    seccion = crear_seccion_rectangular(base=b, altura=h)
    viga = VigaIsostatica(
        longitud=L,
        tipo="simplemente_apoyada",
        pos_apoyos=(0.0, L),
        seccion=seccion,
        E_GPa=E_GPa,
        incluir_peso_propio=False
    )
    viga.agregar_carga_distribuida(w1=w, w2=w, x1=0.0, x2=L)
    res = viga.resolver()

    # Reacciones: w*L/2 = 15*8/2 = 60 kN
    assert np.isclose(res.reacciones["R1"], (w * L) / 2.0, rtol=1e-3)
    assert np.isclose(res.reacciones["R2"], (w * L) / 2.0, rtol=1e-3)

    # Momento teórico: w*L²/8 = 15*64/8 = 120 kN·m
    M_teorico = (w * (L ** 2)) / 8.0
    assert np.isclose(res.M_abs_max, M_teorico, rtol=1e-3)

    # Deflexión teórica: 5*w*L⁴ / (384*E*I)
    w_N_m = w * 1000.0
    E_Pa = E_GPa * 1e9
    delta_teorica_mm = ((5.0 * w_N_m * (L ** 4)) / (384.0 * E_Pa * seccion.inercia)) * 1000.0

    assert np.isclose(res.v_abs_max, delta_teorica_mm, rtol=2e-3)


# =========================================================================
# CASO 3: Viga en Voladizo con Carga Puntual en el Extremo Libre
# Fórmulas canónicas:
#   R_v = P
#   M_empotramiento = P * L
#   delta_extremo = (P * L³) / (3 * E * I) en x = L
# =========================================================================
def test_viga_voladizo_carga_extremo():
    L = 3.0         # [m]
    P = 10.0        # [kN]
    E_GPa = 200.0   # [GPa]
    bf = 0.20
    d = 0.30
    tf = 0.015
    tw = 0.010

    seccion = crear_seccion_perfil_i(bf=bf, d=d, tf=tf, tw=tw)
    viga = VigaIsostatica(
        longitud=L,
        tipo="voladizo",
        seccion=seccion,
        E_GPa=E_GPa,
        incluir_peso_propio=False
    )
    viga.agregar_carga_puntual(P=P, x=L)
    res = viga.resolver()

    # Reacciones en empotramiento x = 0
    assert np.isclose(res.reacciones["R_vertical"], P, rtol=1e-3)
    assert np.isclose(res.reacciones["M_empotramiento"], P * L, rtol=1e-3)

    # Momento máximo en x = 0
    assert np.isclose(res.M_abs_max, P * L, rtol=1e-3)

    # Deflexión teórica en el extremo x = L: P*L³ / (3*E*I)
    P_N = P * 1000.0
    E_Pa = E_GPa * 1e9
    delta_teorica_mm = ((P_N * (L ** 3)) / (3.0 * E_Pa * seccion.inercia)) * 1000.0

    assert np.isclose(res.v_abs_max, delta_teorica_mm, rtol=2e-3)


# =========================================================================
# CASO 4: Sección PerfilI analítica vs pysections
# =========================================================================
def test_geometria_perfil_i():
    bf = 0.20
    d = 0.40
    tf = 0.02
    tw = 0.01

    # Cálculo analítico elemental
    # Área = 2*(bf*tf) + (d - 2*tf)*tw
    area_analitica = 2.0 * (bf * tf) + (d - 2.0 * tf) * tw
    # Inercia respecto al eje neutro baricéntrico horizontal
    # I = (1/12)*bf*d³ - (1/12)*(bf - tw)*(d - 2*tf)³
    I_analitica = (1.0 / 12.0) * bf * (d ** 3) - (1.0 / 12.0) * (bf - tw) * ((d - 2.0 * tf) ** 3)

    perfil = crear_seccion_perfil_i(bf=bf, d=d, tf=tf, tw=tw)

    assert np.isclose(perfil.area, area_analitica, rtol=1e-6)
    assert np.isclose(perfil.inercia, I_analitica, rtol=1e-6)


# =========================================================================
# CASO 5: Operaciones CRUD en Base de Datos SQLite
# =========================================================================
def test_crud_sqlite(tmp_path):
    test_db = str(tmp_path / "test_vigas.db")
    inicializar_bd(test_db)

    # 1. Guardar
    datos_ent = {"L": 5.0, "cargas": []}
    resumen = {"M_abs_max": 45.0, "v_abs_max": 2.5}
    cid = guardar_calculo(
        proyecto_nombre="Proyecto Test",
        calculo_nombre="Viga Test 1",
        tipo_viga="simplemente_apoyada",
        longitud=5.0,
        datos_entrada=datos_ent,
        resumen_resultados=resumen,
        cumple_global=True,
        db_path=test_db
    )
    assert cid > 0

    # 2. Listar
    lista = listar_calculos(db_path=test_db)
    assert len(lista) == 1
    assert lista[0]["nombre"] == "Viga Test 1"
    assert lista[0]["proyecto_nombre"] == "Proyecto Test"

    # 3. Obtener por ID
    calc = obtener_calculo_por_id(cid, db_path=test_db)
    assert calc is not None
    assert calc["datos_entrada"]["L"] == 5.0

    # 4. Eliminar
    ok = eliminar_calculo(cid, db_path=test_db)
    assert ok is True
    assert len(listar_calculos(db_path=test_db)) == 0


# =========================================================================
# CASO 6: Viga Doblemente Empotrada (Hiperestática) con Carga Uniforme
#   M_emp = w * L² / 12, delta_max = w * L⁴ / (384 * E * I)
# =========================================================================
def test_doble_empotramiento_uniforme():
    L = 6.0
    w = 20.0
    E_GPa = 25.0
    seccion = crear_seccion_rectangular(0.30, 0.50)

    viga = VigaIsostatica(
        longitud=L, tipo="doble_empotrada", seccion=seccion, E_GPa=E_GPa, incluir_peso_propio=False
    )
    viga.agregar_carga_distribuida(w1=w, w2=w, x1=0.0, x2=L, origen="D")
    res = viga.resolver()

    assert res.grado_hiperestaticidad == 2
    assert np.isclose(res.reacciones_detalle[0]["Ry"], w * L / 2.0, rtol=1e-3)
    assert np.isclose(res.reacciones_detalle[1]["Ry"], w * L / 2.0, rtol=1e-3)
    M_emp_teorico = (w * (L ** 2)) / 12.0
    assert np.isclose(abs(res.reacciones_detalle[0]["M"]), M_emp_teorico, rtol=1e-3)

    delta_teorica_mm = (((w * 1000.0) * (L ** 4)) / (384.0 * (E_GPa * 1e9) * seccion.inercia)) * 1000.0
    assert np.isclose(res.v_abs_max, delta_teorica_mm, rtol=1e-3)


# =========================================================================
# CASO 7: Empotramiento Guiado + Fijo con Carga Horizontal y Vertical
# =========================================================================
def test_guiado_y_carga_horizontal():
    L = 5.0
    w = 12.0
    Px = 30.0
    seccion = crear_seccion_rectangular(0.25, 0.40)

    viga = VigaIsostatica(
        longitud=L,
        tipo="personalizado",
        apoyos=[
            Apoyo(x=0.0, tipo="guiado", etiqueta="A1"),  # Impide v y theta, permite u
            Apoyo(x=L, tipo="fijo", etiqueta="A2"),      # Impide u y v
        ],
        seccion=seccion, E_GPa=200.0, incluir_peso_propio=False
    )
    viga.agregar_carga_distribuida(w1=w, w2=w, x1=0.0, x2=L)
    viga.agregar_carga_puntual(P=0.0, x=2.5, Px=Px)
    res = viga.resolver()

    # Empotramiento guiado+fijo bajo w = equiv. empotrado+rodillo: R1=5/8*wL, R2=3/8*wL, M1=wL^2/8
    assert np.isclose(res.reacciones_detalle[0]["Ry"], (5.0 / 8.0) * w * L, rtol=1e-3)
    assert np.isclose(res.reacciones_detalle[1]["Ry"], (3.0 / 8.0) * w * L, rtol=1e-3)
    assert np.isclose(abs(res.reacciones_detalle[0]["M"]), (w * L**2) / 8.0, rtol=1e-3)
    # Solo A2 (Fijo) toma la reacción axial Rx = -Px; A1 (Guiado) desliza con Rx = 0
    assert np.isclose(res.reacciones_detalle[0]["Rx"], 0.0, atol=1e-6)
    assert np.isclose(res.reacciones_detalle[1]["Rx"], -Px, rtol=1e-4)


# =========================================================================
# CASO 8: Apoyo Elástico (Resorte ky) + Carga Polinómica + Combinación NSR-10
# =========================================================================
def test_apoyo_elastico_y_polinomica():
    L = 4.0
    ky = 2000.0  # kN/m
    seccion = crear_seccion_rectangular(0.30, 0.50)

    # Pin en x=0, resorte en x=L, carga puntual P=40 kN en x=L -> R_resorte = P, delta_L = -P/ky
    viga = VigaIsostatica(
        longitud=L,
        tipo="personalizado",
        apoyos=[Apoyo(x=0.0, tipo="fijo"), Apoyo(x=L, tipo="elastico", ky=ky)],
        seccion=seccion, E_GPa=24.0, incluir_peso_propio=False
    )
    viga.agregar_carga_puntual(P=40.0, x=L)
    res = viga.resolver()
    assert np.isclose(res.reacciones_detalle[1]["Ry"], 40.0, rtol=1e-3)
    assert np.isclose(res.v_abs_max, (40.0 / ky) * 1000.0, rtol=1e-3)

    # Voladizo con carga parabólica w(x) = q0*(x/L)^2 -> R_v = q0*L/3, M_emp = q0*L^2/4
    q0 = 27.0
    v_poly = VigaIsostatica(longitud=L, tipo="voladizo", seccion=seccion, E_GPa=24.0, combinacion="nsr_2")
    v_poly.agregar_carga_polinomica(a0=0.0, a1=0.0, a2=q0 / (L**2), a3=0.0, x1=0.0, x2=L, origen="L")
    res_p = v_poly.resolver()
    # Combinación nsr_2 multiplica L por 1.6
    assert np.isclose(res_p.reacciones_detalle[0]["Ry"], 1.6 * (q0 * L / 3.0), rtol=1e-3)
    assert np.isclose(res_p.reacciones_detalle[0]["M"], 1.6 * (q0 * (L**2) / 4.0), rtol=1e-3)


# =========================================================================
# CASO 9: Acciones Térmicas (ΔT₀ y Gradiente) y Fluencia Lenta (φ)
# =========================================================================
def test_termica_y_fluencia():
    L = 5.0
    E_GPa = 30.0
    b, h = 0.30, 0.50
    sec = crear_seccion_rectangular(b, h)

    # Viga doblemente empotrada con Delta T uniforme = +30°C y gradiente = +20°C
    dT0 = 30.0
    dTg = 20.0
    alpha = 1.2e-5
    viga = VigaIsostatica(
        longitud=L, tipo="doble_empotrada", seccion=sec, E_GPa=E_GPa,
        accion_termica=AccionTermicaReologica(delta_T_uniforme=dT0, delta_T_gradiente=dTg, alpha_T=alpha)
    )
    res = viga.resolver()

    EA_kN = (E_GPa * 1e6) * sec.area
    EI_kNm2 = (E_GPa * 1e6) * sec.inercia
    N_teorico = EA_kN * alpha * dT0
    M_teorico = EI_kNm2 * (alpha * dTg / h)
    assert np.isclose(res.N_abs_max, N_teorico, rtol=1e-4)
    assert np.isclose(res.M_abs_max, M_teorico, rtol=1e-4)

    # Verificar fluencia lenta phi = 1.0 -> deflexión exactamente 2x que phi = 0.0
    v1 = VigaIsostatica(longitud=L, tipo="simplemente_apoyada", seccion=sec, E_GPa=E_GPa)
    v1.agregar_carga_puntual(P=50.0, x=L / 2.0)
    v2 = VigaIsostatica(
        longitud=L, tipo="simplemente_apoyada", seccion=sec, E_GPa=E_GPa,
        accion_termica=AccionTermicaReologica(fluencia_phi=1.0)
    )
    v2.agregar_carga_puntual(P=50.0, x=L / 2.0)
    assert np.isclose(v2.resolver().v_abs_max, 2.0 * v1.resolver().v_abs_max, rtol=1e-4)


# =========================================================================
# CASO 10: Independencia Total de la Interfaz (Sin Flet) y Memoria Word
# =========================================================================
def test_modulo_independiente_sin_flet_y_word(tmp_path):
    import sys
    from app.modelo import analizar_viga_desde_diccionario
    from app.reporte import generar_memoria_word

    config = {
        "longitud": 6.0,
        "tipo_viga": "simplemente_apoyada",
        "apoyos_detalle": [
            {"tipo": "fijo", "x": 0.0},
            {"tipo": "movil", "x": 6.0},
        ],
        "E_GPa": 24.0,
        "sigma_adm": 180.0,
        "limite_k": 360,
        "incluir_peso_propio": True,
        "seccion": {"tipo": "rectangular", "parametros": {"base": 0.30, "altura": 0.50}},
        "cargas": [{"tipo": "puntual", "P": 30.0, "x": 3.0, "origen": "L"}],
    }
    viga, res = analizar_viga_desde_diccionario(config)
    assert res.reacciones_detalle[0]["Ry"] > 0

    # Verificar en un proceso Python limpio (sin plugin de pytest) que no se importa flet
    import subprocess, sys
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys; from app.modelo import analizar_viga_desde_diccionario; "
         "assert 'flet' not in sys.modules"],
        check=True
    )
    assert proc.returncode == 0

    salida = generar_memoria_word(viga, res, ruta_salida=tmp_path / "memoria_auto.docx")
    assert salida.exists() and salida.stat().st_size > 10000


# =========================================================================
# CASO 11: Cálculo Paso a Paso Detallado y Exportación a Word
# =========================================================================
def test_paso_a_paso_y_exportacion_word(tmp_path):
    import subprocess, sys
    from app.modelo import analizar_viga_desde_diccionario
    from app.paso_a_paso import generar_pasos_calculo, generar_word_paso_a_paso

    config = {
        "longitud": 8.0,
        "tipo_viga": "simplemente_apoyada",
        "apoyos_detalle": [
            {"tipo": "fijo", "x": 0.0},
            {"tipo": "movil", "x": 8.0},
        ],
        "E_GPa": 25.0,
        "sigma_adm": 200.0,
        "limite_k": 360,
        "incluir_peso_propio": True,
        "seccion": {"tipo": "rectangular", "parametros": {"base": 0.35, "altura": 0.60}},
        "cargas": [
            {"tipo": "distribuida_uniforme", "w": 15.0, "x_inicio": 0.0, "x_fin": 8.0, "origen": "D"},
            {"tipo": "puntual", "P": 40.0, "x": 4.0, "origen": "L"},
        ],
    }
    viga, res = analizar_viga_desde_diccionario(config)
    pasos = generar_pasos_calculo(viga, res)
    assert len(pasos) == 6
    assert all(
        "numero" in p and "titulo" in p and "ecuaciones" in p and "desarrollo" in p and "resultado_clave" in p
        for p in pasos
    )
    assert all(len(p["ecuaciones"]) > 0 and len(p["desarrollo"]) > 0 for p in pasos)

    # Verificar independencia de Flet en subproceso limpio
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys; from app.paso_a_paso import generar_pasos_calculo, generar_word_paso_a_paso; "
         "assert 'flet' not in sys.modules"],
        check=True
    )
    assert proc.returncode == 0

    salida = generar_word_paso_a_paso(
        viga,
        res,
        proyecto_nombre="Proyecto Prueba",
        calculo_nombre="Viga Paso a Paso",
        autor="Ingeniero Test",
        ruta_salida=tmp_path / "paso_a_paso.docx",
    )
    assert salida.exists() and salida.stat().st_size > 10000
