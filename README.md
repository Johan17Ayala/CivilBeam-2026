# CivilBeam 2026 — Análisis Estructural de Vigas y Diagramas de Solicitaciones

Aplicación de escritorio en Python (Flet Material 3) con núcleo numérico 100 % desacoplado de la interfaz gráfica para analizar vigas isostáticas, hiperestáticas y sobre apoyos elásticos bajo combinaciones normativas NSR-10, consultar el cálculo **paso a paso** y exportar memorias formales a **Microsoft Word (`.docx`)**.

---

## 1. Introducción

**CivilBeam 2026** automatiza el análisis estructural lineal de vigas sometidas simultáneamente a múltiples tipos de apoyos, cargas transversales, cargas horizontales, momentos concentrados y acciones térmicas o reológicas.

Sus capacidades principales son:
- **Motor FEM 1D desacoplado (`app/modelo.py`):** Resuelve sistemas isostáticos e hiperestáticos mediante el Método de Elementos Finitos 1D sin requerir Flet ni ventanas gráficas, lo que permite importarlo y probarlo desde consola o scripts.
- **5 tipos de apoyo estructural:** Simple/Móvil (`movil`), Articulado/Fijo (`fijo`), Empotrado rígido (`empotrado`), Empotramiento guiado/deslizante (`guiado`) y Apoyo elástico traslacional/rotacional (`elastico`).
- **Cargas por geometría y por origen (NSR-10 Título B):** Puntuales ($P, P_x$), distribuidas uniformes, triangulares y trapezoidales, momentos concentrados ($M_0$), cargas no lineales/polinómicas ($w(u) = a_0 + a_1 u + a_2 u^2 + a_3 u^3$), peso propio automático ($\gamma \cdot A$) y efectos térmicos/reológicos ($\Delta T$ uniforme, gradiente térmico $\Delta T_g$, retracción y fluencia lenta $\varphi$).
- **Revisión paso a paso y exportación a Word:** Pestaña interactiva **Paso a Paso** con fórmulas, sustituciones numéricas y extracción directa a `.docx` (`app/paso_a_paso.py`), además de memoria de cálculo automática basada en plantilla (`app/reporte.py`).
- **Persistencia local en SQLite (`app/db.py`):** Historial de proyectos y cálculos con búsqueda, reapertura en formulario y comparación superpuesta de diagramas.

---

## 2. Background y Antecedentes

En el diseño y revisión de elementos horizontales de ingeniería civil (vigas de edificación, pasarelas peatonales, vigas de puente y vigas carril), la determinación exacta de la fuerza axial $N(x)$, fuerza cortante $V(x)$, momento flector $M(x)$, giro elástico $\theta(x)$ y flecha vertical $v(x)$ sustenta las verificaciones de resistencia y serviciabilidad exigidas por el reglamento **NSR-10 (Títulos B y C)** y la especificación **AISC 360-16**.

Las calculadoras académicas clásicas suelen restringirse a casos canónicos aislados (viga simplemente apoyada con una carga puntual o distribuida uniforme) y no contemplan apoyos elásticos, empotramientos guiados, cargas polinómicas ni deformaciones impuestas por temperatura o retracción/fluencia lenta.

Este proyecto surge en el curso **Programación II (Grupo 18, Semestre 2026-III)** de la **Universidad Distrital Francisco José de Caldas — Facultad Tecnológica**, integrando:
- El módulo geométrico poligonal `sections.py` (*Teorema de Green / Gauss*) previamente desarrollado en la asignatura (`pySections`).
- Un solucionador matricial general por Elementos Finitos 1D con cuadratura de Gauss-Legendre.
- Una arquitectura modular en capas que separa completamente el cálculo ingenieril, las gráficas vectorizadas, la base de datos SQLite, los reportes en Word y la interfaz gráfica de escritorio.

---

## 3. Estructura del Código

```text
analisis_vigas/
│
├── main.py                        # Punto de entrada GUI (Flet + NavigationRail de 3 vistas)
├── ejecutar_sin_interfaz.py       # Demostración headless sin Flet (cálculo + Word automático)
├── ejecutar.bat                   # Lanzador automático en 1 clic para Windows (CMD)
├── ejecutar.ps1                   # Lanzador alternativo para PowerShell
├── requirements.txt               # Dependencias con versiones fijadas
├── .gitignore                     # Exclusiones (.venv, __pycache__, datos/*.db, reportes/, *.png)
├── README.md                      # Documentación del proyecto
│
├── app/
│   ├── __init__.py
│   ├── modelo.py                  # Motor FEM 1D (VigaIsostatica, Apoyo, cargas, combinaciones NSR-10)
│   ├── sections.py                # Motor geométrico poligonal pySections (Teorema de Green)
│   ├── secciones.py               # Adaptadores de secciones (Rectangular, PerfilI, Bulb-Tee)
│   ├── paso_a_paso.py             # Desglose explicativo en 6 pasos y exportador Word paso a paso
│   ├── reporte.py                 # Generador de memoria Word oficial con docxtpl
│   ├── graficas.py                # Gráficas técnicas de 4 paneles y comparativas (Matplotlib)
│   ├── db.py                      # Persistencia relacional SQLite (tablas proyectos y calculos)
│   │
│   └── ui/                        # Capa de interfaz gráfica (Flet Material 3)
│       ├── __init__.py
│       ├── calculo_view.py        # Pestaña "Cálculo": apoyos, cargas, sección y diagramas
│       ├── paso_a_paso_view.py    # Pestaña "Paso a Paso": revisión de ecuaciones y botón a Word
│       └── historial_view.py      # Pestaña "Historial BD": consulta, reapertura y comparación
│
├── plantillas/
│   └── memoria.docx               # Plantilla Word institucional con etiquetas Jinja2
│
├── herramientas/
│   └── crear_plantilla.py         # Script generador de plantillas/memoria.docx
│
├── ejemplos/
│   └── memoria_ejemplo.docx       # Ejemplo de memoria Word generada
│
└── tests/
    ├── __init__.py
    └── test_modelo.py             # Suite de 11 pruebas unitarias pytest (analíticas + BD + Word)
```

---

## 4. Cómo Funciona / Marco Matemático

### 4.1 Propiedades Geométricas por Teorema de Green (`app/sections.py` y `app/secciones.py`)
Cada sección transversal (rectangular, perfil I de 12 vértices o viga puente *Bulb-Tee*) se representa como un polígono cerrado en 2D y sus propiedades se obtienen mediante la fórmula del agrimensor de Gauss:

$$A = \frac{1}{2} \sum_{i=0}^{n-1} (x_i y_{i+1} - x_{i+1} y_i), \qquad I_x = \frac{1}{12} \sum_{i=0}^{n-1} (y_i^2 + y_i y_{i+1} + y_{i+1}^2)(x_i y_{i+1} - x_{i+1} y_i) - A\bar{y}^2$$

El módulo resistente es $W_{\text{mín}} = I_x / c_{\text{máx}}$, y el peso propio distribuido se calcula automáticamente cuando está activo como $w_{pp} = \gamma \cdot A$.

### 4.2 Módulo Efectivo por Fluencia Lenta y Acciones Térmicas
Para considerar fluencia lenta del material ($\varphi \ge 0$), el módulo de elasticidad longitudinal se ajusta a:

$$E_{\text{eff}} = \frac{E}{1 + \varphi}$$

Las acciones térmicas y de retracción se incorporan como deformaciones iniciales equivalentes factorizadas según la combinación de carga activa ($f_T$):

$$\varepsilon_0 = f_T \left(\alpha_T \Delta T_{\text{unif}} - \varepsilon_{\text{retrac}}\right), \qquad \kappa_T = \frac{f_T \, \alpha_T \, \Delta T_{\text{grad}}}{h}$$

### 4.3 Formulación por Elementos Finitos 1D (`app/modelo.py`)
La viga de longitud $L$ se discretiza en una malla adaptativa ($N_{\text{base}} = 201$ nodos enriquecida exactamente en todas las abscisas de apoyos y puntos de aplicación/inicio/fin de cargas). Cada nodo posee **3 grados de libertad**: desplazamiento axial $u$, deflexión transversal $v$ y giro $\theta$.

- **Flexión de Euler-Bernoulli ($v, \theta$) con funciones cúbicas de Hermite:**
  $$EI \frac{d^4 v}{dx^4} = -q(x), \qquad [K_b^e]\{d_b^e\} = \{F_b^e\}$$
- **Barra axial 1D desacoplada ($u$):**
  $$EA \frac{d^2 u}{dx^2} = -q_x(x)$$
- **Integración exacta de cargas distribuidas y polinómicas:** Las fuerzas nodales consistentes para cargas uniformes, triangulares, trapezoidales y polinómicas $w(u) = a_0 + a_1 u + a_2 u^2 + a_3 u^3$ se evalúan mediante **cuadratura de Gauss-Legendre de 4 puntos**.
- **Condiciones de apoyo y resortes:** Los grados de libertad restringidos se imponen en el sistema global $K \cdot U = F$, sumando directamente las rigideces elásticas ($k_y, k_\theta, k_x$) en la diagonal de $K$ y recuperando reacciones exactas mediante $R = K_{\text{orig}} U - F_{\text{nodal}}$.

### 4.4 Combinaciones de Carga y Chequeo Normativo (NSR-10)
Se soportan las combinaciones `servicio` y `nsr_1` a `nsr_6` (NSR-10 B.2.4-1 a B.2.4-6) aplicadas por origen (`D`, `L`, `W`, `E`, `S`, `T`), verificando al final:

$$\sigma_{\text{máx}} = \frac{|M|_{\text{máx}} \cdot c}{I_x} + \frac{|N|_{\text{máx}}}{A} \le \sigma_{\text{adm}}, \qquad |\delta|_{\text{máx}} \le \frac{L}{k} \quad (k \in \{180, 240, 360, 480\})$$

---

## 5. Instalación Paso a Paso

### Requisitos previos
- **Python 3.10 o superior** (probado en Windows con Python 3.14).
- Conexión a Internet la primera vez para descargar las librerías de `requirements.txt`.

### Pasos de instalación (terminal / PowerShell)

1. **Clonar el repositorio:**
   ```powershell
   git clone https://github.com/Johan17Ayala/CivilBeam-2026.git
   cd CivilBeam-2026
   ```

2. **Crear el entorno virtual `.venv`:**
   ```powershell
   python -m venv .venv
   ```

3. **Activar el entorno virtual:**
   - En **PowerShell (Windows)**:
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
   - En **CMD (Windows)**:
     ```bat
     .venv\Scripts\activate.bat
     ```
   - En **Linux / macOS**:
     ```bash
     source .venv/bin/activate
     ```

4. **Instalar dependencias:**
   ```powershell
   pip install -r requirements.txt
   ```

5. **Verificar la instalación ejecutando las pruebas unitarias:**
   ```powershell
   pytest -v
   ```
   *(Debe reportar `11 passed`).*

6. **Ejecutar la aplicación gráfica:**
   ```powershell
   python main.py
   ```
   *Atajo en Windows:* también puedes hacer doble clic en `ejecutar.bat` (crea `.venv`, instala `requirements.txt` si falta y abre la ventana automáticamente).

---

## 6. Uso con un Ejemplo Básico

### Opción A — Uso en la aplicación de escritorio (`python main.py`)
1. En la pestaña **Cálculo**, define la longitud $L$ (por ejemplo `6.0 m`), selecciona la sección transversal y los apoyos (por ejemplo, fijo en $x = 0\text{ m}$ y móvil en $x = 6\text{ m}$).
2. Agrega una o varias cargas (puntuales, distribuidas uniformes/trapezoidales/polinómicas o momentos) con su origen (`D`, `L`, `W`, `E`, `S`, `T`) y presiona **CALCULAR VIGA**.
3. Revisa los diagramas de $N(x)$, $V(x)$, $M(x)$ y $\delta(x)$.
4. Abre la pestaña **Paso a Paso** (o pulsa **Ver Cálculo Paso a Paso**) para inspeccionar los 6 pasos detallados y presiona **Extraer Paso a Paso a Word (.docx)** para guardar el documento en `reportes/`.

### Opción B — Uso sin interfaz gráfica (módulo independiente en Python)
El repositorio incluye el script `ejecutar_sin_interfaz.py` como demostración directa de uso headless:

```python
from app.modelo import analizar_viga_desde_diccionario
from app.paso_a_paso import generar_pasos_calculo, generar_word_paso_a_paso

config = {
    "longitud": 8.0,
    "tipo_viga": "empotrada_movil",
    "apoyos_detalle": [
        {"tipo": "empotrado", "x": 0.0},
        {"tipo": "movil", "x": 8.0},
    ],
    "E_GPa": 24.0,
    "sigma_adm": 180.0,
    "limite_k": 360,
    "incluir_peso_propio": True,
    "combinacion": "nsr_2",
    "seccion": {"tipo": "rectangular", "parametros": {"base": 0.30, "altura": 0.60}},
    "cargas": [
        {"tipo": "distribuida", "w1": 18.0, "w2": 18.0, "x1": 0.0, "x2": 8.0, "origen": "D"},
        {"tipo": "puntual", "P": 35.0, "Px": 10.0, "x": 4.0, "origen": "L"},
    ],
}

viga, resultado = analizar_viga_desde_diccionario(config)
pasos = generar_pasos_calculo(viga, resultado)
print(f"|V| máx = {resultado.V_abs_max:.2f} kN | |M| máx = {resultado.M_abs_max:.2f} kN·m")
generar_word_paso_a_paso(viga, resultado, "Proyecto Demo", "Viga V-101", "Ing. Civil")
```

También puedes correr directamente desde consola:
```powershell
python ejecutar_sin_interfaz.py
```

---

## 7. Dependencias

Listado fijado en `requirements.txt`:

| Paquete | Versión | Uso en el proyecto |
| :--- | :--- | :--- |
| `flet` | `1.0.5` | Interfaz gráfica de escritorio Material 3 |
| `flet-desktop` | `1.0.5` | Runtime nativo de ventana desktop para Flet |
| `numpy` | `2.5.4` | Álgebra lineal FEM 1D, mallas adaptativas y cuadratura de Gauss-Legendre |
| `scipy` | `1.18.1` | Soporte científico y utilidades numéricas |
| `matplotlib` | `3.11.2` | Generación de diagramas $V(x), M(x), \theta(x), v(x)$ y comparativas |
| `docxtpl` | `0.20.2` | Rellenado de plantilla Word institucional (`plantillas/memoria.docx`) |
| `python-docx` | `1.2.0` | Construcción directa del documento Word paso a paso (`app/paso_a_paso.py`) |
| `pytest` | `9.2.0` | Ejecución de pruebas unitarias automatizadas (`tests/test_modelo.py`) |

Además se utiliza `sqlite3` de la biblioteca estándar de Python para la base de datos local (`datos/vigas.db`).

---

## 8. Créditos y Contribuciones

- **Universidad Distrital Francisco José de Caldas** — Facultad Tecnológica, Ingeniería Civil (*Programación II*, Grupo 18, 2026-III).
- **Propietario del repositorio:** [@Johan17Ayala](https://github.com/Johan17Ayala)
- **Colaborador:** [@herrerita1414](https://github.com/herrerita1414)

### Cómo contribuir
1. Clona el repositorio (`git clone https://github.com/Johan17Ayala/CivilBeam-2026.git`) o crea una rama descriptiva (`git checkout -b feature/nueva-mejora`).
2. Realiza tus cambios manteniendo la separación entre el núcleo numérico (`app/modelo.py`, `app/paso_a_paso.py`) y la capa UI (`app/ui/`).
3. Ejecuta `pytest -v` y verifica que todas las pruebas unitarias pasen antes de hacer `commit` y `push`.
