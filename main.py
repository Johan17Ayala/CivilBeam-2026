"""
main.py
Punto de entrada principal de la aplicación CivilBeam 2026.
Análisis, Diagramas y Diseño de Vigas Isostáticas con Cargas Arbitrarias.

Universidad Distrital Francisco José de Caldas - Facultad Tecnológica
Ingeniería Civil - Programación II
Semestre 2026-III - Grupo 18 - Proyecto 02
"""

import sys
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import flet as ft
from app.db import inicializar_bd
from app.ui.calculo_view import CalculoView
from app.ui.historial_view import HistorialView
from app.ui.paso_a_paso_view import PasoAPasoView


def main(page: ft.Page):
    # Configuración de ventana de escritorio
    page.title = "CivilBeam 2026 | Análisis Estructural & NSR-10 - Universidad Distrital"
    page.window.width = 1380
    page.window.height = 880
    page.window.min_width = 1050
    page.window.min_height = 700

    # Tema Material 3
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        color_scheme_seed=ft.Colors.BLUE_900,
        use_material3=True
    )
    page.padding = 0

    # Inicializar Base de Datos SQLite relacional
    inicializar_bd()

    # Callbacks de integración entre vistas
    def al_guardar_nuevo():
        historial_view.recargar_datos()

    def al_calcular_nuevo(viga, res, proy, calc, aut):
        paso_a_paso_view.actualizar_calculo(viga, res, proy, calc, aut)

    def al_ver_paso_a_paso():
        cambiar_vista(1)

    def al_reabrir_calculo(calc_dict):
        calculo_view.cargar_calculo_desde_datos(calc_dict)
        cambiar_vista(0)

    # Instanciar las vistas principales
    paso_a_paso_view = PasoAPasoView(page=page)
    calculo_view = CalculoView(
        page=page,
        al_guardar_callback=al_guardar_nuevo,
        al_calcular_callback=al_calcular_nuevo,
        al_abrir_paso_a_paso_callback=al_ver_paso_a_paso,
    )
    historial_view = HistorialView(page=page, al_reabrir_callback=al_reabrir_calculo)

    def cambiar_tema(e):
        if page.theme_mode == ft.ThemeMode.LIGHT:
            page.theme_mode = ft.ThemeMode.DARK
            btn_tema.icon = ft.Icons.LIGHT_MODE
            btn_tema.tooltip = "Cambiar a modo Claro"
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
            btn_tema.icon = ft.Icons.DARK_MODE
            btn_tema.tooltip = "Cambiar a modo Oscuro"
        page.update()

    btn_tema = ft.IconButton(
        icon=ft.Icons.DARK_MODE,
        tooltip="Cambiar a modo Oscuro",
        icon_color=ft.Colors.WHITE,
        on_click=cambiar_tema
    )

    # Contenedor central intercambiable
    contenedor_vistas = ft.AnimatedSwitcher(
        content=calculo_view,
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=200,
        reverse_duration=200,
        expand=True
    )

    def cambiar_vista(index: int):
        rail.selected_index = index
        if index == 0:
            contenedor_vistas.content = calculo_view
        elif index == 1:
            contenedor_vistas.content = paso_a_paso_view
        else:
            historial_view.recargar_datos()
            contenedor_vistas.content = historial_view
        page.update()

    def on_rail_change(e):
        cambiar_vista(rail.selected_index)

    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=90,
        min_extended_width=180,
        bgcolor=ft.Colors.BLUE_GREY_50,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.CALCULATE_OUTLINED,
                selected_icon=ft.Icons.CALCULATE,
                label="Cálculo"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.FORMAT_LIST_NUMBERED_OUTLINED,
                selected_icon=ft.Icons.FORMAT_LIST_NUMBERED,
                label="Paso a Paso"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.HISTORY_ROUNDED,
                selected_icon=ft.Icons.HISTORY,
                label="Historial BD"
            ),
        ],
        on_change=on_rail_change
    )

    # Encabezado institucional elegante
    header = ft.Container(
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.Icons.ARCHITECTURE, size=32, color=ft.Colors.AMBER_400),
                ft.Column([
                    ft.Text(
                        "CivilBeam 2026",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE
                    ),
                    ft.Text(
                        "Universidad Distrital Francisco José de Caldas • Facultad Tecnológica • Programación II",
                        size=11,
                        color=ft.Colors.BLUE_GREY_100
                    )
                ], spacing=1)
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([
                ft.Container(
                    content=ft.Text(
                        "NSR-10 / AISC-LRFD",
                        size=11,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.WHITE
                    ),
                    bgcolor=ft.Colors.BLUE_800,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                    border_radius=12
                ),
                btn_tema
            ], alignment=ft.MainAxisAlignment.END, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        bgcolor=ft.Colors.BLUE_900,
        padding=ft.Padding.symmetric(horizontal=16, vertical=8),
        shadow=ft.BoxShadow(spread_radius=1, blur_radius=6, color=ft.Colors.BLACK_26)
    )

    page.add(
        ft.Column([
            header,
            ft.Row([
                rail,
                ft.VerticalDivider(width=1),
                contenedor_vistas
            ], expand=True, spacing=0)
        ], spacing=0, expand=True)
    )

    # Ejecutar cálculo inicial y generar memoria Word automáticamente al abrir la herramienta
    calculo_view.ejecutar_calculo_inicial()


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
