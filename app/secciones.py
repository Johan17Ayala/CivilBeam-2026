"""
secciones.py
Adaptador y extensiones de secciones transversales para el análisis estructural,
reutilizando pysections (sections.py) sin modificar el módulo base original.

Universidad Distrital Francisco José de Caldas - Facultad Tecnológica
Programación II
"""

import numpy as np
from app.sections import _SinglePolygonSection, Deck, BulbTeeGirderBridge


class PerfilI(_SinglePolygonSection):
    """
    Modela un perfil en I / doble T simétrico de acero como un polígono cerrado único.
    Hereda de _SinglePolygonSection de pysections.
    
    Dimensiones (todas en metros):
    - bf: Ancho del ala (flange width)
    - d : Altura total del perfil (depth)
    - tf: Espesor del ala (flange thickness)
    - tw: Espesor del alma (web thickness)
    """
    def __init__(self, bf: float, d: float, tf: float, tw: float):
        if bf <= 0 or d <= 0 or tf <= 0 or tw <= 0:
            raise ValueError("Todas las dimensiones deben ser estrictamente positivas.")
        if 2 * tf >= d:
            raise ValueError("El espesor total de las dos alas (2*tf) no puede exceder la altura d.")
        if tw >= bf:
            raise ValueError("El espesor del alma (tw) no puede ser mayor o igual al ancho del ala (bf).")

        self.bf = float(bf)
        self.d = float(d)
        self.tf = float(tf)
        self.tw = float(tw)
        super().__init__()

    def _calculate_points(self):
        """
        Genera los 12 vértices del contorno en sentido antihorario.
        El centroide horizontal se alinea con Y = 0 y la base descansa en Z = 0.
        """
        bf = self.bf
        d = self.d
        tf = self.tf
        tw = self.tw

        # Vértices en semiplano derecho y simetría
        # 1. Base derecha: (+bf/2, 0)
        # 2. Esquina inferior ala inf der: (+bf/2, tf)
        # 3. Encuentro ala-alma inf der: (+tw/2, tf)
        # 4. Encuentro ala-alma sup der: (+tw/2, d - tf)
        # 5. Esquina inferior ala sup der: (+bf/2, d - tf)
        # 6. Esquina superior ala sup der: (+bf/2, d)
        # 7. Esquina superior ala sup izq: (-bf/2, d)
        # 8. Esquina inferior ala sup izq: (-bf/2, d - tf)
        # 9. Encuentro ala-alma sup izq: (-tw/2, d - tf)
        # 10. Encuentro ala-alma inf izq: (-tw/2, tf)
        # 11. Esquina inferior ala inf izq: (-bf/2, tf)
        # 12. Base izquierda: (-bf/2, 0)

        pts = np.array([
            [ bf / 2.0, 0.0],
            [ bf / 2.0, tf],
            [ tw / 2.0, tf],
            [ tw / 2.0, d - tf],
            [ bf / 2.0, d - tf],
            [ bf / 2.0, d],
            [-bf / 2.0, d],
            [-bf / 2.0, d - tf],
            [-tw / 2.0, d - tf],
            [-tw / 2.0, tf],
            [-bf / 2.0, tf],
            [-bf / 2.0, 0.0]
        ], dtype=float)

        return pts

    @property
    def height(self):
        return self.d

    @property
    def zi(self):
        return self.z

    @property
    def zs(self):
        return self.height - self.zi

    @property
    def wi(self):
        return self.Iyy / self.zi

    @property
    def ws(self):
        return self.Iyy / self.zs


class SeccionVigaInfo:
    """
    Contenedor estándar de propiedades de cualquier sección transversal
    calculadas por pysections para su consumo en app/modelo.py.
    """
    def __init__(self, tipo: str, nombre: str, area: float, inercia: float,
                 altura: float, zi: float, zs: float, wi: float, ws: float,
                 parametros: dict, puntos: np.ndarray = None):
        self.tipo = tipo            # 'rectangular', 'perfil_i', 'bulb_tee'
        self.nombre = nombre        # Etiqueta legible
        self.area = float(area)     # [m²]
        self.inercia = float(inercia) # [m⁴] Iyy (respecto al eje horizontal)
        self.altura = float(altura) # [m] Altura total de la sección
        self.zi = float(zi)         # [m] Distancia al centroide desde la fibra inferior
        self.zs = float(zs)         # [m] Distancia al centroide desde la fibra superior
        self.wi = float(wi)         # [m³] Módulo de sección inferior
        self.ws = float(ws)         # [m³] Módulo de sección superior
        self.w_min = min(self.wi, self.ws) # Módulo de sección crítico
        self.parametros = parametros
        self.puntos = puntos

    def to_dict(self):
        return {
            "tipo": self.tipo,
            "nombre": self.nombre,
            "area": self.area,
            "inercia": self.inercia,
            "altura": self.altura,
            "zi": self.zi,
            "zs": self.zs,
            "wi": self.wi,
            "ws": self.ws,
            "w_min": self.w_min,
            "parametros": self.parametros
        }


def crear_seccion_rectangular(base: float, altura: float) -> SeccionVigaInfo:
    """
    Crea una sección rectangular utilizando la clase Deck de pysections.
    """
    if base <= 0 or altura <= 0:
        raise ValueError("Base y altura deben ser positivas.")
    deck = Deck(width=base, thickness=altura)
    # En Deck: width es horizontal, thickness es vertical (altura)
    # inercia Iyy es respecto al eje horizontal
    zi = altura / 2.0
    zs = altura / 2.0
    wi = deck.Iyy / zi
    ws = deck.Iyy / zs

    return SeccionVigaInfo(
        tipo="rectangular",
        nombre=f"Rectangular {base*100:.0f}x{altura*100:.0f} cm",
        area=deck.area,
        inercia=deck.Iyy,
        altura=altura,
        zi=zi,
        zs=zs,
        wi=wi,
        ws=ws,
        parametros={"base": base, "altura": altura},
        puntos=deck.points
    )


def crear_seccion_perfil_i(bf: float, d: float, tf: float, tw: float) -> SeccionVigaInfo:
    """
    Crea un perfil en I estructural utilizando la clase PerfilI heredada de _SinglePolygonSection.
    """
    perfil = PerfilI(bf=bf, d=d, tf=tf, tw=tw)
    return SeccionVigaInfo(
        tipo="perfil_i",
        nombre=f"Perfil I {bf*100:.0f}x{d*100:.0f} (tf={tf*100:.1f}, tw={tw*100:.1f} cm)",
        area=perfil.area,
        inercia=perfil.Iyy,
        altura=perfil.height,
        zi=perfil.zi,
        zs=perfil.zs,
        wi=perfil.wi,
        ws=perfil.ws,
        parametros={"bf": bf, "d": d, "tf": tf, "tw": tw},
        puntos=perfil.points
    )


def crear_seccion_bulb_tee(b1: float, b2: float, b3: float, b4: float,
                           d1: float, d2: float, d3: float, d4: float,
                           d5: float, d6: float, d7: float,
                           t1: float, t2: float, c1: float) -> SeccionVigaInfo:
    """
    Crea una viga de puente tipo Bulb-Tee utilizando directamente BulbTeeGirderBridge de pysections.
    """
    params = dict(b1=b1, b2=b2, b3=b3, b4=b4, d1=d1, d2=d2, d3=d3, d4=d4,
                  d5=d5, d6=d6, d7=d7, t1=t1, t2=t2, c1=c1)
    viga = BulbTeeGirderBridge(**params)

    return SeccionVigaInfo(
        tipo="bulb_tee",
        nombre=f"Bulb-Tee Girder (H={viga.height:.2f} m, A={viga.area:.3f} m²)",
        area=viga.area,
        inercia=viga.Iyy,
        altura=viga.height,
        zi=viga.zi,
        zs=viga.zs,
        wi=viga.wi,
        ws=viga.ws,
        parametros=params,
        puntos=viga.points
    )
