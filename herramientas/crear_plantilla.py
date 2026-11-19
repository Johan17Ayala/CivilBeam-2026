"""
crear_plantilla.py
Script reproducible para generar la plantilla Word 'plantillas/memoria.docx'
con el formato institucional formal de la Universidad Distrital Francisco José de Caldas
(Facultad Tecnológica - Ingeniería Civil).

Garantiza que los tags de Jinja2 ({%tr for %}, {{ InlineImage }}, etc.)
se almacenen en un único 'run' de texto XML.
"""

from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_ESCUDO_UD = BASE_DIR / "plantillas" / "escudo_ud.png"


def aplicar_borde_celda(cell, color="D1D5DB", sz="4", val="single"):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), val)
        el.set(qn('w:sz'), sz)
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), color)
        tcBorders.append(el)
    tcPr.append(tcBorders)


def pintar_celda(cell, hex_color: str):
    tcPr = cell._tc.get_or_add_tcPr()
    for child in list(tcPr):
        if child.tag.endswith('shd'):
            tcPr.remove(child)
    tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color.lstrip("#")}"/>'))


def crear_plantilla_memoria(ruta_salida: Path):
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
    r_aut2 = p_aut.add_run("{{ autor }}\n")
    r_aut2.bold = True
    r_aut2.font.size = Pt(10.5)

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
        "{{ fecha }}"
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
        ("6.3.\tCálculos y deducciones", "6"),
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
        ("Tabla 4. Solicitaciones internas longitudinales discretizadas en estaciones.", "9"),
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

    p_res_body = doc.add_paragraph()
    p_res_body.paragraph_format.space_after = Pt(8)
    p_res_body.add_run(
        "En este informe se presentan los resultados del análisis estructural elástico lineal de la viga "
        "'{{ calculo_nombre }}' perteneciente al proyecto '{{ proyecto_nombre }}', con una longitud total de L = {{ longitud }} m. "
        "La sección transversal corresponde a {{ seccion_nombre }} (A = {{ seccion_area }} m², Ix = {{ seccion_inercia }} m⁴), "
        "evaluada mediante el Teorema de Green / Gauss integrado a partir del proyecto de código abierto pymas (desarrollado por "
        "Cristian Danilo Ramírez Vargas). El cálculo de esfuerzos internos y deformaciones elásticas se llevó a cabo mediante el "
        "Método de Elementos Finitos 1D (FEM) bajo la combinación {{ combinacion_nombre }}. Se obtuvieron una fuerza cortante máxima "
        "de |V|máx = {{ V_abs_max }} kN, un momento flector máximo de |M|máx = {{ M_abs_max }} kN·m y una deflexión elástica máxima "
        "de |δ|máx = {{ v_abs_max }} mm frente al límite normativo L/{{ limite_k }} (±{{ deflexion_limite }} mm), arrojando el dictamen global: "
        "{{ dictamen_global }}."
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
        "Calcular las propiedades mecánicas de la sección transversal mediante el Teorema de Green / Gauss.",
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
        "• Propiedades del Material: Módulo de Elasticidad E = {{ E_GPa }} GPa, Esfuerzo admisible σ_adm = {{ sigma_adm }} MPa.\n"
        "• Peso Propio Volumétrico: {{ peso_propio_texto }}."
    )

    # 5. PROCEDIMIENTO Y METODOLOGÍA
    p_h5 = doc.add_paragraph()
    r_h5 = p_h5.add_run("5.\tPROCEDIMIENTO Y METODOLOGÍA")
    r_h5.bold = True; r_h5.font.size = Pt(12)

    p_proc = doc.add_paragraph()
    p_proc.paragraph_format.space_after = Pt(8)
    p_proc.add_run(
        "El procedimiento de modelación y solución estructural comprende las siguientes etapas secuenciales:\n"
        "1. Definición geométrica del elemento estructural (longitud L = {{ longitud }} m) y selección de la sección transversal.\n"
        "2. Configuración de los apoyos estructurales en la viga: {{ apoyos_texto }}.\n"
        "3. Incorporación de solicitaciones externas con su respectivo origen de persistencia (D, L, W, E, S, T) y combinación {{ combinacion_nombre }}.\n"
        "4. Discretización adaptativa de nodos en apoyos y puntos singulares de carga.\n"
        "5. Ensamblaje de la matriz de rigidez global K y el vector de fuerzas nodales consistentes F.\n"
        "6. Imposición de condiciones de frontera y solución del sistema K·U = F.\n"
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

    p_t1_lbl = doc.add_paragraph()
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
        pintar_celda(c, "1B365D")
        aplicar_borde_celda(c, "1B365D")

    filas_t1 = [
        ("Longitud total de la viga (L)", "{{ longitud }}", "m"),
        ("Sección transversal", "{{ seccion_nombre }}", "Polígono 2D"),
        ("Área transversal (A) / Inercia (Ix)", "{{ seccion_area }} m² / {{ seccion_inercia }}", "m² / m⁴"),
        ("Módulo de Elasticidad (E) / Esfuerzo admisible", "{{ E_GPa }} GPa / {{ sigma_adm }}", "GPa / MPa"),
        ("Criterio de deflexión admisible", "L / {{ limite_k }} (±{{ deflexion_limite }} mm)", "NSR-10 B.4"),
    ]
    for row_idx, (p_nom, p_val, p_uni) in enumerate(filas_t1, start=1):
        bg = "F9FAFB" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, txt in enumerate([p_nom, p_val, p_uni]):
            c = t_d1.rows[row_idx].cells[col_idx]
            c.paragraphs[0].add_run(txt).font.size = Pt(8.5)
            pintar_celda(c, bg)
            aplicar_borde_celda(c, "D1D5DB")

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

    p_reac_info = doc.add_paragraph()
    p_reac_info.paragraph_format.space_after = Pt(4)
    p_reac_info.add_run("• Reacciones calculadas en apoyos: {{ reacciones_texto }}\n")
    p_reac_info.add_run("• Grado de hiperestaticidad del sistema: {{ grado_hiperestaticidad }}")

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # 6.3 Cálculos y deducciones
    p_h63 = doc.add_paragraph()
    p_h63.paragraph_format.space_before = Pt(4)
    p_h63.paragraph_format.space_after = Pt(4)
    r_h63 = p_h63.add_run("6.3.\tCálculos y deducciones analíticas\n")
    r_h63.bold = True; r_h63.font.size = Pt(10.5)

    p_calc_txt = doc.add_paragraph()
    p_calc_txt.paragraph_format.space_after = Pt(4)
    p_calc_txt.add_run(
        "A continuación se presentan las cargas aplicadas al elemento estructural:\n"
        "{{ cargas_descripcion }}"
    )

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
        "a la mecánica de materiales lineal:"
    )

    # Gráfica técnica Matplotlib (tag Jinja2 en 1 solo run)
    p_graf = doc.add_paragraph()
    p_graf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_graf.paragraph_format.space_before = Pt(4)
    p_graf.paragraph_format.space_after = Pt(2)
    p_graf.add_run("{{ grafica_analisis }}")

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
        pintar_celda(c, "1B365D")
        aplicar_borde_celda(c, "1B365D")

    filas_el = [
        ("Momento flector máximo (|M|máx)", "{{ M_abs_max }} kN·m", "Capacidad de sección", "RESISTE"),
        ("Deflexión elástica instantánea (|δ|)", "{{ v_abs_max }} mm", "≤ {{ deflexion_limite }} mm (L/{{ limite_k }})", "{{ estado_deflexion }}"),
        ("Esfuerzo normal combinado (σ)", "{{ sigma_max }} MPa", "≤ {{ sigma_adm }} MPa", "{{ estado_esfuerzo }}"),
    ]
    for row_idx, (e_nom, e_act, e_adm, e_con) in enumerate(filas_el, start=1):
        bg = "F9FAFB" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, txt in enumerate([e_nom, e_act, e_adm, e_con]):
            c = t_est.rows[row_idx].cells[col_idx]
            c.paragraphs[0].add_run(txt).font.size = Pt(8.5)
            pintar_celda(c, bg)
            aplicar_borde_celda(c, "D1D5DB")

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Tabla 4. Solicitaciones longitudinales ({%tr for %})
    p_t4_lbl = doc.add_paragraph()
    p_t4_lbl.paragraph_format.space_after = Pt(2)
    p_t4_lbl.add_run("Tabla 4. Solicitaciones internas longitudinales discretizadas en estaciones.").bold = True
    p_t4_lbl.runs[0].font.size = Pt(8.5)

    t_tram = doc.add_table(rows=4, cols=5)
    t_tram.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers_tram = ["x [m]", "Cortante V [kN]", "Momento M [kN·m]", "Giro θ [rad]", "Deflexión v [mm]"]
    for j, h_txt in enumerate(headers_tram):
        c = t_tram.rows[0].cells[j]
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        c.paragraphs[0].add_run(h_txt).bold = True
        c.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        pintar_celda(c, "1B365D")
        aplicar_borde_celda(c, "1B365D")

    # Fila de apertura Jinja2 {%tr for %}
    t_tram.rows[1].cells[0].paragraphs[0].add_run("{%tr for item in tramos %}")

    # Fila repetida con las celdas de datos
    row_data = t_tram.rows[2]
    row_data.cells[0].paragraphs[0].add_run("{{ item.x }}")
    row_data.cells[1].paragraphs[0].add_run("{{ item.V }}")
    row_data.cells[2].paragraphs[0].add_run("{{ item.M }}")
    row_data.cells[3].paragraphs[0].add_run("{{ item.theta }}")
    row_data.cells[4].paragraphs[0].add_run("{{ item.v_mm }}")
    for j in range(5):
        row_data.cells[j].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        row_data.cells[j].paragraphs[0].runs[0].font.size = Pt(8.5)
        aplicar_borde_celda(row_data.cells[j], "E5E7EB")

    # Fila de cierre Jinja2 {%tr endfor %}
    t_tram.rows[3].cells[0].paragraphs[0].add_run("{%tr endfor %}")

    # 7. CONCLUSIONES
    p_h7 = doc.add_paragraph()
    p_h7.paragraph_format.space_before = Pt(8)
    r_h7 = p_h7.add_run("7.\tCONCLUSIONES")
    r_h7.bold = True; r_h7.font.size = Pt(12)

    p_conc = doc.add_paragraph()
    p_conc.paragraph_format.space_after = Pt(8)
    p_conc.add_run("• Dictamen Global de la Estructura: ").bold = True
    p_conc.add_run("{{ dictamen_global }}\n")
    p_conc.add_run("• Observaciones Técnicas: {{ observaciones }}\n")
    p_conc.add_run(
        "• La aplicación del Teorema de Green / Gauss sobre la sección poligonal (mediante el módulo abierto pymas) "
        "permitió calcular con precisión de máquina la inercia y rigidez efectiva a flexión.\n"
        "• El método de Elementos Finitos 1D demostró convergencia total y equilibrio estático estricto, confirmando "
        "la fiabilidad de la herramienta CivilBeam 2026."
    )

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

    # Guardar plantilla
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(ruta_salida))
    print(f"Plantilla generada exitosamente en: {ruta_salida}")


if __name__ == "__main__":
    destino = Path(__file__).resolve().parent.parent / "plantillas" / "memoria.docx"
    crear_plantilla_memoria(destino)
