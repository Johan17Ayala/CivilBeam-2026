"""
historial_view.py
Vista de Historial, Persistencia y Comparación de Cálculos en SQLite.
Permite listar, buscar, filtrar, reabrir, comparar y eliminar cálculos guardados.

Universidad Distrital Francisco José de Caldas - Facultad Tecnológica
Programación II
"""

import base64
import flet as ft
from app.db import listar_calculos, obtener_calculo_por_id, eliminar_calculo
from app.modelo import analizar_viga_desde_diccionario
from app.graficas import generar_figura_comparativa, figura_a_bytes
from app.reporte import generar_memoria_word


class HistorialView(ft.Container):
    def __init__(self, page: ft.Page, al_reabrir_callback=None):
        super().__init__(expand=True)
        self.pagina = page
        self.al_reabrir_callback = al_reabrir_callback

        # Selección para comparación
        self.seleccionados = []

        self._construir_interfaz()

    def _construir_interfaz(self):
        # 1. Barra de búsqueda y filtrado
        self.txt_buscar = ft.TextField(
            label="Buscar por proyecto o cálculo...",
            prefix_icon=ft.Icons.SEARCH,
            expand=True,
            on_change=self._filtrar
        )
        self.btn_refrescar = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="Refrescar lista",
            on_click=lambda e: self.recargar_datos()
        )
        self.btn_comparar = ft.FilledButton(
            "Comparar Seleccionados (2)",
            icon=ft.Icons.COMPARE_ARROWS,
            style=ft.ButtonStyle(bgcolor=ft.Colors.INDIGO_700, color=ft.Colors.WHITE),
            on_click=self._comparar_calculos,
            disabled=True
        )

        barra_superior = ft.Row([
            self.txt_buscar,
            self.btn_refrescar,
            self.btn_comparar
        ], spacing=10)

        # 2. Contenedor de la lista de cálculos
        self.col_lista = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)

        # 3. Vista de Comparación modal / contenedor
        self.img_comparacion = ft.Image(src="", visible=False, fit="contain", width=760)

        card_principal = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Historial de Proyectos y Cálculos Estructurales (SQLite)",
                            size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900),
                    barra_superior,
                    ft.Divider(),
                    self.col_lista,
                    self.img_comparacion
                ]), padding=15
            )
        )

        self.content = ft.ListView([card_principal], padding=15)
        self.recargar_datos()

    def recargar_datos(self):
        """Lee la base de datos y refresca las tarjetas de cálculos."""
        self.seleccionados.clear()
        self.btn_comparar.disabled = True
        self.img_comparacion.visible = False

        calculos = listar_calculos(filtro_busqueda=self.txt_buscar.value or "")
        self.col_lista.controls.clear()

        if not calculos:
            self.col_lista.controls.append(
                ft.Container(
                    content=ft.Text("No hay cálculos registrados que coincidan con la búsqueda.",
                                    italic=True, color=ft.Colors.GREY_600),
                    padding=20, alignment=ft.Alignment(0, 0)
                )
            )
            self.pagina.update()
            return

        for c in calculos:
            cid = c["id"]
            p_nombre = c["proyecto_nombre"]
            c_nombre = c["nombre"]
            fecha = c["fecha"]
            nombres_tipo = {
                "simplemente_apoyada": "Simple",
                "voladizo": "Voladizo",
                "doble_empotrada": "Doble Empotr.",
                "empotrada_movil": "Empotr.+Móvil",
                "guiada_movil": "Guiado+Móvil",
                "elastica": "Elástica",
                "personalizado": "Personalizada"
            }
            tipo_v = nombres_tipo.get(c["tipo_viga"], c["tipo_viga"])
            L = c["longitud"]
            cumple = bool(c["cumple_global"])
            res = c.get("resumen", {})

            chip = ft.Chip(
                label=ft.Text("CUMPLE" if cumple else "NO CUMPLE", size=10, weight=ft.FontWeight.BOLD),
                bgcolor=ft.Colors.GREEN_100 if cumple else ft.Colors.RED_100,
                label_padding=0
            )

            # Checkbox para seleccionar para comparación
            chk = ft.Checkbox(
                value=False,
                tooltip="Seleccionar para comparar (máx 2)",
                on_change=lambda e, cal_id=cid: self._toggle_seleccion(cal_id, e.control.value)
            )

            btn_reabrir = ft.TextButton(
                "Reabrir", icon=ft.Icons.FOLDER_OPEN,
                on_click=lambda e, cal_id=cid: self._reabrir_calculo(cal_id)
            )
            btn_doc = ft.IconButton(
                icon=ft.Icons.DESCRIPTION_OUTLINED,
                tooltip="Descargar Memoria Word",
                on_click=lambda e, cal_id=cid: self._descargar_memoria(cal_id)
            )
            btn_eliminar = ft.IconButton(
                icon=ft.Icons.DELETE_FOREVER,
                icon_color=ft.Colors.RED_400,
                tooltip="Eliminar cálculo",
                on_click=lambda e, cal_id=cid, tit=c_nombre: self._confirmar_eliminacion(cal_id, tit)
            )

            info_txt = (
                f"Proyecto: {p_nombre} | Autor: {c.get('autor', 'Ingeniero')}\n"
                f"Tipo: {tipo_v} | Luz L: {L:.2f} m | Mmáx: {res.get('M_abs_max', 0):.1f} kN·m | δmáx: {res.get('v_abs_max', 0):.2f} mm\n"
                f"Fecha de guardado: {fecha}"
            )

            item = ft.Container(
                content=ft.Row([
                    chk,
                    ft.Column([
                        ft.Row([
                            ft.Text(f"#{cid} — {c_nombre}", weight=ft.FontWeight.BOLD, size=14),
                            chip
                        ]),
                        ft.Text(info_txt, size=11, color=ft.Colors.GREY_800)
                    ], expand=True),
                    ft.Row([btn_reabrir, btn_doc, btn_eliminar], spacing=0)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=10,
                border=ft.Border.all(1, ft.Colors.GREY_300),
                border_radius=8
            )
            self.col_lista.controls.append(item)

        self.pagina.update()

    def _filtrar(self, e):
        self.recargar_datos()

    def _toggle_seleccion(self, cid: int, seleccionado: bool):
        if seleccionado:
            if cid not in self.seleccionados:
                self.seleccionados.append(cid)
        else:
            if cid in self.seleccionados:
                self.seleccionados.remove(cid)

        # Habilitar comparar solo si hay exactamente 2 seleccionados
        self.btn_comparar.disabled = (len(self.seleccionados) != 2)
        self.pagina.update()

    def _reabrir_calculo(self, cid: int):
        calc = obtener_calculo_por_id(cid)
        if not calc:
            return
        if self.al_reabrir_callback:
            self.al_reabrir_callback(calc)
            self._mostrar_mensaje(f"Cálculo #{cid} recargado en el formulario.", bgcolor=ft.Colors.BLUE_700)

    def _descargar_memoria(self, cid: int):
        calc = obtener_calculo_por_id(cid)
        if not calc:
            return
        try:
            viga, res = self._reconstruir_modelo(calc)
            ruta = generar_memoria_word(
                viga=viga,
                resultado=res,
                proyecto_nombre=calc.get("proyecto_nombre", "Proyecto"),
                calculo_nombre=calc.get("nombre", "Viga"),
                autor=calc.get("autor", "Ingeniero")
            )
            self._mostrar_mensaje(f"Memoria generada en:\n{ruta.name}", bgcolor=ft.Colors.BLUE_800)
        except Exception as ex:
            self._mostrar_error(f"Error al generar memoria: {ex}")

    def _comparar_calculos(self, e):
        if len(self.seleccionados) != 2:
            return
        try:
            c1 = obtener_calculo_por_id(self.seleccionados[0])
            c2 = obtener_calculo_por_id(self.seleccionados[1])

            _, res1 = self._reconstruir_modelo(c1)
            _, res2 = self._reconstruir_modelo(c2)

            fig = generar_figura_comparativa(
                res1, res2,
                etiqueta1=f"#{c1['id']} {c1['nombre']}",
                etiqueta2=f"#{c2['id']} {c2['nombre']}"
            )
            png_bytes = figura_a_bytes(fig)
            b64_img = base64.b64encode(png_bytes).decode('ascii')

            self.img_comparacion.src = f"data:image/png;base64,{b64_img}"
            self.img_comparacion.visible = True
            self.pagina.update()

            self._mostrar_mensaje("Comparativa generada con éxito.", bgcolor=ft.Colors.INDIGO_700)
        except Exception as ex:
            self._mostrar_error(f"Error al comparar: {ex}")

    def _reconstruir_modelo(self, calc_dict: dict):
        """Reconstruye los objetos VigaIsostatica y ResultadoViga delegando al módulo de cálculo puro."""
        return analizar_viga_desde_diccionario(calc_dict["datos_entrada"])

    def _confirmar_eliminacion(self, cid: int, titulo: str):
        def _eliminar(e):
            self.pagina.pop_dialog()
            eliminar_calculo(cid)
            self.recargar_datos()
            self._mostrar_mensaje(f"Cálculo #{cid} eliminado.", bgcolor=ft.Colors.RED_700)

        dlg = ft.AlertDialog(
            title=ft.Text("Confirmar Eliminación", weight=ft.FontWeight.BOLD),
            content=ft.Text(f"¿Está seguro de que desea eliminar permanentemente el cálculo:\n'{titulo}'?"),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: self.pagina.pop_dialog()),
                ft.FilledButton("Eliminar", style=ft.ButtonStyle(bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE), on_click=_eliminar)
            ]
        )
        self.pagina.show_dialog(dlg)

    def _mostrar_error(self, mensaje: str):
        dlg = ft.AlertDialog(
            title=ft.Text("Notificación", weight=ft.FontWeight.BOLD),
            content=ft.Text(mensaje),
            actions=[ft.TextButton("Cerrar", on_click=lambda e: self.pagina.pop_dialog())]
        )
        self.pagina.show_dialog(dlg)

    def _mostrar_mensaje(self, texto: str, bgcolor=ft.Colors.BLUE_700):
        sb = ft.SnackBar(content=ft.Text(texto), bgcolor=bgcolor)
        self.pagina.show_dialog(sb)
