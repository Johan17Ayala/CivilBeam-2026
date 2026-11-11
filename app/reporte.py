"""
reporte.py
Generador automático de memorias de cálculo en formato Word (.docx) utilizando docxtpl.
Soporta todos los tipos de apoyo, cargas geométricas, orígenes (D, L, W, E, S, T),
combinaciones NSR-10 y acciones térmicas/reológicas.

Universidad Distrital Francisco José de Caldas - Facultad Tecnológica
Programación II
"""

import io
from pathlib import Path
from datetime import datetime
from typing import Optional
import numpy as np

from docxtpl import DocxTemplate, InlineImage
from docx.shared import Inches

from app.modelo import (
    VigaIsostatica,
    ResultadoViga,
    TIPOS_APOYO,
    COMBINACIONES_CARGA,
)
from app.graficas import generar_figura_analisis_completo, figura_a_bytes

RUTA_APP = Path(__file__).resolve().parent
RUTA_PROYECTO = RUTA_APP.parent
RUTA_PLANTILLA = RUTA_PROYECTO / "plantillas" / "memoria.docx"
RUTA_REPORTES = RUTA_PROYECTO / "reportes"


def generar_memoria_word(
    viga: VigaIsostatica,
    resultado: ResultadoViga,
    proyecto_nombre: str = "Proyecto General",
    calculo_nombre: str = "Viga de Análisis",
    autor: str = "Ingeniero Calculista",
    ruta_salida: Optional[Path] = None,
    ruta_plantilla: Optional[Path] = None
) -> Path:
    """
    Genera un archivo .docx completo y profesional con la memoria de cálculo.
    """
    if ruta_plantilla is None:
        ruta_plantilla = RUTA_PLANTILLA

    if not ruta_plantilla.exists():
        raise FileNotFoundError(f"No se encontró la plantilla en: {ruta_plantilla}")

    doc = DocxTemplate(str(ruta_plantilla))

    # 1. Imagen técnica Matplotlib
    fig = generar_figura_analisis_completo(viga, resultado)
    img_bytes = figura_a_bytes(fig, formato="png")
    img_stream = io.BytesIO(img_bytes)
    img_word = InlineImage(doc, img_stream, width=Inches(6.4))

    # 2. Descripción detallada de apoyos
    apoyos_lineas = []
    for ap in viga.apoyos:
        nom = TIPOS_APOYO.get(ap.tipo, ap.tipo)
        if ap.tipo == "elastico":
            apoyos_lineas.append(f"{ap.etiqueta}: {nom} en x={ap.x:.2f} m (ky={ap.ky:.1f} kN/m, kθ={ap.ktheta:.1f} kN·m/rad)")
        else:
            apoyos_lineas.append(f"{ap.etiqueta}: {nom} en x={ap.x:.2f} m")
    apoyos_txt = "; ".join(apoyos_lineas)

    # 3. Descripción de cargas + combinación + acciones térmicas/reológicas
    comb_nombre = COMBINACIONES_CARGA.get(resultado.combinacion_usada, {}).get("nombre", resultado.combinacion_usada)
    cargas_lineas = [f"  • Combinación activa: {comb_nombre}"]
    if viga.cargas_puntuales:
        for i, cp in enumerate(viga.cargas_puntuales, 1):
            extra_x = f", Px = {cp.Px:.2f} kN" if abs(cp.Px) > 1e-6 else ""
            cargas_lineas.append(f"  • Puntual P{i} [{cp.origen}]: P = {cp.P:.2f} kN{extra_x} en x = {cp.x:.2f} m")
    if viga.cargas_distribuidas:
        for i, cd in enumerate(viga.cargas_distribuidas, 1):
            cargas_lineas.append(
                f"  • Distribuida w{i} [{cd.origen}]: de {cd.w1:.2f} a {cd.w2:.2f} kN/m en [{cd.x1:.2f}, {cd.x2:.2f}] m"
            )
    if viga.cargas_polinomicas:
        for i, cp_poly in enumerate(viga.cargas_polinomicas, 1):
            cargas_lineas.append(
                f"  • Polinómica w_pol{i} [{cp_poly.origen}]: w(u)={cp_poly.a0:.2f}+{cp_poly.a1:.2f}u+"
                f"{cp_poly.a2:.2f}u²+{cp_poly.a3:.2f}u³ en [{cp_poly.x1:.2f}, {cp_poly.x2:.2f}] m"
            )
    if viga.momentos_concentrados:
        for i, mc in enumerate(viga.momentos_concentrados, 1):
            cargas_lineas.append(f"  • Momento M{i} [{mc.origen}]: {mc.M0:.2f} kN·m en x = {mc.x:.2f} m")

    term = viga.accion_termica
    if any(abs(val) > 1e-9 for val in (term.delta_T_uniforme, term.delta_T_gradiente, term.retraccion_micro, term.fluencia_phi)):
        cargas_lineas.append(
            f"  • Térmicas/Reológicas: ΔT₀={term.delta_T_uniforme:+.1f}°C, ΔT_grad={term.delta_T_gradiente:+.1f}°C, "
            f"Retracción={term.retraccion_micro:.0f} με, Fluencia φ={term.fluencia_phi:.2f}"
        )

    cargas_descripcion = "\n".join(cargas_lineas)

    # 4. Texto completo de reacciones
    reac_lineas = []
    for det in resultado.reacciones_detalle:
        partes = [f"Ry={det['Ry']:.2f} kN"]
        if det["tipo"] in ("fijo", "empotrado") or abs(det["Rx"]) > 1e-2:
            partes.append(f"Rx={det['Rx']:.2f} kN")
        if det["tipo"] in ("empotrado", "guiado") or abs(det["M"]) > 1e-2:
            partes.append(f"M={det['M']:.2f} kN·m")
        reac_lineas.append(f"{det['etiqueta']} (x={det['x']:.2f} m): " + ", ".join(partes))
    reacciones_txt = " | ".join(reac_lineas)

    # 5. Muestreo de tramos para tabla Jinja2
    n_total = len(resultado.x)
    n_muestras = min(21, n_total)
    indices = np.linspace(0, n_total - 1, n_muestras, dtype=int)

    tramos_tabla = []
    for idx in indices:
        tramos_tabla.append({
            "x": f"{resultado.x[idx]:.3f}",
            "V": f"{resultado.V[idx]:.2f}",
            "M": f"{resultado.M[idx]:.2f}",
            "theta": f"{resultado.theta[idx]:.5f}",
            "v_mm": f"{resultado.v_mm[idx]:.3f}"
        })

    # 6. Diagnóstico y conclusiones
    estado_esf = "CUMPLE (OK)" if resultado.cumple_esfuerzo else "NO CUMPLE (FALLA)"
    estado_def = "CUMPLE (OK)" if resultado.cumple_deflexion else "NO CUMPLE (FALLA)"

    if resultado.cumple_global:
        dictamen = "ESTRUCTURA SATISFACTORIA (CUMPLE TODOS LOS ESTADOS LÍMITES)"
        obs = ("El elemento estructural evaluado satisface ampliamente los requerimientos de resistencia combinada (flexión/axial) "
               "y los criterios de rigidez y servicio de deflexión máxima admisible bajo las combinaciones de carga analizadas.")
    else:
        fallas = []
        if not resultado.cumple_esfuerzo:
            fallas.append("exceso de esfuerzo admisible")
        if not resultado.cumple_deflexion:
            fallas.append("exceso de deflexión elástica admisible (L/k)")
        dictamen = "ESTRUCTURA NO CONFORME (REQUIERE REDISEÑO)"
        obs = f"El elemento no cumple debido a: {', '.join(fallas)}. Se recomienda aumentar la inercia de la sección o modificar las condiciones de apoyo."

    grado_txt = "Isostática" if resultado.grado_hiperestaticidad == 0 else f"Hiperestática (grado {resultado.grado_hiperestaticidad})"
    nombres_tipo = {
        "simplemente_apoyada": "Simplemente Apoyada",
        "voladizo": "Voladizo Empotrado",
        "doble_empotrada": "Doble Empotramiento",
        "empotrada_movil": "Empotrada + Móvil",
        "guiada_movil": "Empotramiento Guiado + Móvil",
        "elastica": "Sobre Apoyos Elásticos",
        "personalizado": "Configuración Personalizada",
    }
    tipo_txt = f"{nombres_tipo.get(resultado.tipo_viga, resultado.tipo_viga)} ({grado_txt})"

    contexto = {
        "proyecto_nombre": proyecto_nombre,
        "calculo_nombre": calculo_nombre,
        "autor": autor,
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "tipo_viga": tipo_txt,
        "longitud": f"{resultado.L:.2f}",
        "apoyos_texto": apoyos_txt,
        "E_GPa": f"{resultado.E_efectivo_GPa:.2f}",
        "sigma_adm": f"{resultado.sigma_adm:.1f}",
        "limite_k": str(resultado.limite_k),
        "deflexion_limite": f"{resultado.deflexion_limite:.2f}",
        "peso_propio_texto": "Sí" if resultado.peso_propio_incluido else "No",
        "seccion_nombre": resultado.seccion.nombre,
        "seccion_tipo": resultado.seccion.tipo.replace('_', ' ').capitalize(),
        "seccion_area": f"{resultado.seccion.area:.4f}",
        "seccion_inercia": f"{resultado.seccion.inercia:.6e}",
        "seccion_altura": f"{resultado.seccion.altura:.3f}",
        "seccion_w_min": f"{resultado.seccion.w_min:.6e}",
        "cargas_descripcion": cargas_descripcion,
        "reacciones_texto": reacciones_txt,
        "V_abs_max": f"{resultado.V_abs_max:.2f}",
        "x_V_max": f"{resultado.x_V_max:.2f}",
        "M_abs_max": f"{resultado.M_abs_max:.2f}",
        "x_M_max": f"{resultado.x_M_max:.2f}",
        "v_abs_max": f"{resultado.v_abs_max:.3f}",
        "x_v_max": f"{resultado.x_v_max:.2f}",
        "grafica_analisis": img_word,
        "tramos": tramos_tabla,
        "sigma_max": f"{resultado.sigma_max:.2f}",
        "estado_esfuerzo": estado_esf,
        "estado_deflexion": estado_def,
        "dictamen_global": dictamen,
        "observaciones": obs
    }

    doc.render(contexto)

    if ruta_salida is None:
        RUTA_REPORTES.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_sanitizado = "".join(c for c in calculo_nombre if c.isalnum() or c in (' ', '_', '-')).strip()
        ruta_salida = RUTA_REPORTES / f"Memoria_{nombre_sanitizado}_{timestamp}.docx"

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(ruta_salida))
    return ruta_salida
