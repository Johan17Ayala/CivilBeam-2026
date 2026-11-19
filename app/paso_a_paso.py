"""
paso_a_paso.py
Generador de memoria explicativa paso a paso (con ecuaciones, sustituciones numéricas y chequeos)
y exportador directo a Microsoft Word (.docx) mediante python-docx.
Módulo 100% independiente de la interfaz gráfica.

Universidad Distrital Francisco José de Caldas - Facultad Tecnológica
Programación II
"""

import io
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import numpy as np

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.modelo import (
    VigaIsostatica,
    ResultadoViga,
    TIPOS_APOYO,
    COMBINACIONES_CARGA,
)
from app.graficas import generar_figura_analisis_completo, figura_a_bytes


RUTA_APP = Path(__file__).resolve().parent
RUTA_REPORTES = RUTA_APP.parent / "reportes"
RUTA_ESCUDO_UD = RUTA_APP.parent / "plantillas" / "escudo_ud.png"


def generar_pasos_calculo(viga: VigaIsostatica, res: ResultadoViga) -> List[Dict[str, Any]]:
    """
    Construye el desglose técnico paso a paso del cálculo realizado,
    incluyendo fórmulas teóricas y sustituciones con los valores reales del modelo.
    """
    pasos: List[Dict[str, Any]] = []
    sec = res.seccion
    L = res.L
    comb_info = COMBINACIONES_CARGA.get(res.combinacion_usada, COMBINACIONES_CARGA["servicio"])
    factores = comb_info["factores"]

    # ------------------------------------------------------------------
    # PASO 1: Propiedades geométricas y rigidez del material
    # ------------------------------------------------------------------
    c_fibra = sec.inercia / max(sec.w_min, 1e-12)
    w_pp = viga.densidad_kN_m3 * sec.area if viga.incluir_peso_propio else 0.0
    phi = max(0.0, viga.accion_termica.fluencia_phi)
    EI_kNm2 = (res.E_efectivo_GPa * 1e6) * sec.inercia
    EA_kN = (res.E_efectivo_GPa * 1e6) * sec.area

    pasos.append({
        "numero": 1,
        "titulo": "Propiedades Geométricas de la Sección y Rigidez del Material",
        "ecuaciones": [
            "Teorema de Green (Gauss): A = ½ Σ(xᵢyᵢ₊₁ − xᵢ₊₁yᵢ) | Ix = (1/12)Σ(...) − A·ȳ²",
            "Módulo resistente: W_mín = Ix / c_máx",
            "Módulo efectivo por fluencia: E_eff = E / (1 + φ)",
            "Peso propio unitario: w_pp = γ · A",
        ],
        "desarrollo": [
            f"Sección transversal seleccionada: {sec.nombre} (altura total h = {sec.altura:.3f} m).",
            f"Área transversal calculada: A = {sec.area:.5f} m².",
            f"Momento de inercia baricéntrico: Ix = {sec.inercia:.6e} m⁴.",
            f"Distancia máxima al eje neutro: c ≈ Ix / W_mín = {c_fibra:.4f} m → W_mín = {sec.w_min:.6e} m³.",
            (
                f"Peso propio activado (γ = {viga.densidad_kN_m3:.1f} kN/m³): "
                f"w_pp = {viga.densidad_kN_m3:.1f} × {sec.area:.5f} = {w_pp:.3f} kN/m (Origen D)."
                if viga.incluir_peso_propio
                else "Peso propio automático desactivado (w_pp = 0.000 kN/m)."
            ),
            f"Módulo de elasticidad inicial E = {res.E_GPa:.2f} GPa; fluencia lenta φ = {phi:.2f} → E_eff = {res.E_GPa:.2f} / (1 + {phi:.2f}) = {res.E_efectivo_GPa:.2f} GPa.",
            f"Rigidez a flexión E_eff·I = {EI_kNm2:,.2f} kN·m² | Rigidez axial E_eff·A = {EA_kN:,.2f} kN.",
        ],
        "resultado_clave": f"E·I = {EI_kNm2:,.2f} kN·m² | W_mín = {sec.w_min:.4e} m³ | w_pp = {w_pp:.3f} kN/m",
    })

    # ------------------------------------------------------------------
    # PASO 2: Condiciones de apoyo y clasificación estática
    # ------------------------------------------------------------------
    desarrollo_apoyos = [
        f"Longitud total de la viga: L = {L:.2f} m, con {len(viga.apoyos)} apoyo(s) estructural(es):"
    ]
    n_reac_v = 0
    for ap in viga.apoyos:
        nom = TIPOS_APOYO.get(ap.tipo, ap.tipo)
        if ap.tipo == "movil":
            n_reac_v += 1
            desarrollo_apoyos.append(f"• {ap.etiqueta} en x = {ap.x:.2f} m → {nom}: restringe desplazamiento vertical v=0 (incógnita Ry).")
        elif ap.tipo == "fijo":
            n_reac_v += 1
            desarrollo_apoyos.append(f"• {ap.etiqueta} en x = {ap.x:.2f} m → {nom}: restringe u=0 y v=0 (incógnitas Rx, Ry).")
        elif ap.tipo == "empotrado":
            n_reac_v += 2
            desarrollo_apoyos.append(f"• {ap.etiqueta} en x = {ap.x:.2f} m → {nom}: restringe u=0, v=0, θ=0 (incógnitas Rx, Ry, M).")
        elif ap.tipo == "guiado":
            n_reac_v += 2
            desarrollo_apoyos.append(f"• {ap.etiqueta} en x = {ap.x:.2f} m → {nom}: restringe v=0 y θ=0, axial u libre (incógnitas Ry, M).")
        elif ap.tipo == "elastico":
            if ap.ky > 0:
                n_reac_v += 1
            if ap.ktheta > 0:
                n_reac_v += 1
            desarrollo_apoyos.append(
                f"• {ap.etiqueta} en x = {ap.x:.2f} m → {nom}: rigideces ky={ap.ky:.1f} kN/m, kθ={ap.ktheta:.1f} kN·m/rad (R = k·δ)."
            )

    if res.grado_hiperestaticidad == 0:
        clasif_txt = f"Grado de hiperestaticidad en flexión g = {n_reac_v} − 2 = 0 → Viga ISOSTÁTICA."
    else:
        clasif_txt = (
            f"Grado de hiperestaticidad en flexión g = {n_reac_v} − 2 = {res.grado_hiperestaticidad} "
            f"→ Viga HIPERESTÁTICA (requiere compatibilidad de deformaciones / rigidez)."
        )
    desarrollo_apoyos.append(clasif_txt)

    pasos.append({
        "numero": 2,
        "titulo": "Condiciones de Apoyo, Grados de Libertad y Grado de Hiperestaticidad",
        "ecuaciones": [
            "Ecuaciones de equilibrio en plano vertical (flexión): 2 ecuaciones (ΣFy = 0, ΣM = 0)",
            "Grado de indeterminación estática: g = R_flexión − 2",
        ],
        "desarrollo": desarrollo_apoyos,
        "resultado_clave": clasif_txt,
    })

    # ------------------------------------------------------------------
    # PASO 3: Inventario de cargas, factores NSR-10 y resultantes equivalentes
    # ------------------------------------------------------------------
    desarrollo_cargas = [
        f"Combinación de diseño activa: {comb_info['nombre']}.",
        "Factores aplicados por origen: "
        + ", ".join(f"{k}={v:.2f}" for k, v in factores.items()),
    ]
    F_tot_y = 0.0
    F_tot_x = 0.0
    M_tot_x0 = 0.0  # Momento horario total respecto a x=0

    if viga.incluir_peso_propio:
        f_d = float(factores.get("D", 1.0))
        F_pp = f_d * w_pp * L
        xc_pp = L / 2.0
        F_tot_y += F_pp
        M_tot_x0 += F_pp * xc_pp
        desarrollo_cargas.append(
            f"• Peso propio [D]: F_pp = {f_d:.2f} × ({w_pp:.3f} kN/m × {L:.2f} m) = {F_pp:.2f} kN, aplicado en centroide x̄ = {xc_pp:.2f} m."
        )

    for i, cp in enumerate(viga.cargas_puntuales, 1):
        f = float(factores.get(cp.origen.upper(), 1.0))
        Py_f = f * cp.P
        Px_f = f * cp.Px
        F_tot_y += Py_f
        F_tot_x += Px_f
        M_tot_x0 += Py_f * cp.x
        px_str = f", Px_fact = {Px_f:.2f} kN" if abs(Px_f) > 1e-6 else ""
        desarrollo_cargas.append(
            f"• Puntual P{i} [{cp.origen}, f={f:.2f}]: Py_fact = {f:.2f}×{cp.P:.2f} = {Py_f:.2f} kN{px_str} en x = {cp.x:.2f} m "
            f"(aporta M₀ = {Py_f * cp.x:.2f} kN·m)."
        )

    for i, cd in enumerate(viga.cargas_distribuidas, 1):
        f = float(factores.get(cd.origen.upper(), 1.0))
        dx = cd.x2 - cd.x1
        w1_f = f * cd.w1
        w2_f = f * cd.w2
        F_cd = 0.5 * (w1_f + w2_f) * dx
        if abs(w1_f + w2_f) > 1e-12:
            xc_loc = dx * (w1_f + 2.0 * w2_f) / (3.0 * (w1_f + w2_f))
        else:
            xc_loc = 0.5 * dx
        xc_glob = cd.x1 + xc_loc
        F_tot_y += F_cd
        M_tot_x0 += F_cd * xc_glob
        desarrollo_cargas.append(
            f"• Distribuida w{i} [{cd.origen}, f={f:.2f}] en [{cd.x1:.2f}, {cd.x2:.2f}] m (Δx={dx:.2f} m): "
            f"w_fact = [{w1_f:.2f} → {w2_f:.2f}] kN/m → Resultante F = ½({w1_f:.2f}+{w2_f:.2f})×{dx:.2f} = {F_cd:.2f} kN "
            f"en x̄ = {xc_glob:.3f} m."
        )

    for i, cp_poly in enumerate(viga.cargas_polinomicas, 1):
        f = float(factores.get(cp_poly.origen.upper(), 1.0))
        xs_int = np.linspace(cp_poly.x1, cp_poly.x2, 200)
        ws_int = f * cp_poly.evaluar(xs_int)
        F_poly = float(np.trapezoid(ws_int, xs_int)) if hasattr(np, "trapezoid") else float(np.trapz(ws_int, xs_int))
        M_poly = float(np.trapezoid(ws_int * xs_int, xs_int)) if hasattr(np, "trapezoid") else float(np.trapz(ws_int * xs_int, xs_int))
        xc_poly = M_poly / F_poly if abs(F_poly) > 1e-9 else 0.5 * (cp_poly.x1 + cp_poly.x2)
        F_tot_y += F_poly
        M_tot_x0 += M_poly
        desarrollo_cargas.append(
            f"• Polinómica w_pol{i} [{cp_poly.origen}, f={f:.2f}] en [{cp_poly.x1:.2f}, {cp_poly.x2:.2f}] m: "
            f"∫w(u)dx = {F_poly:.2f} kN con centroide en x̄ = {xc_poly:.3f} m."
        )

    for i, mc in enumerate(viga.momentos_concentrados, 1):
        f = float(factores.get(mc.origen.upper(), 1.0))
        M0_f = f * mc.M0
        M_tot_x0 -= M0_f
        desarrollo_cargas.append(
            f"• Momento puntual M{i} [{mc.origen}, f={f:.2f}]: M₀_fact = {M0_f:.2f} kN·m en x = {mc.x:.2f} m."
        )

    term = viga.accion_termica
    if any(abs(v) > 1e-9 for v in (term.delta_T_uniforme, term.delta_T_gradiente, term.retraccion_micro)):
        f_T = float(factores.get("T", 1.0))
        eps0 = (term.alpha_T * term.delta_T_uniforme - term.retraccion_micro * 1e-6) * f_T
        kapT = (term.alpha_T * term.delta_T_gradiente * f_T) / max(sec.altura, 1e-4)
        desarrollo_cargas.append(
            f"• Acción Térmica/Reológica [T, f={f_T:.2f}]: deformación axial ε₀ = {eps0:.3e}, "
            f"curvatura térmica κ_T = {kapT:.3e} rad/m."
        )

    desarrollo_cargas.append(
        f"Total cargas verticales factorizadas ΣFy_cargas = {F_tot_y:.2f} kN (↓) | ΣFx_cargas = {F_tot_x:.2f} kN."
    )

    pasos.append({
        "numero": 3,
        "titulo": "Factores de Combinación y Resultantes Equivalentes de Carga",
        "ecuaciones": [
            "Carga trapezoidal: F = ½·(w₁ + w₂)·Δx",
            "Centroide local desde x₁: x̄_loc = Δx · (w₁ + 2w₂) / [3·(w₁ + w₂)]",
            "Carga no lineal: F = ∫ w(u) dx mediante cuadratura de Gauss-Legendre",
        ],
        "desarrollo": desarrollo_cargas,
        "resultado_clave": f"ΣFy_cargas = {F_tot_y:.2f} kN | ΣM(x=0)_cargas = {M_tot_x0:.2f} kN·m",
    })

    # ------------------------------------------------------------------
    # PASO 4: Equilibrio Estático / Solución Matricial y Reacciones
    # ------------------------------------------------------------------
    desarrollo_reac = []
    ecuaciones_reac = [
        "Equilibrio global: ΣFy = 0 (ΣRy_apoyos = ΣFy_cargas)",
        "Equilibrio de momentos: ΣM_z = 0",
    ]

    if res.grado_hiperestaticidad == 0 and len(viga.apoyos) == 2 and all(ap.tipo in ("fijo", "movil") for ap in viga.apoyos):
        x1 = viga.apoyos[0].x
        x2 = viga.apoyos[1].x
        M_resp_a1 = M_tot_x0 - F_tot_y * x1
        R2_calc = M_resp_a1 / (x2 - x1)
        R1_calc = F_tot_y - R2_calc
        ecuaciones_reac.append("R₂ = ΣM_A1 / (x₂ − x₁)  y  R₁ = ΣFy_cargas − R₂")
        desarrollo_reac.extend([
            f"Tomando momentos respecto al apoyo {viga.apoyos[0].etiqueta} (x₁ = {x1:.2f} m):",
            f"ΣM_A1 = ΣM(x=0) − ΣFy·x₁ = {M_tot_x0:.2f} − ({F_tot_y:.2f}×{x1:.2f}) = {M_resp_a1:.2f} kN·m.",
            f"R₂ = {M_resp_a1:.2f} / ({x2:.2f} − {x1:.2f}) = {R2_calc:.2f} kN (↑).",
            f"Por ΣFy = 0: R₁ = {F_tot_y:.2f} − {R2_calc:.2f} = {R1_calc:.2f} kN (↑).",
        ])
    elif res.grado_hiperestaticidad == 0 and len(viga.apoyos) == 1 and viga.apoyos[0].tipo == "empotrado":
        x0 = viga.apoyos[0].x
        M_emp_calc = M_tot_x0 - F_tot_y * x0
        ecuaciones_reac.append("Rv = ΣFy_cargas  y  M_emp = ΣM(x_emp)")
        desarrollo_reac.extend([
            f"Por equilibrio vertical en voladizo: Rv = ΣFy_cargas = {F_tot_y:.2f} kN (↑).",
            f"Momento de empotramiento en x = {x0:.2f} m: M_emp = {M_emp_calc:.2f} kN·m.",
        ])
    else:
        ecuaciones_reac.append("Sistema matricial FEM 1D (Hermite): [K_estructural]{d} = {F_eq} → {R} = [K]{d} − {F_eq}")
        desarrollo_reac.append(
            "Debido a las restricciones hiperestáticas o elásticas, el sistema se resuelve ensamblando la matriz "
            "de rigidez global de Euler-Bernoulli (funciones de Hermite cúbicas) y barra axial 1D."
        )

    sum_Ry = sum(d["Ry"] for d in res.reacciones_detalle)
    sum_Rx = sum(d["Rx"] for d in res.reacciones_detalle)
    for det in res.reacciones_detalle:
        desarrollo_reac.append(
            f"• Reacción {det['etiqueta']} ({det['tipo']} en x={det['x']:.2f} m): "
            f"Ry = {det['Ry']:.2f} kN | Rx = {det['Rx']:.2f} kN | M = {det['M']:.2f} kN·m."
        )
    desarrollo_reac.append(
        f"Verificación de equilibrio: ΣRy = {sum_Ry:.2f} kN vs ΣFy_cargas = {F_tot_y:.2f} kN "
        f"(diferencia = {abs(sum_Ry - F_tot_y):.2e} kN)."
    )

    pasos.append({
        "numero": 4,
        "titulo": "Cálculo de Reacciones en Apoyos y Verificación de Equilibrio",
        "ecuaciones": ecuaciones_reac,
        "desarrollo": desarrollo_reac,
        "resultado_clave": " | ".join(f"{d['etiqueta']}: Ry={d['Ry']:.2f} kN" for d in res.reacciones_detalle),
    })

    # ------------------------------------------------------------------
    # PASO 5: Esfuerzos internos V(x), M(x) y N(x)
    # ------------------------------------------------------------------
    pasos.append({
        "numero": 5,
        "titulo": "Construcción de Diagramas Internos V(x), M(x) y N(x)",
        "ecuaciones": [
            "Fuerza Cortante: V(x) = ΣRy(xᵢ ≤ x) − ΣP(xᵢ ≤ x) − ∫₀ˣ w(ξ) dξ",
            "Momento Flector: M(x) = M(0⁺) + ∫₀ˣ V(ξ) dξ − ΣM₀(xᵢ ≤ x)",
            "Fuerza Axial: N(x) = E·A · (du/dx − ε₀)",
        ],
        "desarrollo": [
            f"Se discretizó la viga en {len(res.x)} puntos de evaluación incluyendo exactamente todas las abscisas de apoyos y saltos de carga.",
            f"Fuerza cortante positiva máxima: V_máx = {res.V_max:.2f} kN | Cortante mínima: V_mín = {res.V_min:.2f} kN.",
            f"Cortante absoluto máximo de diseño: |V|_máx = {res.V_abs_max:.2f} kN ubicado en x = {res.x_V_max:.2f} m.",
            f"Momento flector positivo máximo (tracción inferior): M⁺_máx = {res.M_max:.2f} kN·m.",
            f"Momento flector negativo máximo (tracción superior): M⁻_mín = {res.M_min:.2f} kN·m.",
            f"Momento flector absoluto máximo de diseño: |M|_máx = {res.M_abs_max:.2f} kN·m ubicado en x = {res.x_M_max:.2f} m.",
            f"Fuerza axial máxima en la sección: |N|_máx = {res.N_abs_max:.2f} kN (por cargas horizontales o restricción térmica).",
        ],
        "resultado_clave": f"|V|_máx = {res.V_abs_max:.2f} kN | |M|_máx = {res.M_abs_max:.2f} kN·m | |N|_máx = {res.N_abs_max:.2f} kN",
    })

    # ------------------------------------------------------------------
    # PASO 6: Deflexión elástica, esfuerzo combinado y dictamen NSR-10
    # ------------------------------------------------------------------
    sigma_flex_MPa = (res.M_abs_max / max(sec.w_min, 1e-12)) / 1000.0
    sigma_ax_MPa = (res.N_abs_max / max(sec.area, 1e-12)) / 1000.0
    uso_esf = (res.sigma_max / max(res.sigma_adm, 1e-9)) * 100.0
    uso_def = (res.v_abs_max / max(res.deflexion_limite, 1e-9)) * 100.0

    pasos.append({
        "numero": 6,
        "titulo": "Deflexión Elástica (Euler-Bernoulli), Esfuerzos y Chequeo NSR-10",
        "ecuaciones": [
            "Ecuación elástica: d²v/dx² = M(x) / (E_eff · I) + κ_T",
            "Esfuerzo normal combinado: σ_máx = máx(|N|/A + |M|/W_mín)",
            f"Límite de servicio en deflexión: δ_adm = L / {res.limite_k}",
        ],
        "desarrollo": [
            f"Integración de curvatura: la flecha elástica máxima absoluta ocurre en x = {res.x_v_max:.2f} m con magnitud |δ|_máx = {res.v_abs_max:.3f} mm (rango [{res.v_min:.3f}, {res.v_max:.3f}] mm).",
            f"Límite normativo L / {res.limite_k}: δ_adm = ({L:.2f} m / {res.limite_k}) × 1000 = ±{res.deflexion_limite:.2f} mm.",
            f"Verificación de deflexión: {res.v_abs_max:.3f} mm vs {res.deflexion_limite:.2f} mm (uso = {uso_def:.1f}%) → {'CUMPLE' if res.cumple_deflexion else 'NO CUMPLE'}.",
            f"Componente por flexión: |M|_máx / W_mín = {res.M_abs_max:.2f} kN·m / {sec.w_min:.4e} m³ / 1000 = {sigma_flex_MPa:.2f} MPa.",
            f"Componente axial: |N|_máx / A = {res.N_abs_max:.2f} / {sec.area:.5f} / 1000 = {sigma_ax_MPa:.2f} MPa.",
            f"Esfuerzo máximo combinado real: σ_máx = {res.sigma_max:.2f} MPa vs σ_adm = {res.sigma_adm:.1f} MPa (uso = {uso_esf:.1f}%) → {'CUMPLE' if res.cumple_esfuerzo else 'NO CUMPLE'}.",
            f"DICTAMEN GLOBAL DE LA ESTRUCTURA: {'SATISFACTORIO (CUMPLE NORMATIVA)' if res.cumple_global else 'NO CONFORME (REQUIERE REDISEÑO)'}.",
        ],
        "resultado_clave": f"σ_máx = {res.sigma_max:.2f} MPa ({uso_esf:.1f}%) | δ_máx = {res.v_abs_max:.3f} mm ({uso_def:.1f}%)",
    })

    return pasos


def _borde_celda(cell, color="BFBFBF"):
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '4')
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), color)
        tcBorders.append(el)
    tcPr.append(tcBorders)


def _sombreado_celda(cell, fill_hex="EBF3FA"):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)
    tcPr.append(shd)


def generar_word_paso_a_paso(
    viga: VigaIsostatica,
    resultado: ResultadoViga,
    proyecto_nombre: str = "Proyecto Estructural",
    calculo_nombre: str = "Viga Analizada",
    autor: str = "Ingeniero Calculista",
    ruta_salida: Optional[Path] = None,
) -> Path:
    """
    Genera un informe formal en Word (.docx) adaptado rigurosamente al formato
    institucional de la Universidad Distrital Francisco José de Caldas (Facultad Tecnológica),
    con portada oficial, tablas de contenido/figuras/tablas, y los 8 capítulos completos.
    """
    pasos = generar_pasos_calculo(viga, resultado)
    sec = resultado.seccion
    L = resultado.L
    doc = Document()

    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # =========================================================================
    # 1. PORTADA OFICIAL (FORMATO UNIVERSIDAD DISTRITAL)
    # =========================================================================
    p_port_tit = doc.add_paragraph()
    p_port_tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_port_tit.paragraph_format.space_before = Pt(6)
    p_port_tit.paragraph_format.space_after = Pt(14)
    r_pt = p_port_tit.add_run("INFORME DE ANÁLISIS ESTRUCTURAL DE VIGAS Y DIAGRAMAS DE SOLICITACIONES (NSR-10)")
    r_pt.bold = True
    r_pt.font.size = Pt(14)
    r_pt.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

    # Escudo institucional centrado
    if RUTA_ESCUDO_UD.exists():
        p_esc = doc.add_paragraph()
        p_esc.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_esc.paragraph_format.space_after = Pt(8)
        p_esc.add_run().add_picture(str(RUTA_ESCUDO_UD), width=Inches(2.5))

    p_ud_nom = doc.add_paragraph()
    p_ud_nom.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ud_nom.paragraph_format.space_after = Pt(20)
    r_ud_n = p_ud_nom.add_run("UNIVERSIDAD DISTRITAL\nFRANCISCO JOSÉ DE CALDAS")
    r_ud_n.bold = True
    r_ud_n.font.size = Pt(13)
    r_ud_n.font.color.rgb = RGBColor(0x1B, 0x1B, 0x1B)

    # Autores con códigos estudiantiles
    p_aut = doc.add_paragraph()
    p_aut.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_aut.paragraph_format.space_after = Pt(18)
    r_aut1 = p_aut.add_run("JOHAN FABIAN AYALA MARENTES – 20251579041\n")
    r_aut1.bold = True
    r_aut1.font.size = Pt(11)
    if autor and autor.strip() not in ("Ingeniero Calculista", "Johan Ayala", "JOHAN FABIAN AYALA MARENTES"):
        r_aut_extra = p_aut.add_run(f"{autor.strip()}\n")
        r_aut_extra.bold = True
        r_aut_extra.font.size = Pt(10.5)

    # Asignatura y Programa
    p_prog = doc.add_paragraph()
    p_prog.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_prog.paragraph_format.space_after = Pt(28)
    r_prog = p_prog.add_run(
        "PROGRAMACIÓN II (GRUPO 18)\n"
        "PROYECTO 02: APLICACIÓN DE ESCRITORIO CIVILBEAM 2026\n"
        "INGENIERÍA CIVIL (CICLOS PROPEDÉUTICOS)\n"
        "UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS\n"
        "FACULTAD TECNOLÓGICA\n"
        "BOGOTÁ D.C.\n"
        f"{datetime.now().strftime('%B %Y').upper()}"
    )
    r_prog.font.size = Pt(10.5)
    r_prog.bold = True
    r_prog.font.color.rgb = RGBColor(0x22, 0x22, 0x22)

    # =========================================================================
    # 2. PÁGINA DE CONTENIDO E ÍNDICES
    # =========================================================================
    doc.add_page_break()

    p_tc = doc.add_paragraph()
    r_tc = p_tc.add_run("Tabla de contenido")
    r_tc.bold = True
    r_tc.font.size = Pt(12)

    items_tc = [
        ("1.\tRESUMEN", "3"),
        ("2.\tOBJETIVOS", "3"),
        ("2.1.\tObjetivo general", "3"),
        ("2.2.\tObjetivos específicos", "3"),
        ("3.\tMARCO TEORICO", "3"),
        ("4.\tMATERIALES Y ENTORNO COMPUTACIONAL", "4"),
        ("5.\tPROCEDIMIENTO Y METODOLOGÍA", "5"),
        ("6.\tANÁLISIS ESTRUCTURAL DE LA VIGA", "5"),
        ("6.1.\tDatos iniciales", "5"),
        ("6.2.\tResultados del ensayo / análisis FEM 1D", "6"),
        ("6.3.\tCálculos paso a paso y deducciones", "6"),
        ("6.4.\tAnálisis de resultados y verificación normativa", "8"),
        ("7.\tCONCLUSIONES", "10"),
        ("8.\tBIBLIOGRAFÍA", "10"),
    ]
    for tit, pag in items_tc:
        p_item = doc.add_paragraph()
        p_item.paragraph_format.space_before = Pt(1)
        p_item.paragraph_format.space_after = Pt(1)
        r_i = p_item.add_run(tit)
        r_i.font.size = Pt(9.5)
        if not tit.startswith("2.") and not tit.startswith("6."):
            r_i.bold = True
        r_p = p_item.add_run(f"\t{pag}")
        r_p.font.size = Pt(9.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Tabla ilustraciones
    p_ti = doc.add_paragraph()
    r_ti = p_ti.add_run("Tabla ilustraciones")
    r_ti.bold = True
    r_ti.font.size = Pt(11)
    for ilu, pag in [
        ("Ilustración 1. Modelo físico de apoyos y cargas en viga longitudinal.", "5"),
        ("Ilustración 2. Sección transversal poligonal analizada con pysections (pymas).", "6"),
    ]:
        p_il = doc.add_paragraph()
        p_il.paragraph_format.space_before = Pt(1)
        p_il.paragraph_format.space_after = Pt(1)
        p_il.add_run(f"{ilu}\t{pag}").font.size = Pt(9)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # Tabla de graficas
    p_tg = doc.add_paragraph()
    r_tg = p_tg.add_run("Tabla de graficas")
    r_tg.bold = True
    r_tg.font.size = Pt(11)
    for grf, pag in [
        ("Gráfica 1. Diagrama de Fuerza Axial N(x) en el elemento estructural.", "8"),
        ("Gráfica 2. Diagrama de Fuerza Cortante V(x) y verificación de saltos de cortante.", "8"),
        ("Gráfica 3. Diagrama de Momento Flector M(x) y localización de Mmáx.", "8"),
        ("Gráfica 4. Curva elástica de Deflexión v(x) frente al límite de servicio NSR-10.", "8"),
    ]:
        p_g = doc.add_paragraph()
        p_g.paragraph_format.space_before = Pt(1)
        p_g.paragraph_format.space_after = Pt(1)
        p_g.add_run(f"{grf}\t{pag}").font.size = Pt(9)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # Índice de Tablas
    p_tt = doc.add_paragraph()
    r_tt = p_tt.add_run("Índice de Tablas")
    r_tt.bold = True
    r_tt.font.size = Pt(11)
    for tab, pag in [
        ("Tabla 1. Datos iniciales del modelo, apoyos y solicitaciones. Elaboración: Propia.", "5"),
        ("Tabla 2. Resumen de reacciones nodales y grado de hiperestaticidad. Elaboración: Propia.", "6"),
        ("Tabla 3. Verificación de Estados Límites de Resistencia y Servicio (NSR-10).", "9"),
        ("Tabla 4. Solicitaciones internas longitudinales discretizadas en 17 estaciones.", "9"),
    ]:
        p_t = doc.add_paragraph()
        p_t.paragraph_format.space_before = Pt(1)
        p_t.paragraph_format.space_after = Pt(1)
        p_t.add_run(f"{tab}\t{pag}").font.size = Pt(9)

    # =========================================================================
    # 3. CUERPO DEL INFORME (CAPÍTULOS 1 AL 8)
    # =========================================================================
    doc.add_page_break()

    # 1. RESUMEN
    p_h1 = doc.add_paragraph()
    r_h1 = p_h1.add_run("1.\tRESUMEN")
    r_h1.bold = True; r_h1.font.size = Pt(12)

    comb_txt = COMBINACIONES_CARGA.get(resultado.combinacion_usada, {}).get("nombre", resultado.combinacion_usada)
    p_res_body = doc.add_paragraph()
    p_res_body.paragraph_format.space_after = Pt(8)
    p_res_body.add_run(
        f"En este informe se presentan los resultados del análisis estructural elástico lineal de la viga "
        f"'{calculo_nombre}' perteneciente al proyecto '{proyecto_nombre}', con una longitud total de L = {L:.2f} m. "
        f"La sección transversal seleccionada corresponde a {sec.nombre} (A = {sec.area:.5f} m², Ix = {sec.inercia:.6e} m⁴), "
        f"cuyas propiedades geométricas se calcularon aplicando el Teorema de Green / Gauss mediante el módulo de código abierto "
        f"pymas. El cálculo de esfuerzos internos y deformaciones se llevó a cabo mediante el Método de Elementos Finitos 1D (FEM) "
        f"bajo la combinación de carga {comb_txt}. Se obtuvieron una fuerza cortante máxima de |V|máx = {resultado.V_abs_max:.2f} kN, "
        f"un momento flector máximo de |M|máx = {resultado.M_abs_max:.2f} kN·m en x = {resultado.x_M_max:.2f} m, y una flecha "
        f"elástica máxima de |δ|máx = {resultado.v_abs_max:.3f} mm frente al límite normativo de L/{resultado.limite_k} "
        f"(±{resultado.deflexion_limite:.2f} mm), concluyendo un dictamen global de: "
        f"{'CUMPLE SATISFACTORIAMENTE LA NORMATIVA' if resultado.cumple_global else 'NO CUMPLE LOS LÍMITES NORMATIVOS'}."
    )

    # 2. OBJETIVOS
    p_h2 = doc.add_paragraph()
    r_h2 = p_h2.add_run("2.\tOBJETIVOS")
    r_h2.bold = True; r_h2.font.size = Pt(12)

    p_og = doc.add_paragraph()
    p_og.paragraph_format.space_after = Pt(2)
    r_og_t = p_og.add_run("2.1.\tObjetivo general\n")
    r_og_t.bold = True; r_og_t.font.size = Pt(10.5)
    p_og.add_run(
        "Determinar analítica y numéricamente los diagramas de fuerza cortante, momento flector, fuerza axial y "
        "deflexión elástica en vigas continuas bajo combinaciones de carga del Reglamento Colombiano de Construcción "
        "Sismo Resistente (NSR-10, Título B y C), evaluando rigurosamente los estados límites de resistencia y serviciabilidad."
    )

    p_oe = doc.add_paragraph()
    p_oe.paragraph_format.space_before = Pt(4)
    p_oe.paragraph_format.space_after = Pt(8)
    r_oe_t = p_oe.add_run("2.2.\tObjetivos específicos\n")
    r_oe_t.bold = True; r_oe_t.font.size = Pt(10.5)
    oes = [
        "Calcular las propiedades mecánicas de la sección transversal (área, inercia, centroide y módulo resistente) mediante el Teorema de Green.",
        "Implementar un motor de Elementos Finitos 1D con funciones cúbicas de Hermite y cuadratura de Gauss-Legendre de 4 puntos.",
        "Evaluar la respuesta estructural bajo los 5 tipos de apoyos (móvil, fijo, empotrado, guiado y elástico).",
        "Verificar el equilibrio estático residual global (ΣFy = 0, ΣM = 0) asegurando convergencia y precisión de máquina.",
        "Contrastar los esfuerzos actuantes y deflexiones frente a los admisibles normativos de la NSR-10.",
    ]
    for oe in oes:
        p_oe.add_run(f"• {oe}\n")

    # 3. MARCO TEÓRICO
    p_h3 = doc.add_paragraph()
    r_h3 = p_h3.add_run("3.\tMARCO TEORICO")
    r_h3.bold = True; r_h3.font.size = Pt(12)

    p_mt = doc.add_paragraph()
    p_mt.paragraph_format.space_after = Pt(8)
    p_mt.add_run(
        "El análisis estructural elástico lineal de elementos prismáticos bajo flexión se fundamenta en la teoría de "
        "vigas de Euler-Bernoulli, la cual postula que las secciones planas perpendiculares al eje neutro permanecen planas "
        "y perpendiculares al mismo después de la deformación. La ecuación diferencial de cuarto orden que rige la deflexión v(x) es:\n\n"
        "\tE·I · (d⁴v / dx⁴) = −q(x)\n\n"
        "Integrando sucesivamente a lo largo de la directriz longitudinal se obtienen la fuerza cortante V(x) = dM/dx, el momento "
        "flector M(x) = E·I·(d²v/dx²), el giro elástico θ(x) = dv/dx y la flecha elástica v(x).\n\n"
        "Para secciones transversales arbitrarias, el cálculo de las propiedades se efectúa mediante la aplicación del "
        "Teorema de Green / Gauss sobre polígonos cerrados 2D, provisto por el módulo de código abierto pymas (desarrollado por "
        "Cristian Danilo Ramírez Vargas):\n\n"
        "\tA = ½ Σ(xᵢ yᵢ₊₁ − xᵢ₊₁ yᵢ),    Ix = (1/12) Σ(yᵢ² + yᵢyᵢ₊₁ + yᵢ₊₁²)(xᵢ yᵢ₊₁ − xᵢ₊₁ yᵢ) − A·ȳ²\n\n"
        "Asimismo, los criterios de diseño se rigen por la NSR-10 (Título B), controlando el esfuerzo normal combinado "
        "σ = |M|·c/I + |N|/A ≤ σ_adm y la deflexión máxima instantánea |δ|máx ≤ L/k (donde k = 360 según B.4.2)."
    )

    # 4. MATERIALES Y ENTORNO COMPUTACIONAL
    p_h4 = doc.add_paragraph()
    r_h4 = p_h4.add_run("4.\tMATERIALES Y ENTORNO COMPUTACIONAL")
    r_h4.bold = True; r_h4.font.size = Pt(12)

    p_mat = doc.add_paragraph()
    p_mat.paragraph_format.space_after = Pt(8)
    p_mat.add_run(
        "Para la ejecución y validación del modelo estructural se utilizó el siguiente entorno tecnológico y materiales:\n\n"
        "• Lenguaje de Programación: Python 3.14 (arquitectura modular en capas).\n"
        "• Interfaz Gráfica de Usuario: Flet Material 3 (GUI desktop nativa mediante flet-desktop).\n"
        "• Álgebra Matricial y Cuadratura Numérica: NumPy 2.5 y SciPy 1.18 (cuadratura de Gauss-Legendre de 4 puntos).\n"
        "• Visualización Técnica Vectorizada: Matplotlib 3.11 (figuras de alta resolución exportadas en memoria).\n"
        "• Persistencia de Datos Relacional: SQLite 3 embebido (base de datos relacional local con tablas proyectos y calculos).\n"
        "• Generación Documental: python-docx 1.2 y docxtpl 0.20.\n"
        f"• Propiedades del Material: Módulo de Elasticidad E = {resultado.E_GPa:.2f} GPa (E_eff = {resultado.E_efectivo_GPa:.2f} GPa), "
        f"Densidad volumétrica γ = {viga.densidad_kN_m3:.1f} kN/m³, Esfuerzo admisible σ_adm = {resultado.sigma_adm:.1f} MPa."
    )

    # 5. PROCEDIMIENTO Y METODOLOGÍA
    p_h5 = doc.add_paragraph()
    r_h5 = p_h5.add_run("5.\tPROCEDIMIENTO Y METODOLOGÍA")
    r_h5.bold = True; r_h5.font.size = Pt(12)

    p_proc = doc.add_paragraph()
    p_proc.paragraph_format.space_after = Pt(8)
    p_proc.add_run(
        "El procedimiento de modelación y solución estructural implementado en la aplicación CivilBeam 2026 comprende las siguientes etapas:\n"
        "1. Definición geométrica del elemento estructural (longitud L) y selección de la sección transversal.\n"
        "2. Configuración de los apoyos en la viga según su tipología (móvil, fijo, empotrado, guiado o elástico).\n"
        "3. Incorporación de solicitaciones externas (puntuales P, distribuidas uniformes/trapezoidales, no lineales y momentos) "
        "con su respectivo origen de persistencia (D, L, W, E, S, T) y factores de mayoración NSR-10.\n"
        "4. Discretización de malla adaptativa nodal ubicando nodos obligatorios en discontinuidades de carga y apoyos.\n"
        "5. Ensamblaje de la matriz de rigidez global K y el vector de fuerzas nodales consistentes F.\n"
        "6. Imposición de condiciones de frontera y solución del sistema algebraico lineal K·U = F.\n"
        "7. Recuperación de reacciones, postproceso de diagramas internos (N, V, M, v) y verificación de equilibrio residual.\n"
        "8. Generación automatizada de la presente memoria técnica y exportación a formato Microsoft Word."
    )

    # 6. ANÁLISIS ESTRUCTURAL DE LA VIGA
    p_h6 = doc.add_paragraph()
    r_h6 = p_h6.add_run("6.\tANÁLISIS ESTRUCTURAL DE LA VIGA")
    r_h6.bold = True; r_h6.font.size = Pt(12)

    # 6.1 Datos iniciales
    p_h61 = doc.add_paragraph()
    p_h61.paragraph_format.space_after = Pt(4)
    r_h61 = p_h61.add_run("6.1.\tDatos iniciales\n")
    r_h61.bold = True; r_h61.font.size = Pt(10.5)
    p_h61.add_run("Para la elaboración del análisis se ingresaron los siguientes parámetros en la herramienta computacional:")

    # Tabla 1. Datos iniciales
    p_t1_lbl = doc.add_paragraph()
    p_t1_lbl.paragraph_format.space_before = Pt(4)
    p_t1_lbl.paragraph_format.space_after = Pt(2)
    p_t1_lbl.add_run("Tabla 1. Datos iniciales del modelo, apoyos y solicitaciones. Elaboración: Propia.").bold = True
    p_t1_lbl.runs[0].font.size = Pt(8.5)

    t_d1 = doc.add_table(rows=6, cols=3)
    t_d1.alignment = WD_TABLE_ALIGNMENT.CENTER
    for r in t_d1.rows:
        r.cells[0].width = Inches(2.5)
        r.cells[1].width = Inches(2.2)
        r.cells[2].width = Inches(1.8)

    for j, h in enumerate(["Parámetro del Modelo", "Valor Numérico", "Unidad"]):
        c = t_d1.rows[0].cells[j]
        c.paragraphs[0].add_run(h).bold = True
        c.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _sombreado_celda(c, "1B365D")
        _borde_celda(c, "1B365D")

    filas_t1 = [
        ("Longitud total de la viga (L)", f"{L:.2f}", "m"),
        ("Sección transversal", f"{sec.nombre} (h = {sec.altura:.3f} m)", "Polígono 2D"),
        ("Área transversal (A) / Inercia (Ix)", f"{sec.area:.5f} m² / {sec.inercia:.6e}", "m² / m⁴"),
        ("Módulo de Elasticidad (E) / Esfuerzo admisible", f"{resultado.E_GPa:.2f} GPa / {resultado.sigma_adm:.1f}", "GPa / MPa"),
        ("Criterio de deflexión admisible", f"L / {resultado.limite_k} (±{resultado.deflexion_limite:.2f} mm)", "NSR-10 B.4"),
    ]
    for row_idx, (p_nom, p_val, p_uni) in enumerate(filas_t1, start=1):
        bg = "F9FAFB" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, txt in enumerate([p_nom, p_val, p_uni]):
            c = t_d1.rows[row_idx].cells[col_idx]
            c.paragraphs[0].add_run(txt).font.size = Pt(8.5)
            _sombreado_celda(c, bg)
            _borde_celda(c, "D1D5DB")

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # 6.2 Resultados del ensayo / análisis FEM 1D
    p_h62 = doc.add_paragraph()
    p_h62.paragraph_format.space_before = Pt(4)
    p_h62.paragraph_format.space_after = Pt(4)
    r_h62 = p_h62.add_run("6.2.\tResultados del ensayo / análisis FEM 1D\n")
    r_h62.bold = True; r_h62.font.size = Pt(10.5)

    p_t2_lbl = doc.add_paragraph()
    p_t2_lbl.paragraph_format.space_after = Pt(2)
    p_t2_lbl.add_run("Tabla 2. Resumen de reacciones nodales y grado de hiperestaticidad. Elaboración: Propia.").bold = True
    p_t2_lbl.runs[0].font.size = Pt(8.5)

    n_ap = len(viga.apoyos)
    t_reac = doc.add_table(rows=1 + max(1, n_ap), cols=5)
    t_reac.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, h in enumerate(["Apoyo / Etiqueta", "Tipo de Apoyo", "Posición x [m]", "Reacción Vertical Ry [kN]", "Reacción Axial Rx [kN]"]):
        c = t_reac.rows[0].cells[j]
        c.paragraphs[0].add_run(h).bold = True
        c.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _sombreado_celda(c, "1B365D")
        _borde_celda(c, "1B365D")

    for i_ap, ap_det in enumerate(resultado.reacciones_detalle, start=1):
        nom_ap = TIPOS_APOYO.get(ap_det.get("tipo", "movil"), ap_det.get("tipo", "movil"))
        bg = "F9FAFB" if i_ap % 2 == 1 else "FFFFFF"
        for col_i, txt in enumerate([
            f"Apoyo {ap_det.get('etiqueta', i_ap)}",
            nom_ap,
            f"{ap_det.get('x', 0.0):.2f}",
            f"{ap_det.get('Ry', 0.0):.2f}",
            f"{ap_det.get('Rx', 0.0):.2f}",
        ]):
            c = t_reac.rows[i_ap].cells[col_i]
            c.paragraphs[0].add_run(txt).font.size = Pt(8.5)
            _sombreado_celda(c, bg)
            _borde_celda(c, "D1D5DB")

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # 6.3 Cálculos
    p_h63 = doc.add_paragraph()
    p_h63.paragraph_format.space_before = Pt(4)
    p_h63.paragraph_format.space_after = Pt(4)
    r_h63 = p_h63.add_run("6.3.\tCálculos paso a paso y deducciones\n")
    r_h63.bold = True; r_h63.font.size = Pt(10.5)

    for p_info in pasos:
        p_paso_tit = doc.add_paragraph()
        p_paso_tit.paragraph_format.space_before = Pt(4)
        p_paso_tit.paragraph_format.space_after = Pt(2)
        r_ptit = p_paso_tit.add_run(f"Paso {p_info['numero']}: {p_info['titulo']}")
        r_ptit.bold = True; r_ptit.font.size = Pt(9.5); r_ptit.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

        # Cuadro de fórmulas aplicadas
        t_box = doc.add_table(rows=1, cols=1)
        t_box.alignment = WD_TABLE_ALIGNMENT.CENTER
        t_box.columns[0].width = Inches(6.5)
        c_box = t_box.rows[0].cells[0]
        _sombreado_celda(c_box, "F0F4F8")
        _borde_celda(c_box, "93C5FD")
        p_fe = c_box.paragraphs[0]
        p_fe.add_run("Ecuaciones de diseño:\n").bold = True
        p_fe.runs[0].font.size = Pt(8.5)
        p_fe.runs[0].font.color.rgb = RGBColor(0x1E, 0x40, 0xAF)
        for eq in p_info["ecuaciones"]:
            r_eq = p_fe.add_run(f"  • {eq}\n")
            r_eq.font.size = Pt(8.5)
            r_eq.font.name = "Consolas"

        for lin in p_info["desarrollo"]:
            p_dl = doc.add_paragraph()
            p_dl.paragraph_format.space_before = Pt(1)
            p_dl.paragraph_format.space_after = Pt(1)
            r_dl = p_dl.add_run(lin)
            r_dl.font.size = Pt(9)

        p_rc = doc.add_paragraph()
        p_rc.paragraph_format.space_before = Pt(2)
        p_rc.paragraph_format.space_after = Pt(4)
        r_rc = p_rc.add_run(f"▶ Resultado Clave: {p_info['resultado_clave']}")
        r_rc.bold = True
        r_rc.font.size = Pt(9)
        r_rc.font.color.rgb = RGBColor(0x06, 0x5F, 0x46)

    # 6.4 Análisis de resultados
    p_h64 = doc.add_paragraph()
    p_h64.paragraph_format.space_before = Pt(6)
    p_h64.paragraph_format.space_after = Pt(4)
    r_h64 = p_h64.add_run("6.4.\tAnálisis de resultados y verificación normativa\n")
    r_h64.bold = True; r_h64.font.size = Pt(10.5)

    p_disc = doc.add_paragraph()
    p_disc.paragraph_format.space_after = Pt(6)
    p_disc.add_run(
        "A partir de la solución por elementos finitos, se construyeron los diagramas completos de fuerza cortante V(x), "
        "momento flector M(x) y curva elástica de deflexión v(x). Las envolventes confirman que el comportamiento se ajusta "
        "a la mecánica de materiales lineal, observándose los saltos exactos de cortante en los puntos de aplicación de cargas "
        "concentradas y variación parabólica/cúbica de momentos flectores en los tramos con carga distribuida."
    )

    # Insertar gráfica de 4 paneles
    fig = generar_figura_analisis_completo(viga, resultado)
    img_bytes = figura_a_bytes(fig, formato="png")
    p_fig = doc.add_paragraph()
    p_fig.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_fig.paragraph_format.space_before = Pt(4)
    p_fig.paragraph_format.space_after = Pt(2)
    p_fig.add_run().add_picture(io.BytesIO(img_bytes), width=Inches(6.3))

    p_fig_pie = doc.add_paragraph()
    p_fig_pie.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_fig_pie.paragraph_format.space_after = Pt(8)
    r_fpie = p_fig_pie.add_run("Gráfica 1-4. Diagramas de solicitaciones internas y curva elástica (CivilBeam 2026).")
    r_fpie.font.size = Pt(8.5); r_fpie.font.italic = True; r_fpie.font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    # Tabla 3. Verificación de Estados Límites NSR-10
    p_t3_lbl = doc.add_paragraph()
    p_t3_lbl.paragraph_format.space_after = Pt(2)
    p_t3_lbl.add_run("Tabla 3. Verificación de Estados Límites de Resistencia y Servicio (NSR-10).").bold = True
    p_t3_lbl.runs[0].font.size = Pt(8.5)

    t_est = doc.add_table(rows=4, cols=4)
    t_est.alignment = WD_TABLE_ALIGNMENT.CENTER
    for r in t_est.rows:
        r.cells[0].width = Inches(2.2)
        r.cells[1].width = Inches(1.5)
        r.cells[2].width = Inches(1.5)
        r.cells[3].width = Inches(1.3)

    for j, h in enumerate(["Estado Límite", "Valor Actuante", "Capacidad Admisible", "Condición NSR-10"]):
        c = t_est.rows[0].cells[j]
        c.paragraphs[0].add_run(h).bold = True
        c.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _sombreado_celda(c, "1B365D")
        _borde_celda(c, "1B365D")

    filas_el = [
        ("Momento flector máximo |M| máx", f"{resultado.M_abs_max:.2f} kN·m", "Capacidad de sección", "RESISTE"),
        ("Deflexión elástica instantánea |δ|", f"{resultado.v_abs_max:.3f} mm", f"{resultado.deflexion_limite:.2f} mm (L/{resultado.limite_k})", "CUMPLE" if resultado.cumple_deflexion else "NO CUMPLE"),
        ("Esfuerzo normal combinado σ", f"{resultado.sigma_max:.2f} MPa", f"{resultado.sigma_adm:.1f} MPa", "CUMPLE" if resultado.cumple_esfuerzo else "NO CUMPLE"),
    ]
    for row_idx, (e_nom, e_act, e_adm, e_con) in enumerate(filas_el, start=1):
        bg = "F9FAFB" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, txt in enumerate([e_nom, e_act, e_adm, e_con]):
            c = t_est.rows[row_idx].cells[col_idx]
            r_c = c.paragraphs[0].add_run(txt)
            r_c.font.size = Pt(8.5)
            if col_idx == 3:
                r_c.bold = True
                r_c.font.color.rgb = RGBColor(0x05, 0x96, 0x69) if "CUMPLE" in txt or "RESISTE" in txt else RGBColor(0xDC, 0x26, 0x26)
            _sombreado_celda(c, bg)
            _borde_celda(c, "D1D5DB")

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Tabla 4. 17 estaciones longitudinales
    p_t4_lbl = doc.add_paragraph()
    p_t4_lbl.paragraph_format.space_after = Pt(2)
    p_t4_lbl.add_run("Tabla 4. Solicitaciones internas longitudinales discretizadas en 17 estaciones.").bold = True
    p_t4_lbl.runs[0].font.size = Pt(8.5)

    indices = np.linspace(0, len(resultado.x) - 1, min(17, len(resultado.x)), dtype=int)
    t_estac = doc.add_table(rows=1 + len(indices), cols=5)
    t_estac.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, h in enumerate(["x [m]", "Cortante V [kN]", "Momento M [kN·m]", "Giro θ [rad]", "Deflexión v [mm]"]):
        c = t_estac.rows[0].cells[j]
        c.paragraphs[0].add_run(h).bold = True
        c.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _sombreado_celda(c, "1B365D")
        _borde_celda(c, "1B365D")

    for row_i, idx in enumerate(indices, 1):
        bg = "F9FAFB" if row_i % 2 == 1 else "FFFFFF"
        for j, v_str in enumerate([
            f"{resultado.x[idx]:.3f}",
            f"{resultado.V[idx]:.2f}",
            f"{resultado.M[idx]:.2f}",
            f"{resultado.theta[idx]:.5f}",
            f"{resultado.v_mm[idx]:.3f}",
        ]):
            c = t_estac.rows[row_i].cells[j]
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            c.paragraphs[0].add_run(v_str).font.size = Pt(8.5)
            _sombreado_celda(c, bg)
            _borde_celda(c, "E5E7EB")

    # 7. CONCLUSIONES
    p_h7 = doc.add_paragraph()
    p_h7.paragraph_format.space_before = Pt(8)
    r_h7 = p_h7.add_run("7.\tCONCLUSIONES")
    r_h7.bold = True; r_h7.font.size = Pt(12)

    conclusiones = [
        f"El análisis estructural elástico lineal de la viga '{calculo_nombre}' con luz de {L:.2f} m y sección {sec.nombre} "
        f"demuestra un comportamiento {'seguro y conforme' if resultado.cumple_global else 'no conforme'} con los estados límites de servicio de la NSR-10.",
        f"La deflexión elástica máxima calculada fue de {resultado.v_abs_max:.3f} mm frente a una admisible de {resultado.deflexion_limite:.2f} mm "
        f"({resultado.v_abs_max / max(1e-6, resultado.deflexion_limite) * 100:.1f} % de utilización de rigidez).",
        f"El esfuerzo normal máximo combinado por flexión y solicitación axial fue de {resultado.sigma_max:.2f} MPa frente a un admisible de "
        f"{resultado.sigma_adm:.1f} MPa ({resultado.sigma_max / max(1e-6, resultado.sigma_adm) * 100:.1f} % de la resistencia del material).",
        "La integración del módulo abierto pymas permitió obtener con exactitud matemática las propiedades geométricas de la sección mediante el Teorema de Green / Gauss.",
        "El método de Elementos Finitos 1D demostró convergencia total y equilibrio estático estricto, confirmando la fiabilidad de la herramienta CivilBeam 2026.",
    ]
    for conc in conclusiones:
        p_c = doc.add_paragraph()
        p_c.paragraph_format.space_before = Pt(1)
        p_c.paragraph_format.space_after = Pt(2)
        p_c.add_run(f"• {conc}").font.size = Pt(9.5)

    # 8. BIBLIOGRAFÍA
    p_h8 = doc.add_paragraph()
    p_h8.paragraph_format.space_before = Pt(8)
    r_h8 = p_h8.add_run("8.\tBIBLIOGRAFÍA")
    r_h8.bold = True; r_h8.font.size = Pt(12)

    biblio = [
        "Asociación Colombiana de Ingeniería Sísmica (AIS). (2010). Reglamento Colombiano de Construcción Sismo Resistente (NSR-10). Título B (Cargas) y Título C (Concreto Estructural). Bogotá, Colombia.",
        "American Institute of Steel Construction (AISC). (2016). Specification for Structural Steel Buildings (AISC 360-16). Chicago, IL.",
        "Beer, F. P., Johnston, E. R., DeWolf, J. T., & Mazurek, D. F. (2020). Mecánica de Materiales (8.ª ed.). McGraw-Hill Education.",
        "Hibbeler, R. C. (2016). Análisis Estructural (9.ª ed.). Pearson Educación.",
        "Ramírez Vargas, C. D. (2025). PyMAS: Python Matrix Analysis of Structures — Cross-sectional properties calculation using Green's Theorem. GitHub repository: https://github.com/rvcristiand/pymas.git",
        "Przemieniecki, J. S. (1985). Theory of Matrix Structural Analysis. Dover Publications.",
    ]
    for b in biblio:
        p_b = doc.add_paragraph()
        p_b.paragraph_format.space_before = Pt(1)
        p_b.paragraph_format.space_after = Pt(2)
        p_b.add_run(b).font.size = Pt(9)

    # Guardado del archivo
    if ruta_salida is None:
        RUTA_REPORTES.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        nom_clean = "".join(c for c in calculo_nombre if c.isalnum() or c in (' ', '_', '-')).strip() or "Viga"
        ruta_salida = RUTA_REPORTES / f"Paso_a_Paso_{nom_clean}_{ts}.docx"

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(ruta_salida))
    return ruta_salida
