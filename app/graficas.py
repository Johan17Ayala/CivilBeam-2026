"""
graficas.py
Generador de gráficas técnicas con Matplotlib utilizando exclusivamente la API orientada a objetos (Figure).
Evita pyplot global para prevenir colisiones en entornos multihilo como Flet.

Soporta la representación gráfica de los 5 tipos de apoyo (móvil, fijo, empotrado, guiado, elástico),
cargas puntuales/inclinadas, distribuidas uniformes/triangulares/trapezoidales, polinómicas/no lineales,
momentos concentrados y acciones térmicas/reológicas.

Universidad Distrital Francisco José de Caldas - Facultad Tecnológica
Programación II
"""

import io
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
import numpy as np

from app.modelo import ResultadoViga, VigaIsostatica


def _dibujar_apoyo(ax, x_pos: float, tipo: str, detalle: dict, L: float, y_offset_lbl: float = -0.24):
    """Dibuja el símbolo técnico de cada tipo de apoyo estructural y sus reacciones."""
    etq = detalle.get("etiqueta", "")
    rx = detalle.get("Rx", 0.0)
    ry = detalle.get("Ry", 0.0)
    rm = detalle.get("M", 0.0)

    if tipo == "fijo":
        # Triángulo verde articulado fijo (Pin)
        ax.plot(x_pos, -0.07, marker='^', markersize=13, color='#27ae60', clip_on=False)
        ax.plot([x_pos - 0.02 * L, x_pos + 0.02 * L], [-0.14, -0.14], color='#27ae60', linewidth=2, clip_on=False)
        txt = f"{etq} [Fijo]\nRy={ry:.1f} kN"
        if abs(rx) > 1e-2:
            txt += f"\nRx={rx:.1f} kN"
        ax.text(x_pos, y_offset_lbl, txt, ha='center', va='top', fontsize=7.5, color='#1e8449', fontweight='bold')

    elif tipo == "movil":
        # Triángulo azul sobre rodillo/línea (Roller)
        ax.plot(x_pos, -0.06, marker='^', markersize=11, color='#2980b9', clip_on=False)
        ax.plot(x_pos - 0.01 * L, -0.13, marker='o', markersize=4, color='#2980b9', clip_on=False)
        ax.plot(x_pos + 0.01 * L, -0.13, marker='o', markersize=4, color='#2980b9', clip_on=False)
        ax.plot([x_pos - 0.02 * L, x_pos + 0.02 * L], [-0.17, -0.17], color='#2980b9', linewidth=1.8, clip_on=False)
        ax.text(x_pos, y_offset_lbl, f"{etq} [Móvil]\nRy={ry:.1f} kN",
                ha='center', va='top', fontsize=7.5, color='#2471a3', fontweight='bold')

    elif tipo == "empotrado":
        # Pared achurada roja (Fixed)
        ax.plot([x_pos, x_pos], [-0.20, 0.20], color='#c0392b', linewidth=5, clip_on=False)
        lado = -0.025 * L if x_pos <= L / 2.0 else 0.025 * L
        for yh in np.linspace(-0.18, 0.18, 6):
            ax.plot([x_pos, x_pos + lado], [yh, yh - 0.04], color='#c0392b', linewidth=1.3, clip_on=False)
        ha_align = 'left' if x_pos < 0.1 * L else ('right' if x_pos > 0.9 * L else 'center')
        txt = f"{etq} [Empotr.]\nRy={ry:.1f} kN\nM={rm:.1f} kN·m"
        if abs(rx) > 1e-2:
            txt += f"\nRx={rx:.1f} kN"
        ax.text(x_pos, y_offset_lbl, txt, ha=ha_align, va='top', fontsize=7.5, color='#c0392b', fontweight='bold')

    elif tipo == "guiado":
        # Empotramiento guiado / deslizante: bloque rígido que impide giro y transversal, libre en X
        ax.plot([x_pos, x_pos], [-0.16, 0.16], color='#16a085', linewidth=4, clip_on=False)
        ax.plot([x_pos - 0.02 * L, x_pos + 0.02 * L], [-0.17, -0.17], color='#16a085', linewidth=2, clip_on=False)
        ax.plot([x_pos - 0.02 * L, x_pos + 0.02 * L], [0.17, 0.17], color='#16a085', linewidth=2, clip_on=False)
        ax.plot(x_pos - 0.01 * L, -0.20, marker='o', markersize=4, color='#16a085', clip_on=False)
        ax.plot(x_pos + 0.01 * L, -0.20, marker='o', markersize=4, color='#16a085', clip_on=False)
        ha_align = 'left' if x_pos < 0.1 * L else ('right' if x_pos > 0.9 * L else 'center')
        ax.text(x_pos, y_offset_lbl, f"{etq} [Guiado]\nRy={ry:.1f} kN\nM={rm:.1f} kN·m",
                ha=ha_align, va='top', fontsize=7.5, color='#117864', fontweight='bold')

    elif tipo == "elastico":
        # Resorte traslacional/rotacional naranja
        y_coil = np.linspace(-0.02, -0.18, 9)
        dx_coil = np.array([0, 1, -1, 1, -1, 1, -1, 1, 0]) * (0.015 * L)
        ax.plot(x_pos + dx_coil, y_coil, color='#d35400', linewidth=1.8, clip_on=False)
        ax.plot([x_pos - 0.02 * L, x_pos + 0.02 * L], [-0.19, -0.19], color='#d35400', linewidth=2, clip_on=False)
        txt = f"{etq} [Elást.]\nRy={ry:.1f} kN"
        if abs(rm) > 1e-2:
            txt += f"\nM={rm:.1f} kN·m"
        ax.text(x_pos, y_offset_lbl, txt, ha='center', va='top', fontsize=7.5, color='#ba4a00', fontweight='bold')


def generar_figura_analisis_completo(viga: VigaIsostatica, res: ResultadoViga) -> Figure:
    """
    Genera una figura técnica con 4 subgráficos alineados verticalmente:
    1. Esquema estructural (Viga, apoyos de todo tipo y cargas aplicadas)
    2. Diagrama de Fuerza Cortante V(x) [kN]
    3. Diagrama de Momento Flector M(x) [kN·m]
    4. Curva de Deflexión Elástica v(x) [mm]
    """
    fig = Figure(figsize=(10, 11.5), dpi=120)
    fig.patch.set_facecolor('#ffffff')

    axes = fig.subplots(4, 1, sharex=True, gridspec_kw={'height_ratios': [1.35, 1, 1, 1]})
    ax_esq, ax_v, ax_m, ax_def = axes

    L = res.L
    x = res.x

    # -------------------------------------------------------------
    # 1. Esquema Estructural de la Viga
    # -------------------------------------------------------------
    grado_txt = "Isostática" if res.grado_hiperestaticidad == 0 else f"Hiperestática (g={res.grado_hiperestaticidad})"
    titulo = f"Esquema Estructural (L = {L:.2f} m | {grado_txt}) — {res.seccion.nombre}"
    if res.combinacion_usada != "servicio":
        titulo += f" [{res.combinacion_usada.upper()}]"
    ax_esq.set_title(titulo, fontsize=10.5, fontweight='bold', pad=10)
    ax_esq.plot([0, L], [0, 0], color='#2c3e50', linewidth=6, solid_capstyle='butt')

    # Dibujar todos los apoyos
    for i, det in enumerate(res.reacciones_detalle):
        y_off = -0.24 if i % 2 == 0 or len(res.reacciones_detalle) <= 3 else -0.34
        _dibujar_apoyo(ax_esq, det["x"], det["tipo"], det, L, y_offset_lbl=y_off)

    # Calcular escala visual para perfil de cargas distribuidas/polinómicas
    x_dist_eval = np.linspace(0.0, L, 400)
    w_tot = viga._evaluar_w_en_puntos(x_dist_eval, usar_factor=True)
    w_max_ref = max(float(np.max(np.abs(w_tot))), 1.0)

    # Dibujar cargas distribuidas (uniforme, triangular, trapezoidal) con su forma real
    for i, cd in enumerate(viga.cargas_distribuidas):
        xs = np.linspace(cd.x1, cd.x2, 30)
        t = (xs - cd.x1) / max(cd.x2 - cd.x1, 1e-9)
        ws = cd.w1 + (cd.w2 - cd.w1) * t
        ys = 0.04 + 0.22 * (np.abs(ws) / w_max_ref)
        poly_x = np.concatenate([[cd.x1], xs, [cd.x2]])
        poly_y = np.concatenate([[0.0], ys, [0.0]])
        ax_esq.fill(poly_x, poly_y, color='#f39c12', alpha=0.35, hatch='///', edgecolor='#d35400')
        if abs(cd.w1 - cd.w2) < 1e-6:
            lbl_w = f"w={cd.w1:.1f} kN/m [{cd.origen}]"
        else:
            lbl_w = f"w=[{cd.w1:.1f}→{cd.w2:.1f}] [{cd.origen}]"
        ax_esq.text((cd.x1 + cd.x2) / 2.0, float(np.max(ys)) + 0.03, lbl_w,
                    ha='center', va='bottom', fontsize=7.5, color='#d35400', fontweight='bold')

    # Dibujar cargas polinómicas / no lineales con curva suave real
    for i, cp_poly in enumerate(viga.cargas_polinomicas):
        xs = np.linspace(cp_poly.x1, cp_poly.x2, 60)
        ws = cp_poly.evaluar(xs)
        ys = 0.04 + 0.24 * (np.abs(ws) / w_max_ref)
        poly_x = np.concatenate([[cp_poly.x1], xs, [cp_poly.x2]])
        poly_y = np.concatenate([[0.0], ys, [0.0]])
        ax_esq.fill(poly_x, poly_y, color='#1abc9c', alpha=0.35, hatch='..', edgecolor='#117864')
        ax_esq.text((cp_poly.x1 + cp_poly.x2) / 2.0, float(np.max(ys)) + 0.03,
                    f"w_pol(x) [{cp_poly.origen}]",
                    ha='center', va='bottom', fontsize=7.5, color='#117864', fontweight='bold')

    # Dibujar cargas puntuales (vertical y componente horizontal si existe)
    for i, cp in enumerate(viga.cargas_puntuales):
        if abs(cp.P) > 1e-9:
            y_ini = 0.36 if cp.P > 0 else -0.26
            ax_esq.annotate(
                '', xy=(cp.x, 0.0), xytext=(cp.x, y_ini),
                arrowprops=dict(facecolor='#e74c3c', edgecolor='#c0392b', width=2, headwidth=7)
            )
            ax_esq.text(cp.x, 0.38 if cp.P > 0 else -0.35,
                        f"P{i+1}={cp.P:.1f} kN [{cp.origen}]",
                        ha='center', va='bottom', fontsize=7.5, color='#c0392b', fontweight='bold')
        if abs(cp.Px) > 1e-9:
            dx_arr = 0.06 * L * (1 if cp.Px > 0 else -1)
            ax_esq.annotate(
                '', xy=(cp.x, 0.04), xytext=(cp.x - dx_arr, 0.04),
                arrowprops=dict(facecolor='#e67e22', edgecolor='#d35400', width=1.8, headwidth=6)
            )
            ax_esq.text(cp.x - dx_arr * 0.5, 0.08, f"Px={cp.Px:.1f} kN",
                        ha='center', va='bottom', fontsize=7, color='#d35400', fontweight='bold')

    # Dibujar momentos concentrados
    for i, mc in enumerate(viga.momentos_concentrados):
        simbolo = r'$\circlearrowleft$' if mc.M0 >= 0 else r'$\circlearrowright$'
        ax_esq.plot(mc.x, 0.16, marker=simbolo, markersize=18, color='#8e44ad')
        ax_esq.text(mc.x, 0.25, f"M{i+1}={mc.M0:.1f} kN·m [{mc.origen}]",
                    ha='center', va='bottom', fontsize=7.5, color='#8e44ad', fontweight='bold')

    # Banner si hay acciones térmicas / reológicas o fuerza axial significativa
    term = viga.accion_termica
    notas_extra = []
    if abs(term.delta_T_uniforme) > 1e-6:
        notas_extra.append(f"ΔT₀={term.delta_T_uniforme:+.1f}°C")
    if abs(term.delta_T_gradiente) > 1e-6:
        notas_extra.append(f"ΔT_grad={term.delta_T_gradiente:+.1f}°C")
    if abs(term.retraccion_micro) > 1e-6:
        notas_extra.append(f"εsh={term.retraccion_micro:.0f}με")
    if term.fluencia_phi > 1e-6:
        notas_extra.append(f"φ={term.fluencia_phi:.2f} (Eeff={res.E_efectivo_GPa:.1f} GPa)")
    if res.N_abs_max > 1e-2:
        notas_extra.append(f"|N|máx={res.N_abs_max:.2f} kN")
    if notas_extra:
        ax_esq.text(0.01 * L, 0.49, "Térm./Reol./Axial: " + " | ".join(notas_extra),
                    ha='left', va='top', fontsize=7.5, color='#34495e',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#ebf5fb', edgecolor='#85c1e9'))

    ax_esq.set_ylim(-0.52, 0.56)
    ax_esq.set_ylabel("Geometría", fontsize=9)
    ax_esq.grid(True, linestyle=':', alpha=0.6)
    ax_esq.axhline(0, color='gray', linestyle='--', linewidth=0.8)

    # -------------------------------------------------------------
    # 2. Diagrama de Fuerza Cortante V(x)
    # -------------------------------------------------------------
    ax_v.plot(x, res.V, color='#2980b9', linewidth=2, label='V(x)')
    ax_v.fill_between(x, 0, res.V, where=(res.V >= 0), color='#3498db', alpha=0.3)
    ax_v.fill_between(x, 0, res.V, where=(res.V < 0), color='#e74c3c', alpha=0.25)
    ax_v.axhline(0, color='black', linewidth=0.9)
    ax_v.set_ylabel("Cortante V [kN]", fontsize=9, fontweight='bold')
    ax_v.grid(True, linestyle=':', alpha=0.6)

    idx_v = int(np.argmax(np.abs(res.V)))
    ax_v.scatter([res.x_V_max], [res.V[idx_v]], color='#c0392b', zorder=5)
    ax_v.annotate(f"|V|máx = {res.V_abs_max:.2f} kN",
                  xy=(res.x_V_max, res.V[idx_v]),
                  xytext=(10, 10), textcoords='offset points',
                  fontsize=8, fontweight='bold', color='#c0392b',
                  bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8, edgecolor='#c0392b'))

    # -------------------------------------------------------------
    # 3. Diagrama de Momento Flector M(x)
    # -------------------------------------------------------------
    ax_m.plot(x, res.M, color='#27ae60', linewidth=2, label='M(x)')
    ax_m.fill_between(x, 0, res.M, where=(res.M >= 0), color='#2ecc71', alpha=0.3, label='Tracción fibra inf.')
    ax_m.fill_between(x, 0, res.M, where=(res.M < 0), color='#e67e22', alpha=0.3, label='Tracción fibra sup.')
    ax_m.axhline(0, color='black', linewidth=0.9)
    ax_m.set_ylabel("Momento M [kN·m]", fontsize=9, fontweight='bold')
    ax_m.grid(True, linestyle=':', alpha=0.6)

    idx_m = int(np.argmax(np.abs(res.M)))
    ax_m.scatter([res.x_M_max], [res.M[idx_m]], color='#16a085', zorder=5)
    ax_m.annotate(f"|M|máx = {res.M_abs_max:.2f} kN·m (x={res.x_M_max:.2f} m)",
                  xy=(res.x_M_max, res.M[idx_m]),
                  xytext=(10, -15 if res.M[idx_m] > 0 else 10),
                  textcoords='offset points',
                  fontsize=8, fontweight='bold', color='#16a085',
                  bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8, edgecolor='#16a085'))
    ax_m.legend(loc='upper right', fontsize=7.5)

    # -------------------------------------------------------------
    # 4. Curva de Deflexión Elástica v(x)
    # -------------------------------------------------------------
    ax_def.plot(x, res.v_mm, color='#8e44ad', linewidth=2, label='v(x) [mm]')
    ax_def.fill_between(x, 0, res.v_mm, color='#9b59b6', alpha=0.25)
    ax_def.axhline(0, color='black', linewidth=0.9)

    ax_def.axhline(-res.deflexion_limite, color='#e74c3c', linestyle='--', linewidth=1,
                   label=f'Límite L/{res.limite_k} = ±{res.deflexion_limite:.2f} mm')
    ax_def.axhline(res.deflexion_limite, color='#e74c3c', linestyle='--', linewidth=1)

    idx_d = int(np.argmax(np.abs(res.v_mm)))
    ax_def.scatter([res.x_v_max], [res.v_mm[idx_d]], color='#8e44ad', zorder=5)
    ax_def.annotate(f"δmáx = {res.v_abs_max:.3f} mm\n({'CUMPLE' if res.cumple_deflexion else 'FALLA'})",
                    xy=(res.x_v_max, res.v_mm[idx_d]),
                    xytext=(10, -20 if res.v_mm[idx_d] < 0 else 10),
                    textcoords='offset points',
                    fontsize=8, fontweight='bold',
                    color='#27ae60' if res.cumple_deflexion else '#c0392b',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8,
                              edgecolor='#27ae60' if res.cumple_deflexion else '#c0392b'))

    ax_def.set_ylabel("Deflexión [mm]", fontsize=9, fontweight='bold')
    ax_def.set_xlabel("Posición longitudinal x [m]", fontsize=10, fontweight='bold')
    ax_def.set_xlim(-0.04 * L, 1.04 * L)
    ax_def.grid(True, linestyle=':', alpha=0.6)
    ax_def.legend(loc='lower right', fontsize=7.5)

    fig.tight_layout()
    return fig


def generar_figura_comparativa(res1: ResultadoViga, res2: ResultadoViga,
                                etiqueta1: str = "Cálculo A", etiqueta2: str = "Cálculo B") -> Figure:
    """
    Genera una figura comparativa lado a lado superponiendo los momentos y deflexiones
    de dos cálculos para cumplir el requisito de 'Historial y comparación'.
    """
    fig = Figure(figsize=(9, 6), dpi=120)
    fig.patch.set_facecolor('#ffffff')

    ax1, ax2 = fig.subplots(2, 1, sharex=False)

    ax1.plot(res1.x, res1.M, color='#2980b9', linewidth=2, label=f"{etiqueta1} (Mmáx={res1.M_abs_max:.1f} kN·m)")
    ax1.plot(res2.x, res2.M, color='#e67e22', linewidth=2, linestyle='--',
             label=f"{etiqueta2} (Mmáx={res2.M_abs_max:.1f} kN·m)")
    ax1.set_title("Comparación de Momentos Flectores M(x)", fontsize=10, fontweight='bold')
    ax1.set_ylabel("Momento [kN·m]", fontsize=9)
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.legend(loc='upper right', fontsize=8)

    ax2.plot(res1.x, res1.v_mm, color='#2980b9', linewidth=2, label=f"{etiqueta1} (δmáx={res1.v_abs_max:.2f} mm)")
    ax2.plot(res2.x, res2.v_mm, color='#e67e22', linewidth=2, linestyle='--',
             label=f"{etiqueta2} (δmáx={res2.v_abs_max:.2f} mm)")
    ax2.set_title("Comparación de Curvas Elásticas de Deflexión v(x)", fontsize=10, fontweight='bold')
    ax2.set_xlabel("Longitud x [m]", fontsize=9)
    ax2.set_ylabel("Deflexión [mm]", fontsize=9)
    ax2.grid(True, linestyle=':', alpha=0.6)
    ax2.legend(loc='lower right', fontsize=8)

    fig.tight_layout()
    return fig


def figura_a_bytes(fig: Figure, formato: str = "png") -> bytes:
    """Convierte una figura Matplotlib en bytes en memoria para Flet o Word."""
    buf = io.BytesIO()
    fig.savefig(buf, format=formato, bbox_inches='tight', dpi=120)
    buf.seek(0)
    return buf.getvalue()
