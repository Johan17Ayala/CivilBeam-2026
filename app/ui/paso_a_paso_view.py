"""
paso_a_paso_view.py
Vista interactiva de revisión paso a paso de todos los cálculos de ingeniería
con extracción directa a documento Word (.docx).

Universidad Distrital Francisco José de Caldas - Facultad Tecnológica
Programación II
"""

import os
import flet as ft
from app.paso_a_paso import generar_pasos_calculo, generar_word_paso_a_paso


class PasoAPasoView(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__(expand=True)
        self.pagina = page

        self.viga_actual = None
        self.resultado_actual = None
        self.proyecto_nombre = "Proyecto General"
        self.calculo_nombre = "Viga Analizada"
        self.autor = "Ingeniero Calculista"
        self.ultima_ruta_word = None

        self._construir_interfaz()

    def _construir_interfaz(self):
        self.btn_extraer_word = ft.FilledButton(
            "Extraer Paso a Paso a Word (.docx)",
            icon=ft.Icons.FILE_DOWNLOAD,
            style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
            on_click=self._extraer_word,
            disabled=True
        )
        self.btn_abrir_word = ft.OutlinedButton(
            "Abrir Word Extraído",
            icon=ft.Icons.OPEN_IN_NEW,
            on_click=self._abrir_word,
            disabled=True
        )
        self.txt_estado_word = ft.Text(
            "Calcule una viga para revisar el procedimiento completo y exportarlo a Word.",
            size=12, color=ft.Colors.BLUE_800, selectable=True
        )

        card_cabecera = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        "Revisión Detallada de Cálculos Paso a Paso",
                        size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900
                    ),
                    ft.Text(
                        "Consulte las ecuaciones aplicadas, sustituciones numéricas, verificación de equilibrio y chequeos NSR-10.",
                        size=12.5, color=ft.Colors.GREY_700
                    ),
                    ft.Row([self.btn_extraer_word, self.btn_abrir_word], spacing=12, wrap=True),
                    self.txt_estado_word,
                ], spacing=8),
                padding=15
            )
        )

        self.col_pasos = ft.Column(spacing=12)
        self.col_pasos.controls.append(
            ft.Container(
                content=ft.Text(
                    "No hay cálculos disponibles aún. Presione 'CALCULAR VIGA' en la pestaña Cálculo.",
                    italic=True, color=ft.Colors.GREY_600
                ),
                padding=20
            )
        )

        self.content = ft.ListView([
            card_cabecera,
            self.col_pasos,
        ], spacing=12, padding=15)

    def actualizar_calculo(self, viga, resultado, proyecto: str, calculo: str, autor: str):
        """Actualiza la vista con el procedimiento completo del cálculo recién resuelto."""
        self.viga_actual = viga
        self.resultado_actual = resultado
        self.proyecto_nombre = proyecto or "Proyecto General"
        self.calculo_nombre = calculo or "Viga Analizada"
        self.autor = autor or "Ingeniero Calculista"

        pasos = generar_pasos_calculo(viga, resultado)
        self.col_pasos.controls.clear()

        for p in pasos:
            caja_ecuaciones = ft.Container(
                content=ft.Column(
                    [ft.Text("Fórmulas aplicadas:", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_900)]
                    + [ft.Text(f"• {eq}", size=12, font_family="monospace", selectable=True) for eq in p["ecuaciones"]],
                    spacing=3
                ),
                bgcolor=ft.Colors.BLUE_50,
                border=ft.Border.all(1, ft.Colors.BLUE_200),
                border_radius=8,
                padding=10,
            )

            col_desarrollo = ft.Column(
                [ft.Text(linea, size=13, selectable=True) for linea in p["desarrollo"]],
                spacing=5
            )

            pie_resultado = ft.Container(
                content=ft.Text(
                    f"▶ Resultado Paso {p['numero']}: {p['resultado_clave']}",
                    size=12.5, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_900, selectable=True
                ),
                bgcolor=ft.Colors.GREEN_50,
                border=ft.Border.all(1, ft.Colors.GREEN_200),
                border_radius=6,
                padding=8,
            )

            tarjeta = ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Text(f"PASO {p['numero']}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                bgcolor=ft.Colors.BLUE_800,
                                padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                border_radius=10
                            ),
                            ft.Text(p["titulo"], size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900, expand=True),
                        ], spacing=10),
                        caja_ecuaciones,
                        col_desarrollo,
                        pie_resultado,
                    ], spacing=10),
                    padding=15
                )
            )
            self.col_pasos.controls.append(tarjeta)

        self.btn_extraer_word.disabled = False
        self.txt_estado_word.value = (
            f"Cálculo listo: {self.calculo_nombre}. Presione 'Extraer Paso a Paso a Word (.docx)' para exportar."
        )

    def _extraer_word(self, e):
        if not self.viga_actual or not self.resultado_actual:
            return
        try:
            ruta = generar_word_paso_a_paso(
                viga=self.viga_actual,
                resultado=self.resultado_actual,
                proyecto_nombre=self.proyecto_nombre,
                calculo_nombre=self.calculo_nombre,
                autor=self.autor,
            )
            self.ultima_ruta_word = ruta
            self.btn_abrir_word.disabled = False
            self.txt_estado_word.value = f"Documento Paso a Paso exportado en: reportes\\{ruta.name}"
            sb = ft.SnackBar(
                content=ft.Text(f"Paso a paso exportado a Word:\n{ruta.name}"),
                bgcolor=ft.Colors.GREEN_700
            )
            self.pagina.show_dialog(sb)
            self.pagina.update()
        except Exception as ex:
            dlg = ft.AlertDialog(
                title=ft.Text("Error al exportar", weight=ft.FontWeight.BOLD),
                content=ft.Text(str(ex)),
                actions=[ft.TextButton("Cerrar", on_click=lambda ev: self.pagina.pop_dialog())]
            )
            self.pagina.show_dialog(dlg)

    def _abrir_word(self, e):
        if self.ultima_ruta_word and self.ultima_ruta_word.exists():
            try:
                if hasattr(os, "startfile"):
                    os.startfile(str(self.ultima_ruta_word))
            except Exception as ex:
                dlg = ft.AlertDialog(
                    title=ft.Text("No se pudo abrir Word", weight=ft.FontWeight.BOLD),
                    content=ft.Text(str(ex)),
                    actions=[ft.TextButton("Cerrar", on_click=lambda ev: self.pagina.pop_dialog())]
                )
                self.pagina.show_dialog(dlg)
