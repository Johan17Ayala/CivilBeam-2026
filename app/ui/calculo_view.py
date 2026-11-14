"""
calculo_view.py
Vista principal de Cálculo y Diseño Estructural de Vigas en Flet.
Soporta los 5 tipos de apoyos (móvil, fijo, empotrado, guiado, elástico),
todos los tipos geométricos de carga (puntual/inclinada, uniforme, triangular,
trapezoidal, momento, polinómica), clasificación por origen (D, L, W, E, S, T),
combinaciones NSR-10 y acciones térmicas/reológicas.

Universidad Distrital Francisco José de Caldas - Facultad Tecnológica
Programación II
"""

import os
import base64
import flet as ft
from app.modelo import (
    analizar_viga_desde_diccionario,
    TIPOS_APOYO,
    ORIGENES_CARGA,
    COMBINACIONES_CARGA,
)
from app.graficas import generar_figura_analisis_completo, figura_a_bytes
from app.db import guardar_calculo
from app.reporte import generar_memoria_word


class CalculoView(ft.Container):
    def __init__(
        self,
        page: ft.Page,
        al_guardar_callback=None,
        al_calcular_callback=None,
        al_abrir_paso_a_paso_callback=None,
    ):
        super().__init__(expand=True)
        self.pagina = page
        self.al_guardar_callback = al_guardar_callback
        self.al_calcular_callback = al_calcular_callback
        self.al_abrir_paso_a_paso_callback = al_abrir_paso_a_paso_callback

        self.viga_actual = None
        self.resultado_actual = None
        self.ultima_ruta_word = None
        self.apoyos_memoria = []
        self.cargas_memoria = []

        self._construir_interfaz()

    def _construir_interfaz(self):
        # 1. Identificación del Proyecto
        self.txt_proyecto = ft.TextField(label="Nombre del Proyecto", value="Edificio Torres de la 26", width=260)
        self.txt_calculo = ft.TextField(label="Elemento / Cálculo", value="Viga Principal V-101", width=240)
        self.txt_autor = ft.TextField(label="Ingeniero Calculista", value="Johan Ayala", width=220)

        # 2. Geometría y Apoyos
        self.dd_tipo_viga = ft.Dropdown(
            label="Plantilla / Tipo de Viga",
            width=280,
            value="simplemente_apoyada",
            options=[
                ft.dropdown.Option("simplemente_apoyada", "Simplemente Apoyada (Fijo + Móvil)"),
                ft.dropdown.Option("voladizo", "Voladizo Empotrado (x = 0)"),
                ft.dropdown.Option("doble_empotrada", "Doble Empotramiento (Hiperestática)"),
                ft.dropdown.Option("empotrada_movil", "Empotrada + Apoyo Móvil"),
                ft.dropdown.Option("guiada_movil", "Empotramiento Guiado + Apoyo Móvil"),
                ft.dropdown.Option("elastica", "Viga sobre Apoyos Elásticos"),
                ft.dropdown.Option("personalizado", "Personalizado (Lista libre de apoyos)"),
            ],
            on_select=self._on_cambio_tipo_viga
        )
        self.txt_L = ft.TextField(label="Longitud L", value="8.00", suffix=ft.Text("m"), width=140)

        # Controles para agregar apoyos individuales
        self.dd_tipo_apoyo = ft.Dropdown(
            label="Tipo de Apoyo",
            width=270,
            value="movil",
            options=[
                ft.dropdown.Option("movil", "Apoyo Simple / Móvil (Roller -> Ry)"),
                ft.dropdown.Option("fijo", "Apoyo Articulado / Fijo (Pin -> Rx, Ry)"),
                ft.dropdown.Option("empotrado", "Empotramiento Rígido (Rx, Ry, M)"),
                ft.dropdown.Option("guiado", "Empotramiento Guiado / Deslizante (Ry, M)"),
                ft.dropdown.Option("elastico", "Apoyo Elástico (Resorte ky, kθ)"),
            ],
            on_select=self._on_cambio_tipo_apoyo
        )
        self.txt_apoyo_x = ft.TextField(label="Posición x", value="0.00", suffix=ft.Text("m"), width=120)
        self.txt_apoyo_ky = ft.TextField(label="Rigidez ky", value="5000", suffix=ft.Text("kN/m"), width=140, visible=False)
        self.txt_apoyo_kth = ft.TextField(label="Rigidez kθ", value="0", suffix=ft.Text("kN·m/rad"), width=155, visible=False)
        self.btn_agregar_apoyo = ft.FilledButton(
            "Agregar Apoyo", icon=ft.Icons.ADD_LOCATION_ALT, on_click=self._agregar_apoyo
        )
        self.col_lista_apoyos = ft.Column(spacing=4)

        # Inicializar apoyos por defecto (simplemente apoyada 0 - 8 m)
        self.apoyos_memoria = [
            {"tipo": "fijo", "x": 0.0, "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
            {"tipo": "movil", "x": 8.0, "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
        ]
        self._refrescar_lista_apoyos_ui()

        # 3. Sección Transversal (pysections)
        self.dd_tipo_seccion = ft.Dropdown(
            label="Sección Transversal (pysections)",
            width=260,
            value="rectangular",
            options=[
                ft.dropdown.Option("rectangular", "Rectangular de Concreto (Deck)"),
                ft.dropdown.Option("perfil_i", "Perfil I de Acero (PerfilI)"),
                ft.dropdown.Option("bulb_tee", "Viga Puente Bulb-Tee (pysections)")
            ],
            on_select=self._on_cambio_tipo_seccion
        )

        self.txt_b_rect = ft.TextField(label="Base (b)", value="0.30", suffix=ft.Text("m"), width=130)
        self.txt_h_rect = ft.TextField(label="Altura (h)", value="0.60", suffix=ft.Text("m"), width=130)

        self.txt_bf_i = ft.TextField(label="Ancho ala (bf)", value="0.25", suffix=ft.Text("m"), width=130, visible=False)
        self.txt_d_i = ft.TextField(label="Altura total (d)", value="0.45", suffix=ft.Text("m"), width=130, visible=False)
        self.txt_tf_i = ft.TextField(label="Espesor ala (tf)", value="0.018", suffix=ft.Text("m"), width=130, visible=False)
        self.txt_tw_i = ft.TextField(label="Espesor alma (tw)", value="0.010", suffix=ft.Text("m"), width=130, visible=False)

        self.fila_params_seccion = ft.Row([
            self.txt_b_rect, self.txt_h_rect,
            self.txt_bf_i, self.txt_d_i, self.txt_tf_i, self.txt_tw_i
        ], wrap=True)

        # Material y Criterios Normativos
        self.txt_E = ft.TextField(label="Módulo Elasticidad E", value="24.0", suffix=ft.Text("GPa"), width=160)
        self.txt_sigma_adm = ft.TextField(label="Esfuerzo admisible σ", value="180.0", suffix=ft.Text("MPa"), width=160)
        self.dd_limite_def = ft.Dropdown(
            label="Límite Deflexión",
            width=160,
            value="360",
            options=[
                ft.dropdown.Option("180", "L / 180 (General)"),
                ft.dropdown.Option("240", "L / 240 (Pisos)"),
                ft.dropdown.Option("360", "L / 360 (NSR-10)"),
                ft.dropdown.Option("480", "L / 480 (Sensible)")
            ]
        )
        self.chk_peso_propio = ft.Checkbox(label="Incluir peso propio automático [D] (γ = 24 kN/m³)", value=True)

        # 4. Cargas (Geometría + Origen + Combinación + Térmica/Reológica)
        self.dd_combinacion = ft.Dropdown(
            label="Combinación de Carga (NSR-10)",
            width=340,
            value="servicio",
            options=[ft.dropdown.Option(k, v["nombre"]) for k, v in COMBINACIONES_CARGA.items()]
        )
        self.dd_origen_carga = ft.Dropdown(
            label="Origen / Naturaleza",
            width=200,
            value="L",
            options=[ft.dropdown.Option(k, v) for k, v in ORIGENES_CARGA.items()]
        )

        self.dd_tipo_carga = ft.Dropdown(
            label="Geometría de Carga",
            width=250,
            value="puntual",
            options=[
                ft.dropdown.Option("puntual", "Puntual / Concentrada (P, Px)"),
                ft.dropdown.Option("uniforme", "Distribuida Uniforme (w)"),
                ft.dropdown.Option("triangular", "Distribuida Triangular (0→w)"),
                ft.dropdown.Option("trapezoidal", "Distribuida Trapezoidal (w₁→w₂)"),
                ft.dropdown.Option("momento", "Momento Concentrado (M₀)"),
                ft.dropdown.Option("polinomica", "No Lineal / Polinómica w(u)"),
            ],
            on_select=self._on_cambio_tipo_carga
        )

        self.txt_c_val1 = ft.TextField(label="Vertical P", value="35.0", suffix=ft.Text("kN"), width=130)
        self.txt_c_val2 = ft.TextField(label="Horizontal Px", value="0.0", suffix=ft.Text("kN"), width=135, visible=True)
        self.txt_c_pos1 = ft.TextField(label="Posición x", value="4.0", suffix=ft.Text("m"), width=120)
        self.txt_c_pos2 = ft.TextField(label="Fin x₂", value="8.0", suffix=ft.Text("m"), width=120, visible=False)

        # Coeficientes para carga polinómica w(u) = a0 + a1*u + a2*u^2 + a3*u^3
        self.txt_poly_a0 = ft.TextField(label="a₀ (const.)", value="10.0", width=110, visible=False)
        self.txt_poly_a1 = ft.TextField(label="a₁ (·u)", value="0.0", width=110, visible=False)
        self.txt_poly_a2 = ft.TextField(label="a₂ (·u²)", value="1.5", width=110, visible=False)
        self.txt_poly_a3 = ft.TextField(label="a₃ (·u³)", value="0.0", width=110, visible=False)

        self.btn_agregar_carga = ft.FilledButton("Agregar Carga", icon=ft.Icons.ADD, on_click=self._agregar_carga)
        self.col_lista_cargas = ft.Column(spacing=4)

        # Acciones Térmicas y Reológicas
        self.txt_dT0 = ft.TextField(label="ΔT₀ Uniforme", value="0.0", suffix=ft.Text("°C"), width=140)
        self.txt_dTgrad = ft.TextField(label="Gradiente ΔT (inf-sup)", value="0.0", suffix=ft.Text("°C"), width=175)
        self.txt_retraccion = ft.TextField(label="Retracción εsh", value="0", suffix=ft.Text("με"), width=145)
        self.txt_fluencia = ft.TextField(label="Fluencia lenta φ", value="0.0", width=140)

        # Cargas iniciales de ejemplo
        self.cargas_memoria = [
            {"tipo": "distribuida", "subtipo": "uniforme", "w1": 18.0, "w2": 18.0, "x1": 0.0, "x2": 8.0, "origen": "D"},
            {"tipo": "puntual", "P": 45.0, "Px": 0.0, "x": 4.0, "origen": "L"}
        ]
        self._refrescar_lista_cargas_ui()

        # 5. Botones de Acción
        self.btn_calcular = ft.FilledButton(
            "CALCULAR VIGA", icon=ft.Icons.PLAY_ARROW_ROUNDED,
            style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
            on_click=self._ejecutar_calculo
        )
        self.btn_guardar_bd = ft.OutlinedButton(
            "Guardar en SQLite", icon=ft.Icons.SAVE,
            on_click=self._guardar_en_bd, disabled=True
        )
        self.btn_generar_word = ft.OutlinedButton(
            "Generar Memoria Word (.docx)", icon=ft.Icons.DESCRIPTION,
            on_click=self._generar_word, disabled=True
        )
        self.btn_abrir_word = ft.OutlinedButton(
            "Abrir Último Word", icon=ft.Icons.OPEN_IN_NEW,
            on_click=self._abrir_ultimo_word, disabled=True
        )
        self.btn_ver_paso_a_paso = ft.OutlinedButton(
            "Ver Cálculo Paso a Paso", icon=ft.Icons.FORMAT_LIST_NUMBERED,
            on_click=self._abrir_paso_a_paso, disabled=True
        )
        self.chk_auto_word = ft.Checkbox(
            label="Generar memoria Word (.docx) automáticamente al calcular", value=True
        )
        self.txt_ruta_word = ft.Text(
            "La memoria Word (.docx) se generará automáticamente en la carpeta 'reportes/'.",
            size=12, color=ft.Colors.BLUE_800, selectable=True
        )

        # 6. Resultados
        self.txt_res_reacciones = ft.Text("—", size=12.5, weight=ft.FontWeight.BOLD)
        self.txt_res_cortante = ft.Text("—", size=12.5, weight=ft.FontWeight.BOLD)
        self.txt_res_momento = ft.Text("—", size=12.5, weight=ft.FontWeight.BOLD)
        self.txt_res_axial = ft.Text("—", size=12.5, weight=ft.FontWeight.BOLD)
        self.txt_res_deflexion = ft.Text("—", size=12.5, weight=ft.FontWeight.BOLD)
        self.txt_res_esfuerzo = ft.Text("—", size=12.5, weight=ft.FontWeight.BOLD)
        self.chip_estado = ft.Chip(label=ft.Text("SIN CALCULAR"), bgcolor=ft.Colors.GREY_300)

        # 7. Gráfica
        self.img_grafica = ft.Image(src="", width=780, fit="contain", visible=False)
        self.txt_espera_grafica = ft.Text(
            "Configure los apoyos, sección y cargas, y presione 'CALCULAR VIGA'.",
            italic=True, color=ft.Colors.GREY_600
        )

        # Cards de interfaz
        card_proyecto = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("1. Identificación del Proyecto", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900),
                    ft.Row([self.txt_proyecto, self.txt_calculo, self.txt_autor], wrap=True)
                ]), padding=15
            )
        )

        card_geometria = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("2. Geometría y Apoyos Estructurales", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900),
                    ft.Row([self.dd_tipo_viga, self.txt_L], wrap=True),
                    ft.Divider(),
                    ft.Text("Editor de Apoyos (Móvil, Fijo, Empotramiento, Guiado, Elástico):", size=13, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        self.dd_tipo_apoyo, self.txt_apoyo_x, self.txt_apoyo_ky, self.txt_apoyo_kth,
                        self.btn_agregar_apoyo
                    ], wrap=True),
                    self.col_lista_apoyos,
                ]), padding=15
            )
        )

        card_seccion = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("3. Sección Transversal y Material (pysections)", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900),
                    ft.Row([self.dd_tipo_seccion, self.txt_E, self.txt_sigma_adm, self.dd_limite_def], wrap=True),
                    self.fila_params_seccion,
                    self.chk_peso_propio
                ]), padding=15
            )
        )

        card_cargas = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("4. Cargas, Orígenes (D, L, W, E, S, T) y Combinación", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900),
                    ft.Row([self.dd_combinacion, self.dd_origen_carga], wrap=True),
                    ft.Row([
                        self.dd_tipo_carga,
                        self.txt_c_val1, self.txt_c_val2,
                        self.txt_poly_a0, self.txt_poly_a1, self.txt_poly_a2, self.txt_poly_a3,
                        self.txt_c_pos1, self.txt_c_pos2,
                        self.btn_agregar_carga
                    ], wrap=True),
                    ft.Divider(),
                    ft.Text("Acciones Térmicas y Reológicas (Opcionales):", size=13, weight=ft.FontWeight.BOLD),
                    ft.Row([self.txt_dT0, self.txt_dTgrad, self.txt_retraccion, self.txt_fluencia], wrap=True),
                    ft.Divider(),
                    ft.Text("Cargas registradas en el modelo:", weight=ft.FontWeight.BOLD),
                    self.col_lista_cargas
                ]), padding=15
            )
        )

        card_acciones = ft.Column([
            ft.Row([
                self.btn_calcular,
                self.btn_guardar_bd,
                self.btn_ver_paso_a_paso,
                self.btn_generar_word,
                self.btn_abrir_word,
            ], spacing=12, wrap=True),
            ft.Row([self.chk_auto_word, self.txt_ruta_word], wrap=True, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ], spacing=6)

        card_resultados = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("Resultados y Chequeo Normativo", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900),
                        self.chip_estado
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(),
                    ft.Column([ft.Text("Reacciones en Apoyos:", size=11, color=ft.Colors.GREY_700), self.txt_res_reacciones]),
                    ft.ResponsiveRow([
                        ft.Column([ft.Text("Cortante Máximo |V|:", size=11, color=ft.Colors.GREY_700), self.txt_res_cortante], col={"sm": 6, "md": 4}),
                        ft.Column([ft.Text("Momento Máximo |M|:", size=11, color=ft.Colors.GREY_700), self.txt_res_momento], col={"sm": 6, "md": 4}),
                        ft.Column([ft.Text("Fuerza Axial Máx |N|:", size=11, color=ft.Colors.GREY_700), self.txt_res_axial], col={"sm": 6, "md": 4}),
                        ft.Column([ft.Text("Deflexión Máxima δ:", size=11, color=ft.Colors.GREY_700), self.txt_res_deflexion], col={"sm": 6, "md": 6}),
                        ft.Column([ft.Text("Esfuerzo Combinado Máx σ:", size=11, color=ft.Colors.GREY_700), self.txt_res_esfuerzo], col={"sm": 6, "md": 6}),
                    ])
                ]), padding=15
            )
        )

        card_grafica = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Diagramas Estructurales (Esquema, V, M y v)", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900),
                    self.txt_espera_grafica,
                    self.img_grafica
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=15
            )
        )

        self.content = ft.ListView([
            card_proyecto,
            card_geometria,
            card_seccion,
            card_cargas,
            card_acciones,
            card_resultados,
            card_grafica
        ], spacing=15, padding=15)

    # -------------------------------------------------------------
    # Controladores de Apoyos
    # -------------------------------------------------------------
    def _on_cambio_tipo_viga(self, e):
        try:
            L = float(self.txt_L.value or 8.0)
        except Exception:
            L = 8.0

        preset = self.dd_tipo_viga.value
        if preset == "simplemente_apoyada":
            self.apoyos_memoria = [
                {"tipo": "fijo", "x": 0.0, "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
                {"tipo": "movil", "x": L, "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
            ]
        elif preset == "voladizo":
            self.apoyos_memoria = [
                {"tipo": "empotrado", "x": 0.0, "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
            ]
        elif preset == "doble_empotrada":
            self.apoyos_memoria = [
                {"tipo": "empotrado", "x": 0.0, "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
                {"tipo": "empotrado", "x": L, "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
            ]
        elif preset == "empotrada_movil":
            self.apoyos_memoria = [
                {"tipo": "empotrado", "x": 0.0, "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
                {"tipo": "movil", "x": L, "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
            ]
        elif preset == "guiada_movil":
            self.apoyos_memoria = [
                {"tipo": "guiado", "x": 0.0, "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
                {"tipo": "movil", "x": L, "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
            ]
        elif preset == "elastica":
            self.apoyos_memoria = [
                {"tipo": "elastico", "x": 0.0, "ky": 5000.0, "ktheta": 0.0, "kx": 0.0},
                {"tipo": "elastico", "x": L, "ky": 5000.0, "ktheta": 0.0, "kx": 0.0},
            ]
        self._refrescar_lista_apoyos_ui()
        self.pagina.update()

    def _on_cambio_tipo_apoyo(self, e):
        es_elastico = (self.dd_tipo_apoyo.value == "elastico")
        self.txt_apoyo_ky.visible = es_elastico
        self.txt_apoyo_kth.visible = es_elastico
        self.pagina.update()

    def _agregar_apoyo(self, e):
        try:
            tipo = self.dd_tipo_apoyo.value
            x = float(self.txt_apoyo_x.value)
            L = float(self.txt_L.value)
            if x < 0 or x > L:
                raise ValueError(f"Posición x={x} debe estar entre 0 y {L} m.")
            ky = float(self.txt_apoyo_ky.value or 0.0) if tipo == "elastico" else 0.0
            kth = float(self.txt_apoyo_kth.value or 0.0) if tipo == "elastico" else 0.0
            if tipo == "elastico" and ky <= 0 and kth <= 0:
                raise ValueError("Un apoyo elástico requiere rigidez ky > 0 o kθ > 0.")

            self.apoyos_memoria.append({"tipo": tipo, "x": x, "ky": ky, "ktheta": kth, "kx": 0.0})
            self.dd_tipo_viga.value = "personalizado"
            self._refrescar_lista_apoyos_ui()
            self.pagina.update()
        except Exception as ex:
            self._mostrar_error(f"Error en apoyo: {ex}")

    def _eliminar_apoyo(self, index):
        if 0 <= index < len(self.apoyos_memoria):
            self.apoyos_memoria.pop(index)
            self.dd_tipo_viga.value = "personalizado"
            self._refrescar_lista_apoyos_ui()
            self.pagina.update()

    def _refrescar_lista_apoyos_ui(self):
        self.col_lista_apoyos.controls.clear()
        if not self.apoyos_memoria:
            self.col_lista_apoyos.controls.append(
                ft.Text("Sin apoyos definidos. Agregue al menos un apoyo.", italic=True, size=12, color=ft.Colors.RED_600)
            )
            return

        for i, ap in enumerate(self.apoyos_memoria):
            nom = TIPOS_APOYO.get(ap["tipo"], ap["tipo"])
            extra = ""
            if ap["tipo"] == "elastico":
                extra = f" (ky={ap['ky']:.0f} kN/m, kθ={ap['ktheta']:.0f} kN·m/rad)"
            desc = f"• Apoyo A{i+1}: {nom} en x = {ap['x']:.2f} m{extra}"
            btn_del = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                tooltip="Eliminar apoyo",
                on_click=lambda e, idx=i: self._eliminar_apoyo(idx)
            )
            self.col_lista_apoyos.controls.append(
                ft.Row([ft.Text(desc, size=12.5, expand=True), btn_del], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )

    # -------------------------------------------------------------
    # Controladores de Sección y Cargas
    # -------------------------------------------------------------
    def _on_cambio_tipo_seccion(self, e):
        tipo = self.dd_tipo_seccion.value
        es_rect = (tipo == "rectangular")
        es_i = (tipo == "perfil_i")

        self.txt_b_rect.visible = es_rect
        self.txt_h_rect.visible = es_rect

        self.txt_bf_i.visible = es_i
        self.txt_d_i.visible = es_i
        self.txt_tf_i.visible = es_i
        self.txt_tw_i.visible = es_i
        self.pagina.update()

    def _on_cambio_tipo_carga(self, e):
        tipo = self.dd_tipo_carga.value
        # Ocultar polinómicos por defecto
        for ctrl in (self.txt_poly_a0, self.txt_poly_a1, self.txt_poly_a2, self.txt_poly_a3):
            ctrl.visible = False

        if tipo == "puntual":
            self.txt_c_val1.label = "Vertical P"
            self.txt_c_val1.suffix.value = "kN"
            self.txt_c_val1.visible = True
            self.txt_c_val2.label = "Horizontal Px"
            self.txt_c_val2.suffix.value = "kN"
            self.txt_c_val2.value = "0.0"
            self.txt_c_val2.visible = True
            self.txt_c_pos1.label = "Posición x"
            self.txt_c_pos2.visible = False
        elif tipo == "uniforme":
            self.txt_c_val1.label = "Intensidad w"
            self.txt_c_val1.suffix.value = "kN/m"
            self.txt_c_val1.visible = True
            self.txt_c_val2.visible = False
            self.txt_c_pos1.label = "Inicio x₁"
            self.txt_c_pos2.label = "Fin x₂"
            self.txt_c_pos2.visible = True
        elif tipo == "triangular":
            self.txt_c_val1.label = "Inicio w₁"
            self.txt_c_val1.suffix.value = "kN/m"
            self.txt_c_val1.value = "0.0"
            self.txt_c_val1.visible = True
            self.txt_c_val2.label = "Final w₂"
            self.txt_c_val2.suffix.value = "kN/m"
            self.txt_c_val2.value = "25.0"
            self.txt_c_val2.visible = True
            self.txt_c_pos1.label = "Inicio x₁"
            self.txt_c_pos2.label = "Fin x₂"
            self.txt_c_pos2.visible = True
        elif tipo == "trapezoidal":
            self.txt_c_val1.label = "Carga inicial w₁"
            self.txt_c_val1.suffix.value = "kN/m"
            self.txt_c_val1.visible = True
            self.txt_c_val2.label = "Carga final w₂"
            self.txt_c_val2.suffix.value = "kN/m"
            self.txt_c_val2.visible = True
            self.txt_c_pos1.label = "Inicio x₁"
            self.txt_c_pos2.label = "Fin x₂"
            self.txt_c_pos2.visible = True
        elif tipo == "momento":
            self.txt_c_val1.label = "Momento M₀"
            self.txt_c_val1.suffix.value = "kN·m"
            self.txt_c_val1.visible = True
            self.txt_c_val2.visible = False
            self.txt_c_pos1.label = "Posición x"
            self.txt_c_pos2.visible = False
        elif tipo == "polinomica":
            self.txt_c_val1.visible = False
            self.txt_c_val2.visible = False
            for ctrl in (self.txt_poly_a0, self.txt_poly_a1, self.txt_poly_a2, self.txt_poly_a3):
                ctrl.visible = True
            self.txt_c_pos1.label = "Inicio x₁"
            self.txt_c_pos2.label = "Fin x₂"
            self.txt_c_pos2.visible = True

        self.pagina.update()

    def _agregar_carga(self, e):
        try:
            tipo = self.dd_tipo_carga.value
            origen = self.dd_origen_carga.value or "L"
            if tipo == "puntual":
                P = float(self.txt_c_val1.value or 0.0)
                Px = float(self.txt_c_val2.value or 0.0)
                x = float(self.txt_c_pos1.value)
                self.cargas_memoria.append({"tipo": "puntual", "P": P, "Px": Px, "x": x, "origen": origen})
            elif tipo == "uniforme":
                w = float(self.txt_c_val1.value)
                x1 = float(self.txt_c_pos1.value)
                x2 = float(self.txt_c_pos2.value)
                self.cargas_memoria.append({
                    "tipo": "distribuida", "subtipo": "uniforme",
                    "w1": w, "w2": w, "x1": x1, "x2": x2, "origen": origen
                })
            elif tipo in ("triangular", "trapezoidal"):
                w1 = float(self.txt_c_val1.value)
                w2 = float(self.txt_c_val2.value)
                x1 = float(self.txt_c_pos1.value)
                x2 = float(self.txt_c_pos2.value)
                self.cargas_memoria.append({
                    "tipo": "distribuida", "subtipo": tipo,
                    "w1": w1, "w2": w2, "x1": x1, "x2": x2, "origen": origen
                })
            elif tipo == "momento":
                M0 = float(self.txt_c_val1.value)
                x = float(self.txt_c_pos1.value)
                self.cargas_memoria.append({"tipo": "momento", "M0": M0, "x": x, "origen": origen})
            elif tipo == "polinomica":
                a0 = float(self.txt_poly_a0.value or 0.0)
                a1 = float(self.txt_poly_a1.value or 0.0)
                a2 = float(self.txt_poly_a2.value or 0.0)
                a3 = float(self.txt_poly_a3.value or 0.0)
                x1 = float(self.txt_c_pos1.value)
                x2 = float(self.txt_c_pos2.value)
                self.cargas_memoria.append({
                    "tipo": "polinomica", "a0": a0, "a1": a1, "a2": a2, "a3": a3,
                    "x1": x1, "x2": x2, "origen": origen
                })

            self._refrescar_lista_cargas_ui()
            self.pagina.update()
            self._mostrar_mensaje("Carga agregada correctamente.", bgcolor=ft.Colors.GREEN_700)
        except Exception as ex:
            self._mostrar_error(f"Error al ingresar carga: {ex}")

    def _eliminar_carga(self, index):
        if 0 <= index < len(self.cargas_memoria):
            self.cargas_memoria.pop(index)
            self._refrescar_lista_cargas_ui()
            self.pagina.update()

    def _refrescar_lista_cargas_ui(self):
        self.col_lista_cargas.controls.clear()
        if not self.cargas_memoria:
            self.col_lista_cargas.controls.append(ft.Text("Sin cargas externas agregadas.", italic=True, size=12))
            return

        for i, c in enumerate(self.cargas_memoria):
            orig = c.get("origen", "L")
            if c["tipo"] == "puntual":
                px_txt = f", Px={c.get('Px', 0):.1f} kN" if abs(c.get("Px", 0.0)) > 1e-6 else ""
                desc = f"• [{orig}] Puntual: P = {c['P']:.2f} kN{px_txt} en x = {c['x']:.2f} m"
            elif c["tipo"] == "distribuida":
                sub = c.get("subtipo", "distribuida").capitalize()
                desc = f"• [{orig}] {sub}: w = [{c['w1']:.2f} → {c['w2']:.2f}] kN/m en [{c['x1']:.2f}, {c['x2']:.2f}] m"
            elif c["tipo"] == "polinomica":
                desc = (f"• [{orig}] Polinómica: w(u)={c['a0']:.1f}+{c['a1']:.1f}u+{c['a2']:.1f}u²+{c['a3']:.1f}u³ "
                        f"en [{c['x1']:.2f}, {c['x2']:.2f}] m")
            else:
                desc = f"• [{orig}] Momento: M₀ = {c['M0']:.2f} kN·m en x = {c['x']:.2f} m"

            btn_del = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                tooltip="Eliminar carga",
                on_click=lambda e, idx=i: self._eliminar_carga(idx)
            )
            self.col_lista_cargas.controls.append(
                ft.Row([ft.Text(desc, size=12.5, expand=True), btn_del], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )

    # -------------------------------------------------------------
    # Ejecución del Modelo Físico Independiente de la Interfaz
    # -------------------------------------------------------------
    def _recopilar_config_diccionario(self) -> dict:
        tipo_sec = self.dd_tipo_seccion.value
        if tipo_sec == "rectangular":
            sec_dict = {
                "tipo": "rectangular",
                "parametros": {"base": float(self.txt_b_rect.value), "altura": float(self.txt_h_rect.value)}
            }
        elif tipo_sec == "perfil_i":
            sec_dict = {
                "tipo": "perfil_i",
                "parametros": {
                    "bf": float(self.txt_bf_i.value), "d": float(self.txt_d_i.value),
                    "tf": float(self.txt_tf_i.value), "tw": float(self.txt_tw_i.value),
                }
            }
        else:
            sec_dict = {
                "tipo": "bulb_tee",
                "parametros": {
                    "b1": 0.80, "b2": 0.60, "b3": 0.20, "b4": 0.10,
                    "d1": 1.20, "d2": 0.10, "d3": 0.15, "d4": 0.20,
                    "d5": 0.10, "d6": 0.05, "d7": 0.05,
                    "t1": 0.08, "t2": 0.06, "c1": 0.03,
                }
            }

        return {
            "longitud": float(self.txt_L.value),
            "tipo_viga": self.dd_tipo_viga.value,
            "apoyos_detalle": self.apoyos_memoria,
            "E_GPa": float(self.txt_E.value),
            "sigma_adm": float(self.txt_sigma_adm.value),
            "limite_k": int(self.dd_limite_def.value),
            "incluir_peso_propio": self.chk_peso_propio.value,
            "combinacion": self.dd_combinacion.value or "servicio",
            "accion_termica": {
                "delta_T_uniforme": float(self.txt_dT0.value or 0.0),
                "delta_T_gradiente": float(self.txt_dTgrad.value or 0.0),
                "retraccion_micro": float(self.txt_retraccion.value or 0.0),
                "fluencia_phi": float(self.txt_fluencia.value or 0.0),
            },
            "seccion": sec_dict,
            "cargas": self.cargas_memoria,
        }

    def ejecutar_calculo_inicial(self):
        """Ejecuta el análisis inicial y genera la memoria Word al arrancar la herramienta."""
        self._ejecutar_calculo(None, mostrar_toast=False)

    def _ejecutar_calculo(self, e, mostrar_toast: bool = True):
        try:
            if not self.apoyos_memoria:
                raise ValueError("Debe definir al menos un apoyo en la viga.")

            config = self._recopilar_config_diccionario()
            viga, resultado = analizar_viga_desde_diccionario(config)
            self.viga_actual = viga
            self.resultado_actual = resultado

            lineas_reac = []
            for det in resultado.reacciones_detalle:
                partes = [f"Ry={det['Ry']:.2f} kN"]
                if det["tipo"] in ("fijo", "empotrado") or abs(det["Rx"]) > 1e-2:
                    partes.append(f"Rx={det['Rx']:.2f} kN")
                if det["tipo"] in ("empotrado", "guiado") or abs(det["M"]) > 1e-2:
                    partes.append(f"M={det['M']:.2f} kN·m")
                lineas_reac.append(f"{det['etiqueta']} [{det['tipo'].capitalize()} en {det['x']:.2f}m]: " + ", ".join(partes))
            self.txt_res_reacciones.value = "  |  ".join(lineas_reac)

            self.txt_res_cortante.value = f"{resultado.V_abs_max:.2f} kN (x={resultado.x_V_max:.2f} m)"
            self.txt_res_momento.value = f"{resultado.M_abs_max:.2f} kN·m (x={resultado.x_M_max:.2f} m)"
            self.txt_res_axial.value = f"{resultado.N_abs_max:.2f} kN"
            self.txt_res_deflexion.value = f"{resultado.v_abs_max:.3f} mm (Lím: ±{resultado.deflexion_limite:.2f} mm)"
            self.txt_res_esfuerzo.value = f"{resultado.sigma_max:.2f} MPa (Adm: {resultado.sigma_adm:.1f} MPa)"

            if resultado.cumple_global:
                self.chip_estado.label.value = "CUMPLE NORMATIVA"
                self.chip_estado.bgcolor = ft.Colors.GREEN_100
                self.chip_estado.label.color = ft.Colors.GREEN_900
            else:
                self.chip_estado.label.value = "NO CUMPLE LÍMITES"
                self.chip_estado.bgcolor = ft.Colors.RED_100
                self.chip_estado.label.color = ft.Colors.RED_900

            fig = generar_figura_analisis_completo(viga, resultado)
            png_bytes = figura_a_bytes(fig)
            b64_img = base64.b64encode(png_bytes).decode('ascii')

            self.img_grafica.src = f"data:image/png;base64,{b64_img}"
            self.img_grafica.visible = True
            self.txt_espera_grafica.visible = False

            self.btn_guardar_bd.disabled = False
            self.btn_generar_word.disabled = False
            self.btn_ver_paso_a_paso.disabled = False

            if self.al_calcular_callback:
                self.al_calcular_callback(
                    viga,
                    resultado,
                    self.txt_proyecto.value.strip(),
                    self.txt_calculo.value.strip(),
                    self.txt_autor.value.strip(),
                )

            # Generar automáticamente la memoria Word (.docx)
            if self.chk_auto_word.value:
                self._generar_word(None, mostrar_toast=False)

            if mostrar_toast:
                msg = "Cálculo completado."
                if self.ultima_ruta_word:
                    msg += f" Memoria Word guardada: {self.ultima_ruta_word.name}"
                self._mostrar_mensaje(msg, bgcolor=ft.Colors.GREEN_700)
            self.pagina.update()

        except Exception as ex:
            self._mostrar_error(f"Error en el análisis: {ex}")

    def _guardar_en_bd(self, e):
        if not self.resultado_actual:
            return
        try:
            datos_entrada = {
                "longitud": self.resultado_actual.L,
                "tipo_viga": self.resultado_actual.tipo_viga,
                "apoyos": (self.viga_actual.x_apoyo1, self.viga_actual.x_apoyo2),
                "apoyos_detalle": self.apoyos_memoria,
                "E_GPa": self.resultado_actual.E_GPa,
                "sigma_adm": self.resultado_actual.sigma_adm,
                "limite_k": self.resultado_actual.limite_k,
                "incluir_peso_propio": self.resultado_actual.peso_propio_incluido,
                "combinacion": self.resultado_actual.combinacion_usada,
                "accion_termica": self.viga_actual.accion_termica.to_dict(),
                "seccion": self.resultado_actual.seccion.to_dict(),
                "cargas": self.cargas_memoria
            }

            resumen_resultados = {
                "V_abs_max": self.resultado_actual.V_abs_max,
                "M_abs_max": self.resultado_actual.M_abs_max,
                "N_abs_max": self.resultado_actual.N_abs_max,
                "v_abs_max": self.resultado_actual.v_abs_max,
                "sigma_max": self.resultado_actual.sigma_max,
                "deflexion_limite": self.resultado_actual.deflexion_limite,
                "cumple_esfuerzo": self.resultado_actual.cumple_esfuerzo,
                "cumple_deflexion": self.resultado_actual.cumple_deflexion,
                "cumple_global": self.resultado_actual.cumple_global
            }

            cid = guardar_calculo(
                proyecto_nombre=self.txt_proyecto.value.strip(),
                calculo_nombre=self.txt_calculo.value.strip(),
                tipo_viga=self.resultado_actual.tipo_viga,
                longitud=self.resultado_actual.L,
                datos_entrada=datos_entrada,
                resumen_resultados=resumen_resultados,
                cumple_global=self.resultado_actual.cumple_global,
                autor=self.txt_autor.value.strip()
            )

            if self.al_guardar_callback:
                self.al_guardar_callback()

            self._mostrar_mensaje(f"Cálculo guardado en SQLite con ID #{cid}", bgcolor=ft.Colors.GREEN_700)

        except Exception as ex:
            self._mostrar_error(f"Error al guardar en BD: {ex}")

    def _abrir_paso_a_paso(self, e):
        if self.al_abrir_paso_a_paso_callback:
            self.al_abrir_paso_a_paso_callback()

    def _generar_word(self, e, mostrar_toast: bool = True):
        if not self.resultado_actual or not self.viga_actual:
            return
        try:
            ruta = generar_memoria_word(
                viga=self.viga_actual,
                resultado=self.resultado_actual,
                proyecto_nombre=self.txt_proyecto.value.strip(),
                calculo_nombre=self.txt_calculo.value.strip(),
                autor=self.txt_autor.value.strip()
            )
            self.ultima_ruta_word = ruta
            self.btn_abrir_word.disabled = False
            self.txt_ruta_word.value = f"Memoria Word generada: reportes\\{ruta.name}"
            if mostrar_toast:
                self._mostrar_mensaje(f"Memoria generada en:\n{ruta}", bgcolor=ft.Colors.BLUE_800)
            self.pagina.update()
        except Exception as ex:
            self._mostrar_error(f"Error al generar Word: {ex}")

    def _abrir_ultimo_word(self, e):
        if self.ultima_ruta_word and self.ultima_ruta_word.exists():
            try:
                if hasattr(os, "startfile"):
                    os.startfile(str(self.ultima_ruta_word))
            except Exception as ex:
                self._mostrar_error(f"No se pudo abrir el archivo Word: {ex}")

    def cargar_calculo_desde_datos(self, calc: dict):
        """Reabre un cálculo previamente guardado en SQLite y lo carga en la interfaz."""
        try:
            self.txt_proyecto.value = calc.get("proyecto_nombre", "")
            self.txt_calculo.value = calc.get("nombre", "")
            self.txt_autor.value = calc.get("autor", "")

            inp = calc.get("datos_entrada", {})
            self.txt_L.value = str(inp.get("longitud", 8.0))
            self.dd_tipo_viga.value = inp.get("tipo_viga", "simplemente_apoyada")

            apoyos_det = inp.get("apoyos_detalle")
            if apoyos_det:
                self.apoyos_memoria = apoyos_det
            else:
                apoyos = inp.get("apoyos", (0.0, 8.0))
                if self.dd_tipo_viga.value == "voladizo":
                    self.apoyos_memoria = [{"tipo": "empotrado", "x": 0.0, "ky": 0.0, "ktheta": 0.0, "kx": 0.0}]
                else:
                    self.apoyos_memoria = [
                        {"tipo": "fijo", "x": float(apoyos[0]), "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
                        {"tipo": "movil", "x": float(apoyos[1]), "ky": 0.0, "ktheta": 0.0, "kx": 0.0},
                    ]
            self._refrescar_lista_apoyos_ui()

            self.txt_E.value = str(inp.get("E_GPa", 24.0))
            self.txt_sigma_adm.value = str(inp.get("sigma_adm", 180.0))
            self.dd_limite_def.value = str(inp.get("limite_k", 360))
            self.chk_peso_propio.value = inp.get("incluir_peso_propio", True)
            self.dd_combinacion.value = inp.get("combinacion", "servicio")

            term = inp.get("accion_termica", {})
            self.txt_dT0.value = str(term.get("delta_T_uniforme", 0.0))
            self.txt_dTgrad.value = str(term.get("delta_T_gradiente", 0.0))
            self.txt_retraccion.value = str(term.get("retraccion_micro", 0.0))
            self.txt_fluencia.value = str(term.get("fluencia_phi", 0.0))

            sec_d = inp.get("seccion", {})
            tipo_s = sec_d.get("tipo", "rectangular")
            self.dd_tipo_seccion.value = tipo_s

            params = sec_d.get("parametros", {})
            if tipo_s == "rectangular":
                self.txt_b_rect.value = str(params.get("base", 0.30))
                self.txt_h_rect.value = str(params.get("altura", 0.60))
            elif tipo_s == "perfil_i":
                self.txt_bf_i.value = str(params.get("bf", 0.25))
                self.txt_d_i.value = str(params.get("d", 0.45))
                self.txt_tf_i.value = str(params.get("tf", 0.018))
                self.txt_tw_i.value = str(params.get("tw", 0.010))

            self._on_cambio_tipo_seccion(None)

            self.cargas_memoria = inp.get("cargas", [])
            self._refrescar_lista_cargas_ui()

            self._ejecutar_calculo(None)

        except Exception as ex:
            self._mostrar_error(f"Error al reabrir cálculo: {ex}")

    def _mostrar_error(self, mensaje: str):
        dlg = ft.AlertDialog(
            title=ft.Text("Validación de Entrada", weight=ft.FontWeight.BOLD),
            content=ft.Text(mensaje),
            actions=[ft.TextButton("Aceptar", on_click=lambda e: self.pagina.pop_dialog())]
        )
        self.pagina.show_dialog(dlg)

    def _mostrar_mensaje(self, texto: str, bgcolor=ft.Colors.GREEN_700):
        sb = ft.SnackBar(content=ft.Text(texto), bgcolor=bgcolor)
        self.pagina.show_dialog(sb)
