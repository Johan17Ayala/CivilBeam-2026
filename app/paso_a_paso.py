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
    Genera un documento Word (.docx) profesional con el procedimiento completo
    paso a paso, ecuaciones, sustituciones numéricas, gráfica de diagramas y tabla resumen.
    """
    pasos = generar_pasos_calculo(viga, resultado)
    doc = Document()

    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Encabezado institucional
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_inst = p_inst.add_run("UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS\nFACULTAD TECNOLÓGICA — INGENIERÍA CIVIL — PROGRAMACIÓN II")
    r_inst.bold = True
    r_inst.font.size = Pt(10.5)
    r_inst.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

    p_tit = doc.add_paragraph()
    p_tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_tit = p_tit.add_run("MEMORIA DE CÁLCULO DETALLADA PASO A PASO")
    r_tit.bold = True
    r_tit.font.size = Pt(15)
    r_tit.font.color.rgb = RGBColor(0x0F, 0x4C, 0x81)

    # Tabla de Metadatos
    t_meta = doc.add_table(rows=4, cols=2)
    t_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta = [
        ("Proyecto:", proyecto_nombre),
        ("Elemento / Cálculo:", calculo_nombre),
        ("Ingeniero Responsable:", autor),
        ("Fecha y Hora:", datetime.now().strftime("%d/%m/%Y %H:%M")),
    ]
    for i, (k, v) in enumerate(meta):
        c0, c1 = t_meta.rows[i].cells[0], t_meta.rows[i].cells[1]
        c0.paragraphs[0].add_run(k).bold = True
        c1.paragraphs[0].add_run(v)
        _sombreado_celda(c0, "F2F5F9")
        _borde_celda(c0)
        _borde_celda(c1)

    doc.add_paragraph()

    # Cada uno de los 6 pasos explicados
    for paso in pasos:
        h = doc.add_heading(f"Paso {paso['numero']}: {paso['titulo']}", level=1)
        for run in h.runs:
            run.font.color.rgb = RGBColor(0x0F, 0x4C, 0x81)
            run.font.size = Pt(12.5)

        # Cuadro de ecuaciones teóricas
        t_eq = doc.add_table(rows=1, cols=1)
        t_eq.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell_eq = t_eq.rows[0].cells[0]
        _sombreado_celda(cell_eq, "EBF3FA")
        _borde_celda(cell_eq, "85C1E9")
        p_eq = cell_eq.paragraphs[0]
        r_lbl = p_eq.add_run("Fórmulas aplicadas:\n")
        r_lbl.bold = True
        r_lbl.font.size = Pt(9.5)
        r_lbl.font.color.rgb = RGBColor(0x1B, 0x4F, 0x72)
        for idx_eq, eq in enumerate(paso["ecuaciones"]):
            suf = "\n" if idx_eq < len(paso["ecuaciones"]) - 1 else ""
            r_eq = p_eq.add_run(f"  • {eq}{suf}")
            r_eq.font.size = Pt(9.5)
            r_eq.font.name = "Consolas"

        # Desarrollo numérico
        for linea in paso["desarrollo"]:
            p_lin = doc.add_paragraph()
            p_lin.paragraph_format.space_before = Pt(3)
            p_lin.paragraph_format.space_after = Pt(2)
            r_lin = p_lin.add_run(linea)
            r_lin.font.size = Pt(10)

        # Resultado clave resaltado
        p_res = doc.add_paragraph()
        p_res.paragraph_format.space_before = Pt(3)
        r_res = p_res.add_run(f"▶ Resultado Paso {paso['numero']}: {paso['resultado_clave']}")
        r_res.bold = True
        r_res.font.size = Pt(10)
        r_res.font.color.rgb = RGBColor(0x14, 0x5A, 0x32)

    # Gráfica de Diagramas Estructurales
    h_img = doc.add_heading("Diagramas Estructurales Resultantes (V, M y v)", level=1)
    for run in h_img.runs:
        run.font.color.rgb = RGBColor(0x0F, 0x4C, 0x81)

    fig = generar_figura_analisis_completo(viga, resultado)
    img_bytes = figura_a_bytes(fig, formato="png")
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.add_run().add_picture(io.BytesIO(img_bytes), width=Inches(6.3))

    # Tabla discreta de resultados en estaciones
    h_tab = doc.add_heading("Tabla de Resultados por Estaciones Longitudinales", level=1)
    for run in h_tab.runs:
        run.font.color.rgb = RGBColor(0x0F, 0x4C, 0x81)

    indices = np.linspace(0, len(resultado.x) - 1, min(17, len(resultado.x)), dtype=int)
    t_res = doc.add_table(rows=1 + len(indices), cols=5)
    t_res.alignment = WD_TABLE_ALIGNMENT.CENTER
    encabezados = ["x [m]", "Cortante V [kN]", "Momento M [kN·m]", "Giro θ [rad]", "Deflexión v [mm]"]
    for j, txt in enumerate(encabezados):
        c = t_res.rows[0].cells[j]
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = c.paragraphs[0].add_run(txt)
        r.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _sombreado_celda(c, "0F4C81")
        _borde_celda(c, "0F4C81")

    for row_i, idx in enumerate(indices, 1):
        vals = [
            f"{resultado.x[idx]:.3f}",
            f"{resultado.V[idx]:.2f}",
            f"{resultado.M[idx]:.2f}",
            f"{resultado.theta[idx]:.5f}",
            f"{resultado.v_mm[idx]:.3f}",
        ]
        bg = "F8F9F9" if row_i % 2 == 0 else "FFFFFF"
        for j, v_str in enumerate(vals):
            c = t_res.rows[row_i].cells[j]
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = c.paragraphs[0].add_run(v_str)
            r.font.size = Pt(9)
            _sombreado_celda(c, bg)
            _borde_celda(c, "CCCCCC")

    if ruta_salida is None:
        RUTA_REPORTES.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        nom_clean = "".join(c for c in calculo_nombre if c.isalnum() or c in (' ', '_', '-')).strip() or "Viga"
        ruta_salida = RUTA_REPORTES / f"Paso_a_Paso_{nom_clean}_{ts}.docx"

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(ruta_salida))
    return ruta_salida
