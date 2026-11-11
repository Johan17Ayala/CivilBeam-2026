"""
ejecutar_sin_interfaz.py
Demostración ejecutable del módulo de cálculo de ingeniería 100% independiente de la interfaz gráfica.
Puede importarse o ejecutarse directamente desde consola sin abrir Flet ni ventanas GUI.

Uso:
    python ejecutar_sin_interfaz.py

Universidad Distrital Francisco José de Caldas - Facultad Tecnológica
Programación II
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.modelo import analizar_viga_desde_diccionario
from app.reporte import generar_memoria_word


def ejecutar_ejemplo_headless() -> Path:
    """Ejecuta el análisis estructural y genera la memoria Word sin importar Flet."""
    config = {
        "longitud": 8.0,
        "tipo_viga": "empotrada_movil",
        "apoyos_detalle": [
            {"tipo": "empotrado", "x": 0.0, "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
            {"tipo": "movil", "x": 8.0, "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
        ],
        "E_GPa": 24.0,
        "sigma_adm": 180.0,
        "limite_k": 360,
        "incluir_peso_propio": True,
        "combinacion": "nsr_2",
        "accion_termica": {
            "delta_T_uniforme": 15.0,
            "delta_T_gradiente": 10.0,
            "retraccion_micro": 0.0,
            "fluencia_phi": 0.0,
        },
        "seccion": {
            "tipo": "rectangular",
            "parametros": {"base": 0.30, "altura": 0.60},
        },
        "cargas": [
            {"tipo": "distribuida", "w1": 18.0, "w2": 18.0, "x1": 0.0, "x2": 8.0, "origen": "D"},
            {"tipo": "puntual", "P": 35.0, "Px": 10.0, "x": 4.0, "origen": "L"},
        ],
    }

    viga, res = analizar_viga_desde_diccionario(config)

    assert "flet" not in sys.modules, "El módulo de ingeniería no debe depender de Flet."

    print("=" * 75)
    print("  CIVILBEAM 2026 - EJECUCIÓN DE CÁLCULO SIN INTERFAZ GRÁFICA")
    print("=" * 75)
    print(f"Longitud L: {res.L:.2f} m | Sección: {res.seccion.nombre}")
    print(f"Grado de hiperestaticidad: {res.grado_hiperestaticidad} | Combinación: {res.combinacion_usada}")
    for det in res.reacciones_detalle:
        print(f"  Apoyo {det['etiqueta']} ({det['tipo']} en x={det['x']:.2f}m): "
              f"Ry={det['Ry']:.2f} kN, Rx={det['Rx']:.2f} kN, M={det['M']:.2f} kN·m")
    print(f"|V| máx = {res.V_abs_max:.2f} kN en x = {res.x_V_max:.2f} m")
    print(f"|M| máx = {res.M_abs_max:.2f} kN·m en x = {res.x_M_max:.2f} m")
    print(f"|N| máx = {res.N_abs_max:.2f} kN")
    print(f"|δ| máx = {res.v_abs_max:.3f} mm (Límite L/{res.limite_k} = ±{res.deflexion_limite:.2f} mm)")
    print(f"σ máx   = {res.sigma_max:.2f} MPa (Admisible = {res.sigma_adm:.1f} MPa)")
    print(f"Dictamen Global: {'CUMPLE' if res.cumple_global else 'NO CUMPLE'}")

    ruta_word = generar_memoria_word(
        viga=viga,
        resultado=res,
        proyecto_nombre="Ejecución Autónoma Sin Interfaz",
        calculo_nombre="Viga Demostración Headless",
        autor="Módulo Independiente CivilBeam",
    )
    print(f"\nMemoria de cálculo Word generada automáticamente en:\n  {ruta_word}")
    return ruta_word


if __name__ == "__main__":
    ejecutar_ejemplo_headless()
