"""
modelo.py
Motor analítico y numérico para el cálculo estructural de vigas (isostáticas, hiperestáticas y sobre apoyos elásticos).
Universidad Distrital Francisco José de Caldas - Facultad Tecnológica
Programación II

Implementa:
1. Solucionador matricial por Elementos Finitos 1D (Viga de Euler-Bernoulli + Barra Axial) con 3 GDL por nodo (u, v, theta).
2. Soporte completo para los 5 tipos de apoyo estructural:
   - 'movil': Apoyo simple o móvil / roller (restringe v; reacción Ry).
   - 'fijo': Apoyo articulado o fijo / pin (restringe u, v; reacciones Rx, Ry).
   - 'empotrado': Empotramiento rígido / fixed (restringe u, v, theta; reacciones Rx, Ry, M).
   - 'guiado': Empotramiento guiado o deslizante (restringe v, theta; reacciones Ry, M).
   - 'elastico': Apoyo elástico traslacional/rotacional (rigideces ky, ktheta, kx).
3. Soporte completo de cargas geométricas y por origen/persistencia:
   - Puntuales o concentradas (vertical P y horizontal Px).
   - Distribuidas uniformes, triangulares y trapezoidales.
   - Momentos concentrados (M0).
   - No lineales / polinómicas: w(u) = a0 + a1*u + a2*u^2 + a3*u^3 con cuadratura exacta de Gauss-Legendre.
   - Clasificación por origen (D, L, W, E, S, T) y combinaciones normativas NSR-10 Título B.
   - Acciones térmicas (Delta T uniforme y gradiente) y reológicas (retracción y fluencia lenta).
4. Evaluación de esfuerzos máximos (flexión + axial) y verificación de deflexión según NSR-10.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
import numpy as np

from app.secciones import (
    SeccionVigaInfo,
    crear_seccion_rectangular,
    crear_seccion_perfil_i,
    crear_seccion_bulb_tee,
)


# =========================================================================
# CATÁLOGOS DE APOYOS, ORÍGENES Y COMBINACIONES NORMATIVAS (NSR-10)
# =========================================================================

TIPOS_APOYO = {
    "movil": "Apoyo Simple / Móvil (Roller)",
    "fijo": "Apoyo Articulado / Fijo (Pin)",
    "empotrado": "Empotramiento Rígido (Fixed)",
    "guiado": "Empotramiento Guiado / Deslizante",
    "elastico": "Apoyo Elástico (Resorte ky / kθ)",
}

ORIGENES_CARGA = {
    "D": "Carga Muerta (D)",
    "L": "Carga Viva (L)",
    "W": "Viento (W)",
    "E": "Sismo (E)",
    "S": "Granizo / Nieve (S)",
    "T": "Térmica / Reológica (T)",
}

COMBINACIONES_CARGA = {
    "servicio": {
        "nombre": "Servicio (1.0 D + 1.0 L + 1.0 W + 1.0 E + 1.0 S + 1.0 T)",
        "factores": {"D": 1.0, "L": 1.0, "W": 1.0, "E": 1.0, "S": 1.0, "T": 1.0},
    },
    "nsr_1": {
        "nombre": "NSR-10 B.2.4-1 (1.4 D)",
        "factores": {"D": 1.4, "L": 0.0, "W": 0.0, "E": 0.0, "S": 0.0, "T": 0.0},
    },
    "nsr_2": {
        "nombre": "NSR-10 B.2.4-2 (1.2 D + 1.6 L + 0.5 S + 1.2 T)",
        "factores": {"D": 1.2, "L": 1.6, "W": 0.0, "E": 0.0, "S": 0.5, "T": 1.2},
    },
    "nsr_3": {
        "nombre": "NSR-10 B.2.4-3 (1.2 D + 1.6 S + 1.0 L + 1.2 T)",
        "factores": {"D": 1.2, "L": 1.0, "W": 0.0, "E": 0.0, "S": 1.6, "T": 1.2},
    },
    "nsr_4": {
        "nombre": "NSR-10 B.2.4-4 (1.2 D + 1.0 W + 1.0 L + 0.5 S)",
        "factores": {"D": 1.2, "L": 1.0, "W": 1.0, "E": 0.0, "S": 0.5, "T": 0.0},
    },
    "nsr_5": {
        "nombre": "NSR-10 B.2.4-5 (1.2 D + 1.0 E + 1.0 L + 0.2 S)",
        "factores": {"D": 1.2, "L": 1.0, "W": 0.0, "E": 1.0, "S": 0.2, "T": 0.0},
    },
    "nsr_6": {
        "nombre": "NSR-10 B.2.4-6 (0.9 D + 1.0 W)",
        "factores": {"D": 0.9, "L": 0.0, "W": 1.0, "E": 0.0, "S": 0.0, "T": 0.0},
    },
}


# =========================================================================
# ESTRUCTURAS DE DATOS PARA APOYOS Y CARGAS
# =========================================================================

@dataclass
class Apoyo:
    """
    Representa un apoyo estructural en la posición x [m] de la viga.
    tipo: 'movil', 'fijo', 'empotrado', 'guiado', 'elastico'.
    ky: rigidez traslacional vertical [kN/m] (para tipo 'elastico').
    ktheta: rigidez rotacional [kN·m/rad] (para tipo 'elastico').
    kx: rigidez traslacional axial [kN/m] (opcional para tipo 'elastico').
    """
    x: float
    tipo: str = "movil"
    ky: float = 0.0
    ktheta: float = 0.0
    kx: float = 0.0
    etiqueta: str = ""

    def __post_init__(self):
        self.tipo = self.tipo.lower().strip()
        if self.tipo not in TIPOS_APOYO:
            raise ValueError(f"Tipo de apoyo '{self.tipo}' no reconocido.")
        self.x = float(self.x)
        self.ky = float(self.ky)
        self.ktheta = float(self.ktheta)
        self.kx = float(self.kx)

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "tipo": self.tipo,
            "ky": self.ky,
            "ktheta": self.ktheta,
            "kx": self.kx,
            "etiqueta": self.etiqueta,
        }


@dataclass
class CargaPuntual:
    """
    Carga puntual concentrada.
    P en [kN] (vertical positiva hacia abajo), posicion x en [m].
    Px en [kN] (horizontal positiva hacia la derecha, opcional).
    """
    P: float
    x: float
    Px: float = 0.0
    origen: str = "L"


@dataclass
class CargaDistribuida:
    """
    Carga distribuida uniforme, triangular o trapezoidal.
    w1, w2 en [kN/m] (positivas hacia abajo).
    x1, x2 en [m] (rango de aplicación).
    """
    w1: float
    w2: float
    x1: float
    x2: float
    origen: str = "L"

    def __post_init__(self):
        if self.x1 > self.x2:
            self.x1, self.x2 = self.x2, self.x1
            self.w1, self.w2 = self.w2, self.w1


@dataclass
class CargaPolinomica:
    """
    Carga distribuida no lineal / polinómica sobre [x1, x2]:
    w(u) = a0 + a1*u + a2*u^2 + a3*u^3 [kN/m], donde u = x - x1 [m].
    Positiva hacia abajo.
    """
    a0: float
    a1: float
    a2: float
    a3: float
    x1: float
    x2: float
    origen: str = "L"

    def __post_init__(self):
        if self.x1 > self.x2:
            self.x1, self.x2 = self.x2, self.x1

    def evaluar(self, x_arr: np.ndarray) -> np.ndarray:
        u = x_arr - self.x1
        return self.a0 + self.a1 * u + self.a2 * (u ** 2) + self.a3 * (u ** 3)


@dataclass
class MomentoConcentrado:
    """
    Momento puntual concentrado. M0 en [kN·m].
    Convención: positivo antihorario.
    """
    M0: float
    x: float
    origen: str = "L"


@dataclass
class AccionTermicaReologica:
    """
    Acciones térmicas y reológicas sobre el elemento viga:
    - delta_T_uniforme: cambio uniforme de temperatura [°C] (positivo = calentamiento/expansión).
    - delta_T_gradiente: T_inferior - T_superior [°C] (positivo = cara inferior más caliente).
    - retraccion_micro: retracción por fraguado [microstrain, x10^-6] (valor positivo indica acortamiento).
    - fluencia_phi: coeficiente de fluencia lenta adimensional (>= 0). E_eff = E / (1 + phi).
    - alpha_T: coeficiente de dilatación térmica [1/°C] (típico concreto/acero ~ 1.2e-5).
    """
    delta_T_uniforme: float = 0.0
    delta_T_gradiente: float = 0.0
    retraccion_micro: float = 0.0
    fluencia_phi: float = 0.0
    alpha_T: float = 1.2e-5

    def to_dict(self) -> dict:
        return {
            "delta_T_uniforme": float(self.delta_T_uniforme),
            "delta_T_gradiente": float(self.delta_T_gradiente),
            "retraccion_micro": float(self.retraccion_micro),
            "fluencia_phi": float(self.fluencia_phi),
            "alpha_T": float(self.alpha_T),
        }


@dataclass
class ResultadoViga:
    """Contenedor de resultados del análisis estructural."""
    # Malla y diagramas vectorizados
    x: np.ndarray
    V: np.ndarray          # Cortante [kN]
    M: np.ndarray          # Momento flector [kN·m]
    N: np.ndarray          # Fuerza axial [kN]
    theta: np.ndarray      # Giro / pendiente [rad]
    v: np.ndarray          # Deflexión [m]
    v_mm: np.ndarray       # Deflexión [mm]
    u_mm: np.ndarray       # Desplazamiento axial [mm]

    # Reacciones en apoyos
    reacciones: Dict[str, float]
    reacciones_detalle: List[Dict[str, Any]]

    # Valores extremos
    V_max: float           # [kN]
    V_min: float           # [kN]
    V_abs_max: float       # [kN]
    x_V_max: float         # [m]

    M_max: float           # [kN·m]
    M_min: float           # [kN·m]
    M_abs_max: float       # [kN·m]
    x_M_max: float         # [m]

    N_abs_max: float       # [kN]

    v_max: float           # [mm]
    v_min: float           # [mm]
    v_abs_max: float       # [mm]
    x_v_max: float         # [m]

    # Esfuerzos y chequeos ingenieriles
    sigma_max: float       # [MPa]
    sigma_adm: float       # [MPa]
    cumple_esfuerzo: bool

    deflexion_limite: float # [mm]
    limite_k: int
    cumple_deflexion: bool

    cumple_global: bool

    # Propiedades de entrada para reporte
    tipo_viga: str
    L: float
    E_GPa: float
    E_efectivo_GPa: float
    seccion: SeccionVigaInfo
    peso_propio_incluido: bool
    combinacion_usada: str = "servicio"
    grado_hiperestaticidad: int = 0


# =========================================================================
# MOTOR DE ELEMENTOS FINITOS 1D (EULER-BERNOULLI + BARRA AXIAL)
# =========================================================================

class VigaIsostatica:
    """
    Modela una viga elástica lineal 1D (isostática, hiperestática o sobre apoyos elásticos).
    Mantiene retrocompatibilidad completa con 'simplemente_apoyada' y 'voladizo', y añade
    configuración arbitraria de apoyos (móvil, fijo, empotrado, guiado, elástico),
    cargas polinómicas, cargas horizontales, orígenes (D, L, W, E, S, T), combinaciones NSR-10
    y acciones térmicas/reológicas.
    """

    def __init__(
        self,
        longitud: float,
        tipo: str = "simplemente_apoyada",
        pos_apoyos: Tuple[float, float] = (0.0, None),
        seccion: Optional[SeccionVigaInfo] = None,
        E_GPa: float = 200.0,
        sigma_adm_MPa: float = 150.0,
        limite_deflexion_k: int = 360,
        densidad_concreto_kN_m3: float = 24.0,
        incluir_peso_propio: bool = False,
        apoyos: Optional[List[Apoyo]] = None,
        combinacion: str = "servicio",
        accion_termica: Optional[AccionTermicaReologica] = None,
    ):
        if longitud <= 0:
            raise ValueError("La longitud de la viga debe ser mayor a cero.")
        self.L = float(longitud)
        self.tipo = tipo.lower().strip()

        self.apoyos: List[Apoyo] = []
        if apoyos is not None and len(apoyos) > 0:
            for i, ap in enumerate(apoyos, 1):
                if ap.x < -1e-9 or ap.x > self.L + 1e-9:
                    raise ValueError(f"El apoyo en x={ap.x:.2f} m está fuera de [0, {self.L:.2f}].")
                etq = ap.etiqueta or f"A{i}"
                self.apoyos.append(Apoyo(
                    x=max(0.0, min(self.L, ap.x)),
                    tipo=ap.tipo, ky=ap.ky, ktheta=ap.ktheta, kx=ap.kx, etiqueta=etq
                ))
        else:
            # Inicialización desde presets clásicos
            if self.tipo == "simplemente_apoyada":
                a = float(pos_apoyos[0])
                b = self.L if pos_apoyos[1] is None else float(pos_apoyos[1])
                if a >= b:
                    raise ValueError("La posición del primer apoyo debe ser menor que la del segundo.")
                if a < 0 or b > self.L:
                    raise ValueError(f"Los apoyos [{a}, {b}] deben estar dentro de [0, {self.L}].")
                self.apoyos = [
                    Apoyo(x=a, tipo="fijo", etiqueta="A1"),
                    Apoyo(x=b, tipo="movil", etiqueta="A2"),
                ]
            elif self.tipo == "voladizo":
                self.apoyos = [Apoyo(x=0.0, tipo="empotrado", etiqueta="A1")]
            elif self.tipo == "doble_empotrada":
                self.apoyos = [
                    Apoyo(x=0.0, tipo="empotrado", etiqueta="A1"),
                    Apoyo(x=self.L, tipo="empotrado", etiqueta="A2"),
                ]
            elif self.tipo == "empotrada_movil":
                self.apoyos = [
                    Apoyo(x=0.0, tipo="empotrado", etiqueta="A1"),
                    Apoyo(x=self.L, tipo="movil", etiqueta="A2"),
                ]
            elif self.tipo == "guiada_movil":
                self.apoyos = [
                    Apoyo(x=0.0, tipo="guiado", etiqueta="A1"),
                    Apoyo(x=self.L, tipo="movil", etiqueta="A2"),
                ]
            elif self.tipo == "elastica":
                self.apoyos = [
                    Apoyo(x=0.0, tipo="elastico", ky=5000.0, ktheta=0.0, etiqueta="A1"),
                    Apoyo(x=self.L, tipo="elastico", ky=5000.0, ktheta=0.0, etiqueta="A2"),
                ]
            elif self.tipo == "personalizado":
                pass
            else:
                raise ValueError(f"Tipo de viga no soportado: {self.tipo}")

        # Atributos de compatibilidad directa con versiones previas
        self.x_apoyo1 = self.apoyos[0].x if len(self.apoyos) >= 1 else 0.0
        self.x_apoyo2 = self.apoyos[1].x if len(self.apoyos) >= 2 else self.L

        self.seccion = seccion
        self.E_GPa = float(E_GPa)
        self.E_Pa = self.E_GPa * 1e9
        self.sigma_adm = float(sigma_adm_MPa)
        self.limite_k = int(limite_deflexion_k)
        self.densidad_kN_m3 = float(densidad_concreto_kN_m3)
        self.incluir_peso_propio = bool(incluir_peso_propio)

        self.combinacion = combinacion if combinacion in COMBINACIONES_CARGA else "servicio"
        self.accion_termica = accion_termica if accion_termica is not None else AccionTermicaReologica()

        # Listas de cargas
        self.cargas_puntuales: List[CargaPuntual] = []
        self.cargas_distribuidas: List[CargaDistribuida] = []
        self.cargas_polinomicas: List[CargaPolinomica] = []
        self.momentos_concentrados: List[MomentoConcentrado] = []

    def agregar_apoyo(self, tipo: str, x: float, ky: float = 0.0, ktheta: float = 0.0,
                      kx: float = 0.0, etiqueta: str = ""):
        if x < 0 or x > self.L:
            raise ValueError(f"La posición del apoyo {x} está fuera de [0, {self.L} m].")
        etq = etiqueta or f"A{len(self.apoyos) + 1}"
        self.apoyos.append(Apoyo(x=float(x), tipo=tipo, ky=ky, ktheta=ktheta, kx=kx, etiqueta=etq))
        self.x_apoyo1 = self.apoyos[0].x if len(self.apoyos) >= 1 else 0.0
        self.x_apoyo2 = self.apoyos[1].x if len(self.apoyos) >= 2 else self.L

    def agregar_carga_puntual(self, P: float, x: float, Px: float = 0.0, origen: str = "L"):
        if x < 0 or x > self.L:
            raise ValueError(f"La posición {x} está fuera de la viga (0 - {self.L} m).")
        self.cargas_puntuales.append(CargaPuntual(float(P), float(x), float(Px), origen))

    def agregar_carga_distribuida(self, w1: float, w2: float, x1: float, x2: float, origen: str = "L"):
        x_min = max(0.0, min(float(x1), float(x2)))
        x_max = min(self.L, max(float(x1), float(x2)))
        if x_min == x_max:
            return
        if float(x1) > float(x2):
            w1, w2 = w2, w1
        self.cargas_distribuidas.append(CargaDistribuida(float(w1), float(w2), x_min, x_max, origen))

    def agregar_carga_polinomica(self, a0: float, a1: float, a2: float, a3: float,
                                 x1: float, x2: float, origen: str = "L"):
        x_min = max(0.0, min(float(x1), float(x2)))
        x_max = min(self.L, max(float(x1), float(x2)))
        if x_min == x_max:
            return
        self.cargas_polinomicas.append(
            CargaPolinomica(float(a0), float(a1), float(a2), float(a3), x_min, x_max, origen)
        )

    def agregar_momento(self, M0: float, x: float, origen: str = "L"):
        if x < 0 or x > self.L:
            raise ValueError(f"La posición {x} está fuera de la viga (0 - {self.L} m).")
        self.momentos_concentrados.append(MomentoConcentrado(float(M0), float(x), origen))

    def configurar_termica_reologica(
        self,
        delta_T_uniforme: float = 0.0,
        delta_T_gradiente: float = 0.0,
        retraccion_micro: float = 0.0,
        fluencia_phi: float = 0.0,
        alpha_T: float = 1.2e-5,
    ):
        self.accion_termica = AccionTermicaReologica(
            delta_T_uniforme=delta_T_uniforme,
            delta_T_gradiente=delta_T_gradiente,
            retraccion_micro=retraccion_micro,
            fluencia_phi=max(0.0, fluencia_phi),
            alpha_T=alpha_T,
        )

    def limpiar_cargas(self):
        self.cargas_puntuales.clear()
        self.cargas_distribuidas.clear()
        self.cargas_polinomicas.clear()
        self.momentos_concentrados.clear()

    def _factor_origen(self, origen: str) -> float:
        factores = COMBINACIONES_CARGA[self.combinacion]["factores"]
        return float(factores.get(origen.upper(), 1.0))

    def _evaluar_w_en_puntos(self, x_pts: np.ndarray, usar_factor: bool = True) -> np.ndarray:
        """
        Evalúa la intensidad total de carga vertical distribuida w(x) [kN/m]
        (positiva hacia abajo) sumando peso propio, distribuidas lineales/trapezoidales y polinómicas.
        """
        w = np.zeros_like(x_pts, dtype=float)

        if self.incluir_peso_propio and self.seccion is not None:
            f_D = self._factor_origen("D") if usar_factor else 1.0
            w += f_D * self.densidad_kN_m3 * self.seccion.area

        for cd in self.cargas_distribuidas:
            f = self._factor_origen(cd.origen) if usar_factor else 1.0
            dx = cd.x2 - cd.x1
            if dx <= 0 or f == 0.0:
                continue
            mask = (x_pts >= cd.x1 - 1e-12) & (x_pts <= cd.x2 + 1e-12)
            if np.any(mask):
                t = np.clip((x_pts[mask] - cd.x1) / dx, 0.0, 1.0)
                w[mask] += f * (cd.w1 + (cd.w2 - cd.w1) * t)

        for cp in self.cargas_polinomicas:
            f = self._factor_origen(cp.origen) if usar_factor else 1.0
            if cp.x2 <= cp.x1 or f == 0.0:
                continue
            mask = (x_pts >= cp.x1 - 1e-12) & (x_pts <= cp.x2 + 1e-12)
            if np.any(mask):
                w[mask] += f * cp.evaluar(x_pts[mask])

        return w

    def _evaluar_w_en_elemento(self, x1_el: float, x2_el: float, x_gauss: np.ndarray) -> np.ndarray:
        """Evalúa w(x) dentro del elemento [x1_el, x2_el] evitando saltos de bordes."""
        xc = 0.5 * (x1_el + x2_el)
        w = np.zeros_like(x_gauss, dtype=float)

        if self.incluir_peso_propio and self.seccion is not None:
            w += self._factor_origen("D") * self.densidad_kN_m3 * self.seccion.area

        for cd in self.cargas_distribuidas:
            f = self._factor_origen(cd.origen)
            dx = cd.x2 - cd.x1
            if dx <= 0 or f == 0.0:
                continue
            if cd.x1 - 1e-11 <= xc <= cd.x2 + 1e-11:
                t = np.clip((x_gauss - cd.x1) / dx, 0.0, 1.0)
                w += f * (cd.w1 + (cd.w2 - cd.w1) * t)

        for cp in self.cargas_polinomicas:
            f = self._factor_origen(cp.origen)
            if cp.x2 <= cp.x1 or f == 0.0:
                continue
            if cp.x1 - 1e-11 <= xc <= cp.x2 + 1e-11:
                w += f * cp.evaluar(x_gauss)

        return w

    def _calcular_grado_hiperestaticidad(self) -> int:
        n_reac_flexion = 0
        for ap in self.apoyos:
            if ap.tipo in ("movil", "fijo"):
                n_reac_flexion += 1
            elif ap.tipo in ("empotrado", "guiado"):
                n_reac_flexion += 2
            elif ap.tipo == "elastico":
                if ap.ky > 0:
                    n_reac_flexion += 1
                if ap.ktheta > 0:
                    n_reac_flexion += 1
        return max(0, n_reac_flexion - 2)

    def calcular_reacciones(self) -> Dict[str, float]:
        res = self.resolver(num_puntos=401)
        return res.reacciones

    def resolver(self, num_puntos: int = 2001) -> ResultadoViga:
        """
        Resuelve el sistema estructural completo por el Método de Elementos Finitos 1D:
        - Flexión de Euler-Bernoulli (v, theta) con funciones de forma cúbicas de Hermite.
        - Barra axial 1D (u) desacoplada para cargas horizontales y expansión/retracción térmica.
        - Cuadratura de Gauss-Legendre de 4 puntos para cargas distribuidas y polinómicas exactas.
        """
        if self.seccion is None:
            raise ValueError("No se ha asignado una sección transversal a la viga.")
        if not self.apoyos:
            raise ValueError("Debe definir al menos un apoyo estructural en la viga.")

        phi = max(0.0, self.accion_termica.fluencia_phi)
        E_eff_GPa = self.E_GPa / (1.0 + phi)

        I_m4 = self.seccion.inercia
        A_m2 = self.seccion.area
        h_m = self.seccion.altura

        # Unidades consistentes [kN, m, rad]
        E_kPa = E_eff_GPa * 1e6
        EI_kNm2 = E_kPa * I_m4
        EA_kN = E_kPa * A_m2

        # Malla nodal con discontinuidades clave
        puntos_clave = [0.0, self.L]
        for ap in self.apoyos:
            puntos_clave.append(ap.x)
        for cp in self.cargas_puntuales:
            puntos_clave.append(cp.x)
        for cd in self.cargas_distribuidas:
            puntos_clave.extend([cd.x1, cd.x2])
        for cp_poly in self.cargas_polinomicas:
            puntos_clave.extend([cp_poly.x1, cp_poly.x2])
        for mc in self.momentos_concentrados:
            puntos_clave.append(mc.x)

        n_elem_base = 201
        nodos_base = np.linspace(0.0, self.L, n_elem_base)
        nodos_todos = np.sort(np.concatenate([nodos_base, puntos_clave]))

        x_nodes_list = [nodos_todos[0]]
        for val in nodos_todos[1:]:
            if val - x_nodes_list[-1] > 1e-9:
                x_nodes_list.append(val)
        x_nodes = np.array(x_nodes_list, dtype=float)
        n_nodes = len(x_nodes)
        n_elems = n_nodes - 1

        def idx_nodo(x_val: float) -> int:
            return int(np.argmin(np.abs(x_nodes - x_val)))

        # Efectos térmicos y reológicos factorizados según combinación
        f_T = self._factor_origen("T")
        alpha_T = self.accion_termica.alpha_T
        eps_term = alpha_T * self.accion_termica.delta_T_uniforme * f_T
        eps_retrac = -(self.accion_termica.retraccion_micro * 1e-6) * f_T
        eps_axial_0 = eps_term + eps_retrac
        kappa_T = (alpha_T * self.accion_termica.delta_T_gradiente * f_T) / max(h_m, 1e-4)

        # Ensamblaje Flexión (2 GDL/nodo: v, theta)
        n_dof_b = 2 * n_nodes
        K_b = np.zeros((n_dof_b, n_dof_b), dtype=float)
        F_b = np.zeros(n_dof_b, dtype=float)

        xi_gp, w_gp = np.polynomial.legendre.leggauss(4)

        for e in range(n_elems):
            x1_e = x_nodes[e]
            x2_e = x_nodes[e + 1]
            L_e = x2_e - x1_e

            c = EI_kNm2 / (L_e ** 3)
            k_loc = c * np.array([
                [12.0,       6.0 * L_e,      -12.0,       6.0 * L_e],
                [6.0 * L_e,  4.0 * L_e ** 2, -6.0 * L_e,  2.0 * L_e ** 2],
                [-12.0,     -6.0 * L_e,       12.0,      -6.0 * L_e],
                [6.0 * L_e,  2.0 * L_e ** 2, -6.0 * L_e,  4.0 * L_e ** 2],
            ], dtype=float)

            s_gp = 0.5 * L_e * (xi_gp + 1.0)
            x_gp = x1_e + s_gp
            t_gp = s_gp / L_e
            w_vals = self._evaluar_w_en_elemento(x1_e, x2_e, x_gp)

            N1 = 1.0 - 3.0 * t_gp**2 + 2.0 * t_gp**3
            N2 = L_e * (t_gp - 2.0 * t_gp**2 + t_gp**3)
            N3 = 3.0 * t_gp**2 - 2.0 * t_gp**3
            N4 = L_e * (-t_gp**2 + t_gp**3)

            J = 0.5 * L_e
            f_eq_dist = np.array([
                np.sum(w_gp * (-w_vals) * N1) * J,
                np.sum(w_gp * (-w_vals) * N2) * J,
                np.sum(w_gp * (-w_vals) * N3) * J,
                np.sum(w_gp * (-w_vals) * N4) * J,
            ], dtype=float)

            f_eq_term = EI_kNm2 * kappa_T * np.array([0.0, -1.0, 0.0, 1.0], dtype=float)

            dofs = [2 * e, 2 * e + 1, 2 * (e + 1), 2 * (e + 1) + 1]
            K_b[np.ix_(dofs, dofs)] += k_loc
            F_b[dofs] += (f_eq_dist + f_eq_term)

        K_b_estruc = K_b.copy()
        F_b_nodal_cargas = F_b.copy()

        for cp in self.cargas_puntuales:
            f = self._factor_origen(cp.origen)
            ni = idx_nodo(cp.x)
            F_b[2 * ni] -= f * cp.P
            F_b_nodal_cargas[2 * ni] -= f * cp.P

        for mc in self.momentos_concentrados:
            f = self._factor_origen(mc.origen)
            ni = idx_nodo(mc.x)
            F_b[2 * ni + 1] += f * mc.M0
            F_b_nodal_cargas[2 * ni + 1] += f * mc.M0

        restringidos_v = set()
        restringidos_theta = set()
        apoyo_nodos = []

        for ap in self.apoyos:
            ni = idx_nodo(ap.x)
            apoyo_nodos.append((ap, ni))
            if ap.tipo in ("movil", "fijo"):
                restringidos_v.add(ni)
            elif ap.tipo in ("empotrado", "guiado"):
                restringidos_v.add(ni)
                restringidos_theta.add(ni)
            elif ap.tipo == "elastico":
                if ap.ky > 0:
                    K_b[2 * ni, 2 * ni] += ap.ky
                if ap.ktheta > 0:
                    K_b[2 * ni + 1, 2 * ni + 1] += ap.ktheta

        restringidos_b = sorted(
            [2 * ni for ni in restringidos_v] + [2 * ni + 1 for ni in restringidos_theta]
        )
        libres_b = [i for i in range(n_dof_b) if i not in set(restringidos_b)]

        if len(libres_b) == n_dof_b and not any(ap.tipo == "elastico" and (ap.ky > 0 or ap.ktheta > 0) for ap in self.apoyos):
            raise ValueError("La viga no tiene restricciones verticales suficientes (estructura inestable).")

        d_b = np.zeros(n_dof_b, dtype=float)
        if libres_b:
            K_red = K_b[np.ix_(libres_b, libres_b)]
            F_red = F_b[libres_b]
            cond_num = np.linalg.cond(K_red)
            if not np.isfinite(cond_num) or cond_num > 1e12:
                raise ValueError(
                    "Inestabilidad cinemática (mecanismo): los apoyos seleccionados no impiden "
                    "el desplazamiento rígido o el giro libre de la viga."
                )
            d_b[libres_b] = np.linalg.solve(K_red, F_red)

        R_b_total = K_b_estruc @ d_b - F_b_nodal_cargas

        # Ensamblaje Axial (1 GDL/nodo: u)
        K_a = np.zeros((n_nodes, n_nodes), dtype=float)
        F_a = np.zeros(n_nodes, dtype=float)
        for e in range(n_elems):
            L_e = x_nodes[e + 1] - x_nodes[e]
            k_ax = (EA_kN / L_e) * np.array([[1.0, -1.0], [-1.0, 1.0]])
            f_ax_t = EA_kN * eps_axial_0 * np.array([-1.0, 1.0])
            K_a[np.ix_([e, e + 1], [e, e + 1])] += k_ax
            F_a[[e, e + 1]] += f_ax_t

        K_a_estruc = K_a.copy()
        F_a_nodal = F_a.copy()

        tiene_carga_axial = (abs(eps_axial_0) > 1e-12)
        for cp in self.cargas_puntuales:
            if abs(cp.Px) > 1e-12:
                f = self._factor_origen(cp.origen)
                ni = idx_nodo(cp.x)
                F_a[ni] += f * cp.Px
                F_a_nodal[ni] += f * cp.Px
                tiene_carga_axial = True

        restringidos_u = set()
        for ap, ni in apoyo_nodos:
            if ap.tipo in ("fijo", "empotrado"):
                restringidos_u.add(ni)
            elif ap.tipo == "elastico" and ap.kx > 0:
                K_a[ni, ni] += ap.kx

        u_a = np.zeros(n_nodes, dtype=float)
        R_a_total = np.zeros(n_nodes, dtype=float)

        tiene_resorte_x = any(ap.tipo == "elastico" and ap.kx > 0 for ap in self.apoyos)
        if restringidos_u or tiene_resorte_x:
            libres_a = [i for i in range(n_nodes) if i not in restringidos_u]
            if libres_a:
                u_a[libres_a] = np.linalg.solve(K_a[np.ix_(libres_a, libres_a)], F_a[libres_a])
            R_a_total = K_a_estruc @ u_a - F_a_nodal
        elif tiene_carga_axial:
            raise ValueError(
                "Inestabilidad axial: existen fuerzas horizontales o variación térmica uniforme, "
                "pero ningún apoyo restringe el eje X (use al menos un Apoyo Fijo o Empotramiento)."
            )

        # Detalle de reacciones
        reacciones: Dict[str, float] = {}
        reacciones_detalle: List[Dict[str, Any]] = []

        for ap, ni in apoyo_nodos:
            rx = 0.0
            ry = 0.0
            rm = 0.0

            if ap.tipo == "movil":
                ry = float(R_b_total[2 * ni])
            elif ap.tipo == "fijo":
                rx = float(R_a_total[ni])
                ry = float(R_b_total[2 * ni])
            elif ap.tipo == "empotrado":
                rx = float(R_a_total[ni])
                ry = float(R_b_total[2 * ni])
                rm = float(R_b_total[2 * ni + 1])
            elif ap.tipo == "guiado":
                ry = float(R_b_total[2 * ni])
                rm = float(R_b_total[2 * ni + 1])
            elif ap.tipo == "elastico":
                ry = float(-ap.ky * d_b[2 * ni])
                rm = float(-ap.ktheta * d_b[2 * ni + 1])
                rx = float(-ap.kx * u_a[ni])

            reacciones_detalle.append({
                "etiqueta": ap.etiqueta,
                "tipo": ap.tipo,
                "x": ap.x,
                "Rx": rx,
                "Ry": ry,
                "M": rm,
            })

            reacciones[f"{ap.etiqueta}_Rx"] = rx
            reacciones[f"{ap.etiqueta}_Ry"] = ry
            reacciones[f"{ap.etiqueta}_M"] = rm

        if len(reacciones_detalle) >= 1:
            reacciones["R1"] = reacciones_detalle[0]["Ry"]
            reacciones["pos_R1"] = reacciones_detalle[0]["x"]
            reacciones["R_vertical"] = reacciones_detalle[0]["Ry"]
            reacciones["M_empotramiento"] = reacciones_detalle[0]["M"]
        if len(reacciones_detalle) >= 2:
            reacciones["R2"] = reacciones_detalle[1]["Ry"]
            reacciones["pos_R2"] = reacciones_detalle[1]["x"]

        # Evaluación continua de campos V(x), M(x), N(x), theta(x), v(x), u(x)
        sub_pts = max(5, int(np.ceil(num_puntos / max(n_elems, 1))))
        x_list, V_list, M_list, N_list, theta_list, v_list, u_list = [], [], [], [], [], [], []

        for e in range(n_elems):
            x1_e = x_nodes[e]
            x2_e = x_nodes[e + 1]
            L_e = x2_e - x1_e

            d_e = d_b[[2 * e, 2 * e + 1, 2 * (e + 1), 2 * (e + 1) + 1]]
            c = EI_kNm2 / (L_e ** 3)
            k_loc = c * np.array([
                [12.0,       6.0 * L_e,      -12.0,       6.0 * L_e],
                [6.0 * L_e,  4.0 * L_e ** 2, -6.0 * L_e,  2.0 * L_e ** 2],
                [-12.0,     -6.0 * L_e,       12.0,      -6.0 * L_e],
                [6.0 * L_e,  2.0 * L_e ** 2, -6.0 * L_e,  4.0 * L_e ** 2],
            ], dtype=float)

            s_gp = 0.5 * L_e * (xi_gp + 1.0)
            x_gp = x1_e + s_gp
            t_gp = s_gp / L_e
            w_vals = self._evaluar_w_en_elemento(x1_e, x2_e, x_gp)
            N1g = 1.0 - 3.0 * t_gp**2 + 2.0 * t_gp**3
            N2g = L_e * (t_gp - 2.0 * t_gp**2 + t_gp**3)
            N3g = 3.0 * t_gp**2 - 2.0 * t_gp**3
            N4g = L_e * (-t_gp**2 + t_gp**3)
            J = 0.5 * L_e
            f_eq_e = np.array([
                np.sum(w_gp * (-w_vals) * N1g) * J,
                np.sum(w_gp * (-w_vals) * N2g) * J,
                np.sum(w_gp * (-w_vals) * N3g) * J,
                np.sum(w_gp * (-w_vals) * N4g) * J,
            ]) + EI_kNm2 * kappa_T * np.array([0.0, -1.0, 0.0, 1.0])

            f_int_e = k_loc @ d_e - f_eq_e
            V_left = f_int_e[0]
            M_left = -f_int_e[1]
            N_e = EA_kN * ((u_a[e + 1] - u_a[e]) / L_e - eps_axial_0)

            endpoint = (e == n_elems - 1)
            t_sub = np.linspace(0.0, 1.0, sub_pts, endpoint=endpoint)
            s_sub = t_sub * L_e
            x_sub = x1_e + s_sub

            N1 = 1.0 - 3.0 * t_sub**2 + 2.0 * t_sub**3
            N2 = L_e * (t_sub - 2.0 * t_sub**2 + t_sub**3)
            N3 = 3.0 * t_sub**2 - 2.0 * t_sub**3
            N4 = L_e * (-t_sub**2 + t_sub**3)

            dN1 = (-6.0 * t_sub + 6.0 * t_sub**2) / L_e
            dN2 = 1.0 - 4.0 * t_sub + 3.0 * t_sub**2
            dN3 = (6.0 * t_sub - 6.0 * t_sub**2) / L_e
            dN4 = -2.0 * t_sub + 3.0 * t_sub**2

            v_sub = N1 * d_e[0] + N2 * d_e[1] + N3 * d_e[2] + N4 * d_e[3]
            th_sub = dN1 * d_e[0] + dN2 * d_e[1] + dN3 * d_e[2] + dN4 * d_e[3]
            u_sub = (1.0 - t_sub) * u_a[e] + t_sub * u_a[e + 1]

            if np.any(w_vals != 0.0):
                V_sub = np.empty_like(s_sub)
                M_sub = np.empty_like(s_sub)
                for idx_s, s_val in enumerate(s_sub):
                    if s_val == 0.0:
                        V_sub[idx_s] = V_left
                        M_sub[idx_s] = M_left
                    else:
                        s_loc_gp = 0.5 * s_val * (xi_gp + 1.0)
                        w_loc = self._evaluar_w_en_elemento(x1_e, x2_e, x1_e + s_loc_gp)
                        int_w = np.sum(w_gp * w_loc) * (0.5 * s_val)
                        int_mw = np.sum(w_gp * w_loc * (s_val - s_loc_gp)) * (0.5 * s_val)
                        V_sub[idx_s] = V_left - int_w
                        M_sub[idx_s] = M_left + V_left * s_val - int_mw
            else:
                V_sub = np.full_like(s_sub, V_left)
                M_sub = M_left + V_left * s_sub

            x_list.append(x_sub)
            V_list.append(V_sub)
            M_list.append(M_sub)
            N_list.append(np.full_like(s_sub, N_e))
            theta_list.append(th_sub)
            v_list.append(v_sub)
            u_list.append(u_sub)

        x = np.concatenate(x_list)
        V = np.concatenate(V_list)
        M = np.concatenate(M_list)
        N_arr = np.concatenate(N_list)
        theta = np.concatenate(theta_list)
        v = np.concatenate(v_list)
        u_m = np.concatenate(u_list)

        v_mm = v * 1000.0
        u_mm = u_m * 1000.0

        V_max = float(np.max(V))
        V_min = float(np.min(V))
        idx_V_abs = int(np.argmax(np.abs(V)))
        V_abs_max = float(np.abs(V[idx_V_abs]))
        x_V_max = float(x[idx_V_abs])

        M_max = float(np.max(M))
        M_min = float(np.min(M))
        idx_M_abs = int(np.argmax(np.abs(M)))
        M_abs_max = float(np.abs(M[idx_M_abs]))
        x_M_max = float(x[idx_M_abs])

        N_abs_max = float(np.max(np.abs(N_arr)))

        v_max = float(np.max(v_mm))
        v_min = float(np.min(v_mm))
        idx_v_abs = int(np.argmax(np.abs(v_mm)))
        v_abs_max = float(np.abs(v_mm[idx_v_abs]))
        x_v_max = float(x[idx_v_abs])

        sigma_max = float(
            np.max(np.abs(N_arr) / max(A_m2, 1e-12) + np.abs(M) / max(self.seccion.w_min, 1e-12)) / 1000.0
        )
        cumple_esfuerzo = bool(sigma_max <= self.sigma_adm)

        deflexion_limite_mm = (self.L / float(self.limite_k)) * 1000.0
        cumple_deflexion = bool(v_abs_max <= deflexion_limite_mm)
        cumple_global = cumple_esfuerzo and cumple_deflexion

        return ResultadoViga(
            x=x,
            V=V,
            M=M,
            N=N_arr,
            theta=theta,
            v=v,
            v_mm=v_mm,
            u_mm=u_mm,
            reacciones=reacciones,
            reacciones_detalle=reacciones_detalle,
            V_max=V_max,
            V_min=V_min,
            V_abs_max=V_abs_max,
            x_V_max=x_V_max,
            M_max=M_max,
            M_min=M_min,
            M_abs_max=M_abs_max,
            x_M_max=x_M_max,
            N_abs_max=N_abs_max,
            v_max=v_max,
            v_min=v_min,
            v_abs_max=v_abs_max,
            x_v_max=x_v_max,
            sigma_max=sigma_max,
            sigma_adm=self.sigma_adm,
            cumple_esfuerzo=cumple_esfuerzo,
            deflexion_limite=deflexion_limite_mm,
            limite_k=self.limite_k,
            cumple_deflexion=cumple_deflexion,
            cumple_global=cumple_global,
            tipo_viga=self.tipo,
            L=self.L,
            E_GPa=self.E_GPa,
            E_efectivo_GPa=E_eff_GPa,
            seccion=self.seccion,
            peso_propio_incluido=self.incluir_peso_propio,
            combinacion_usada=self.combinacion,
            grado_hiperestaticidad=self._calcular_grado_hiperestaticidad(),
        )


def analizar_viga_desde_diccionario(config: Dict[str, Any]) -> Tuple[VigaIsostatica, ResultadoViga]:
    """
    Punto de entrada de cálculo puro, 100% independiente de la interfaz gráfica.
    Permite importar este módulo desde scripts, pruebas unitarias o servicios externos
    y ejecutar un análisis estructural completo sin abrir ninguna ventana.
    """
    sec_d = config.get("seccion", {})
    tipo_s = sec_d.get("tipo", "rectangular")
    params = sec_d.get("parametros", {})

    if tipo_s == "rectangular":
        seccion = crear_seccion_rectangular(
            float(params.get("base", 0.30)), float(params.get("altura", 0.60))
        )
    elif tipo_s == "perfil_i":
        seccion = crear_seccion_perfil_i(
            float(params.get("bf", 0.25)), float(params.get("d", 0.45)),
            float(params.get("tf", 0.018)), float(params.get("tw", 0.010))
        )
    else:
        seccion = crear_seccion_bulb_tee(
            b1=float(params.get("b1", 0.80)), b2=float(params.get("b2", 0.60)),
            b3=float(params.get("b3", 0.20)), b4=float(params.get("b4", 0.10)),
            d1=float(params.get("d1", 1.20)), d2=float(params.get("d2", 0.10)),
            d3=float(params.get("d3", 0.15)), d4=float(params.get("d4", 0.20)),
            d5=float(params.get("d5", 0.10)), d6=float(params.get("d6", 0.05)),
            d7=float(params.get("d7", 0.05)),
            t1=float(params.get("t1", 0.08)), t2=float(params.get("t2", 0.06)),
            c1=float(params.get("c1", 0.03)),
        )

    apoyos_obj = None
    if config.get("apoyos_detalle"):
        apoyos_obj = [
            Apoyo(
                x=float(ap["x"]), tipo=ap["tipo"],
                ky=float(ap.get("ky", 0.0)), ktheta=float(ap.get("ktheta", 0.0)),
                kx=float(ap.get("kx", 0.0)), etiqueta=f"A{i}"
            )
            for i, ap in enumerate(config["apoyos_detalle"], 1)
        ]

    term_d = config.get("accion_termica", {})
    accion_termica = AccionTermicaReologica(
        delta_T_uniforme=float(term_d.get("delta_T_uniforme", 0.0)),
        delta_T_gradiente=float(term_d.get("delta_T_gradiente", 0.0)),
        retraccion_micro=float(term_d.get("retraccion_micro", 0.0)),
        fluencia_phi=float(term_d.get("fluencia_phi", 0.0)),
        alpha_T=float(term_d.get("alpha_T", 1.2e-5)),
    )

    viga = VigaIsostatica(
        longitud=float(config.get("longitud", 8.0)),
        tipo=config.get("tipo_viga", "simplemente_apoyada"),
        pos_apoyos=tuple(config.get("apoyos", (0.0, None))),
        seccion=seccion,
        E_GPa=float(config.get("E_GPa", 24.0)),
        sigma_adm_MPa=float(config.get("sigma_adm", 180.0)),
        limite_deflexion_k=int(config.get("limite_k", 360)),
        incluir_peso_propio=bool(config.get("incluir_peso_propio", True)),
        apoyos=apoyos_obj,
        combinacion=config.get("combinacion", "servicio"),
        accion_termica=accion_termica,
    )

    for c in config.get("cargas", []):
        orig = c.get("origen", "L")
        if c["tipo"] == "puntual":
            viga.agregar_carga_puntual(c["P"], c["x"], Px=c.get("Px", 0.0), origen=orig)
        elif c["tipo"] == "distribuida":
            viga.agregar_carga_distribuida(c["w1"], c["w2"], c["x1"], c["x2"], origen=orig)
        elif c["tipo"] == "polinomica":
            viga.agregar_carga_polinomica(
                c["a0"], c["a1"], c["a2"], c["a3"], c["x1"], c["x2"], origen=orig
            )
        elif c["tipo"] == "momento":
            viga.agregar_momento(c["M0"], c["x"], origen=orig)

    res = viga.resolver()
    return viga, res
