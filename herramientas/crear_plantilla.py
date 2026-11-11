"""
crear_plantilla.py
Script reproducible para generar la plantilla Word 'plantillas/memoria.docx'.
Utiliza python-docx para asegurar que los tags de Jinja2 ({%tr for %}, {{ InlineImage }}, etc.)
se almacenen en un único 'run' de texto XML, evitando la fragmentación interna de Word.

Universidad Distrital Francisco José de Caldas - Facultad Tecnológica
Programación II
"""

from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def aplicar_borde_celda(cell, color="CCCCCC", sz="4", val="single"):
    """Aplica bordes discretos a una celda de tabla en Word."""
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


def crear_plantilla_memoria(ruta_salida: Path):
    doc = Document()

    # Configuración de márgenes
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # -------------------------------------------------------------
    # 1. Encabezado Institucional
    # -------------------------------------------------------------
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_inst = p_inst.add_run("UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS\nFACULTAD TECNOLÓGICA — PROYECTO CURRICULAR DE INGENIERÍA CIVIL")
    r_inst.font.name = "Calibri"
    r_inst.font.size = Pt(11)
    r_inst.font.bold = True
    r_inst.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = p_sub.add_run("PROGRAMACIÓN II — SEMESTRE 2026-III — GRUPO 18\n")
    r_sub.font.size = Pt(9.5)
    r_sub.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    # Título Principal
    p_tit = doc.add_paragraph()
    p_tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_tit = p_tit.add_run("MEMORIA DE CÁLCULO ESTRUCTURAL\nANÁLISIS DE VIGAS CON CARGAS ARBITRARIAS")
    r_tit.font.name = "Calibri"
    r_tit.font.size = Pt(16)
    r_tit.font.bold = True
    r_tit.font.color.rgb = RGBColor(0x0F, 0x4C, 0x81)

    doc.add_paragraph() # Espacio

    # -------------------------------------------------------------
    # 2. Metadatos del Proyecto
    # -------------------------------------------------------------
    h1 = doc.add_heading("1. Información General del Proyecto", level=1)
    h1.style.font.color.rgb = RGBColor(0x0F, 0x4C, 0x81)

    t_meta = doc.add_table(rows=4, cols=2)
    t_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_info = [
        ("Proyecto:", "{{ proyecto_nombre }}"),
        ("Cálculo / Elemento:", "{{ calculo_nombre }}"),
        ("Autor / Ingeniero:", "{{ autor }}"),
        ("Fecha de Generación:", "{{ fecha }}")
    ]
    for i, (k, v) in enumerate(meta_info):
        t_meta.rows[i].cells[0].paragraphs[0].add_run(k).bold = True
        t_meta.rows[i].cells[1].paragraphs[0].add_run(v)
        aplicar_borde_celda(t_meta.rows[i].cells[0])
        aplicar_borde_celda(t_meta.rows[i].cells[1])

    doc.add_paragraph()

    # -------------------------------------------------------------
    # 3. Fundamento Teórico y Ecuaciones
    # -------------------------------------------------------------
    h2 = doc.add_heading("2. Fundamento Teórico y Metodología Numérica", level=1)
    h2.style.font.color.rgb = RGBColor(0x0F, 0x4C, 0x81)

    p_teo = doc.add_paragraph()
    p_teo.add_run(
        "El análisis estructural se fundamenta en la teoría clásica de vigas de Euler-Bernoulli para régimen "
        "elástico lineal. Las ecuaciones diferenciales de equilibrio y compatibilidad de deformaciones son:\n\n"
        "  • Fuerza Cortante: V(x) = dM/dx\n"
        "  • Momento Flector: M(x) = E·I · (d²v/dx²)\n"
        "  • Pendiente Elástica: θ(x) = ∫ (M(x) / (E·I)) dx + C₁\n"
        "  • Deflexión Vertical: v(x) = ∫ θ(x) dx + C₂\n\n"
        "La integración de la curvatura elástica se realiza numéricamente mediante el método del trapecio acumulativo "
        "(scipy.integrate.cumulative_trapezoid) sobre una discretización adaptativa vectorizada con NumPy. "
        "Las constantes de integración C₁ y C₂ se resuelven de forma analítica exacta a partir de las condiciones "
        "de frontera de los apoyos. Las propiedades geométricas de la sección transversal provienen de la formulación "
        "poligonal basada en el Teorema de Green / Agrimensor de Gauss del motor pysections."
    )

    doc.add_paragraph()

    # -------------------------------------------------------------
    # 4. Datos de Entrada (Geometría, Material y Sección)
    # -------------------------------------------------------------
    h3 = doc.add_heading("3. Parámetros de Entrada", level=1)
    h3.style.font.color.rgb = RGBColor(0x0F, 0x4C, 0x81)

    p_geom = doc.add_paragraph()
    p_geom.add_run("Geometría y Material:\n").bold = True
    p_geom.add_run(
        "  • Tipo de viga: {{ tipo_viga }}\n"
        "  • Longitud total (L): {{ longitud }} m\n"
        "  • Posición de apoyos: {{ apoyos_texto }}\n"
        "  • Módulo de Elasticidad (E): {{ E_GPa }} GPa\n"
        "  • Esfuerzo admisible (σ_adm): {{ sigma_adm }} MPa\n"
        "  • Límite normativo de deflexión: L / {{ limite_k }} (admisible = {{ deflexion_limite }} mm)\n"
        "  • Peso propio incluido: {{ peso_propio_texto }}\n"
    )

    p_sec = doc.add_paragraph()
    p_sec.add_run("Propiedades de la Sección Transversal (pysections):\n").bold = True
    p_sec.add_run(
        "  • Nombre de la sección: {{ seccion_nombre }}\n"
        "  • Tipo: {{ seccion_tipo }}\n"
        "  • Área (A): {{ seccion_area }} m²\n"
        "  • Momento de Inercia (I): {{ seccion_inercia }} m⁴\n"
        "  • Altura total (h): {{ seccion_altura }} m\n"
        "  • Módulo de sección elástico crítico (W_mín): {{ seccion_w_min }} m³\n"
    )

    p_cargas = doc.add_paragraph()
    p_cargas.add_run("Cargas Aplicadas:\n").bold = True
    p_cargas.add_run("{{ cargas_descripcion }}")

    doc.add_paragraph()

    # -------------------------------------------------------------
    # 5. Resultados del Análisis y Reacciones
    # -------------------------------------------------------------
    h4 = doc.add_heading("4. Reacciones y Solicitaciones Extremas", level=1)
    h4.style.font.color.rgb = RGBColor(0x0F, 0x4C, 0x81)

    t_res = doc.add_table(rows=5, cols=3)
    t_res.alignment = WD_TABLE_ALIGNMENT.CENTER
    encabezados_res = ["Parámetro", "Valor", "Ubicación"]
    for j, enc in enumerate(encabezados_res):
        c = t_res.rows[0].cells[j]
        c.paragraphs[0].add_run(enc).bold = True
        aplicar_borde_celda(c)

    filas_res = [
        ("Reacciones en Apoyos", "{{ reacciones_texto }}", "En apoyos"),
        ("Cortante Máximo Absoluto (|V|máx)", "{{ V_abs_max }} kN", "x = {{ x_V_max }} m"),
        ("Momento Máximo Absoluto (|M|máx)", "{{ M_abs_max }} kN·m", "x = {{ x_M_max }} m"),
        ("Deflexión Máxima Absoluta (|δ|máx)", "{{ v_abs_max }} mm", "x = {{ x_v_max }} m"),
    ]
    for i, fila in enumerate(filas_res, start=1):
        for j, val in enumerate(fila):
            c = t_res.rows[i].cells[j]
            c.paragraphs[0].add_run(val)
            aplicar_borde_celda(c)

    doc.add_paragraph()

    # -------------------------------------------------------------
    # 6. Diagramas Estructurales (Gráfica InlineImage)
    # -------------------------------------------------------------
    h5 = doc.add_heading("5. Diagramas Técnicos de Solicitaciones y Deformación", level=1)
    h5.style.font.color.rgb = RGBColor(0x0F, 0x4C, 0x81)

    p_graf = doc.add_paragraph()
    p_graf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    # Tag de Jinja2 en un solo run para insertar la imagen generada con Matplotlib
    p_graf.add_run("{{ grafica_analisis }}")

    doc.add_paragraph()

    # -------------------------------------------------------------
    # 7. Tabla de Resultados Discretizados por Tramos ({%tr for %})
    # -------------------------------------------------------------
    h6 = doc.add_heading("6. Tabla de Discretización y Esfuerzos por Secciones", level=1)
    h6.style.font.color.rgb = RGBColor(0x0F, 0x4C, 0x81)

    p_desc_tab = doc.add_paragraph()
    p_desc_tab.add_run("A continuación se presenta la envolvente de solicitaciones evaluada a lo largo del vano:")

    # Tabla con Jinja2 {%tr %} para iteración de filas
    t_tram = doc.add_table(rows=4, cols=5)
    t_tram.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers_tram = ["x [m]", "Cortante V [kN]", "Momento M [kN·m]", "Giro θ [rad]", "Deflexión v [mm]"]
    for j, h_txt in enumerate(headers_tram):
        c = t_tram.rows[0].cells[j]
        c.paragraphs[0].add_run(h_txt).bold = True
        aplicar_borde_celda(c)

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
        aplicar_borde_celda(row_data.cells[j])

    # Fila de cierre Jinja2 {%tr endfor %}
    t_tram.rows[3].cells[0].paragraphs[0].add_run("{%tr endfor %}")

    doc.add_paragraph()

    # -------------------------------------------------------------
    # 8. Verificaciones Normativas y Conclusión (CUMPLE / NO CUMPLE)
    # -------------------------------------------------------------
    h7 = doc.add_heading("7. Chequeos Normativos y Conclusiones", level=1)
    h7.style.font.color.rgb = RGBColor(0x0F, 0x4C, 0x81)

    t_chk = doc.add_table(rows=3, cols=4)
    t_chk.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers_chk = ["Estado Límite", "Valor Calculado", "Límite Admisible", "Diagnóstico"]
    for j, h_txt in enumerate(headers_chk):
        c = t_chk.rows[0].cells[j]
        c.paragraphs[0].add_run(h_txt).bold = True
        aplicar_borde_celda(c)

    filas_chk = [
        ("Resistencia a Flexión (σ_máx)", "{{ sigma_max }} MPa", "≤ {{ sigma_adm }} MPa", "{{ estado_esfuerzo }}"),
        ("Servicio / Deflexión (|δ|máx)", "{{ v_abs_max }} mm", "≤ {{ deflexion_limite }} mm (L/{{ limite_k }})", "{{ estado_deflexion }}"),
    ]
    for i, fila in enumerate(filas_chk, start=1):
        for j, val in enumerate(fila):
            c = t_chk.rows[i].cells[j]
            c.paragraphs[0].add_run(val)
            aplicar_borde_celda(c)

    doc.add_paragraph()

    p_conc = doc.add_paragraph()
    p_conc.add_run("Dictamen Global de la Estructura: ").bold = True
    p_conc.add_run("{{ dictamen_global }}\n")
    p_conc.add_run("Observaciones: {{ observaciones }}")

    # Guardar plantilla
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(ruta_salida))
    print(f"Plantilla generada exitosamente en: {ruta_salida}")


if __name__ == "__main__":
    destino = Path(__file__).resolve().parent.parent / "plantillas" / "memoria.docx"
    crear_plantilla_memoria(destino)
