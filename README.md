# CivilBeam 2026: Análisis de Diagramas de Cortante, Momento y Deflexión en Vigas con Cargas Arbitrarias

**Universidad Distrital Francisco José de Caldas**  
*Facultad Tecnológica — Proyecto Curricular de Ingeniería Civil*  
*Espacio Académico: Programación II (Grupo 18) — Semestre 2026-III*  
**Proyecto 02: Aplicación de Escritorio para Ingeniería Civil**  
**Tema 01 (Estructuras):** *Diagramas de cortante, momento y deflexión en vigas con cargas arbitrarias*

---

## 1. Descripción del Problema de Ingeniería Civil

En el diseño y revisión estructural de obras civiles (puentes, vigas de entrepiso en edificación, cerchas, pasarelas peatonales y vigas carril de puentes grúa), el cálculo preciso de las solicitaciones internas de fuerza cortante $V(x)$, momento flector $M(x)$, pendiente elástica o giro $\theta(x)$ y deflexión o flecha elástica $v(x)$ constituye el fundamento para garantizar la seguridad bajo los **Estados Límites de Resistencia** (capacidad de flexión y cortante) y el confort y serviciabilidad bajo los **Estados Límites de Servicio** (control de fisuración y deformaciones excesivas según la norma colombiana sismorresistente **NSR-10, Títulos B y C**, así como la especificación **AISC 360-16 / LRFD**).

Las herramientas tradicionales simplificadas suelen limitarse a casos canónicos aislados (una sola carga puntual o distribuida uniforme). Sin embargo, en la práctica profesional real, una viga soporta simultáneamente:
1. Su **peso propio volumétrico**, calculado automáticamente a partir de la geometría exacta de la sección transversal ($\gamma \cdot A$).
2. Cargas puntuales concentradas en cualquier abscisa $x \in [0, L]$ (columnas apeadas, maquinaria, crucetas).
3. Múltiples cargas distribuidas uniformes o trapezoidales variables ($w_1 \to w_2$) actuando sobre tramos arbitrarios $[x_1, x_2]$.
4. Momentos flectores concentrados externos $M_0$ (empotramientos elásticos, conexiones a momento con columnas secundarias).
5. Configuraciones geométricas tanto de **viga simplemente apoyada con o sin voladizos en ambos extremos** como de **viga en voladizo (empotramiento perfecto en $x = 0$)**.

**CivilBeam 2026** resuelve de forma analítica y numérica rigurosa este problema estructural, integrando una interfaz gráfica moderna (Flet en Material 3), persistencia relacional en SQLite, cálculo de secciones poligonales mediante el Teorema de Green (`pysections`), generación automática de diagramas técnicos vectorizados (Matplotlib) y exportación de memorias de cálculo formales en Microsoft Word (`docxtpl`).

---

## 2. Fundamento Matemático y Mecánico

### 2.1 Ecuación Diferencial de Euler-Bernoulli
Para vigas prismáticas homogéneas e isotrópicas bajo flexión pura en régimen elástico lineal y pequeñas deformaciones, la relación entre la carga distribuida vertical $q(x)$, la fuerza cortante $V(x)$, el momento flector $M(x)$, la rotación de la sección $\theta(x)$ y la deflexión vertical $v(x)$ se rige por la ecuación diferencial de cuarto orden:

$$E I \frac{d^4 v}{dx^4} = -q(x)$$

Integrando sucesivamente a lo largo de la directriz longitudinal de la viga:

$$\frac{dV(x)}{dx} = -q(x) \quad \implies \quad V(x) = V(0) - \int_{0}^{x} q(\xi) \, d\xi$$

$$\frac{dM(x)}{dx} = V(x) \quad \implies \quad M(x) = M(0) + \int_{0}^{x} V(\xi) \, d\xi$$

$$\frac{d\theta(x)}{dx} = \frac{M(x)}{E I} \quad \implies \quad \theta(x) = \theta(0) + \int_{0}^{x} \frac{M(\xi)}{E I} \, d\xi$$

$$\frac{dv(x)}{dx} = \theta(x) \quad \implies \quad v(x) = v(0) + \int_{0}^{x} \theta(\xi) \, d\xi$$

Donde:
- $E$ es el Módulo de Elasticidad longitudinal del material (concreto o acero estructural) en $\text{Pa}$ o $\text{GPa}$.
- $I$ es el Momento de Inercia baricéntrico respecto al eje neutro de flexión en $\text{m}^4$.
- $E I$ representa la rigidez a la flexión del elemento.

### 2.2 Vectorización Numérica con NumPy y Funciones Singulares
Para evitar bucles iterativos lentos (`for`) en Python, el eje de la viga se discretiza en una malla adaptativa vectorizada $X \in \mathbb{R}^N$ ($N \ge 1000$ puntos) mediante `np.linspace(0, L, N)` enriquecida con puntos de discontinuidad exacta en apoyos y puntos de aplicación de cargas concentradas.

Cada carga se modela mediante álgebra booleana vectorizada (`np.where` y máscaras de NumPy):
- **Carga puntual $P$ en $x_0$:** Aporta a $V(x)$ un salto negativo $-P \cdot [x \ge x_0]$ y a $M(x)$ una contribución $-P \cdot (x - x_0) \cdot [x \ge x_0]$.
- **Carga distribuida trapezoidal $[x_1, x_2]$ con intensidades $w_1, w_2$:**
  $$w(\xi) = w_1 + \frac{w_2 - w_1}{x_2 - x_1} (\xi - x_1)$$
  Aporta a $V(x)$ la integral de área del trapecio comprendido entre $x_1$ y $\min(x, x_2)$, y a $M(x)$ el momento estático correspondiente respecto al punto $x$.
- **Momento concentrado $M_0$ en $x_0$:** Aporta una discontinuidad en escalón $+M_0 \cdot [x \ge x_0]$ en el diagrama de momentos flectores sin alterar el cortante.

### 2.3 Doble Integración Numérica con SciPy (`cumulative_trapezoid`)
La rotación y la flecha elástica se obtienen aplicando la regla trapezoidal acumulativa de SciPy:
```python
from scipy.integrate import cumulative_trapezoid

# 1. Curvatura kappa(x) = M(x) / (E * I)
kappa = M / (E_Pa * I_m4)

# 2. Primera integración -> Giro theta(x) salvo constante C1
theta_indefinida = cumulative_trapezoid(kappa, x, initial=0.0)

# 3. Segunda integración -> Deflexión v(x) salvo constantes C1*x + C2
v_indefinida = cumulative_trapezoid(theta_indefinida, x, initial=0.0)
```

### 2.4 Solución Exacta de Condiciones de Frontera
Las constantes de integración $C_1$ y $C_2$ se resuelven analíticamente:
- **Viga Simplemente Apoyada con apoyos en $x_1$ y $x_2$:**
  $$v(x_1) = 0 \quad \text{y} \quad v(x_2) = 0$$
  $$v_{\text{num}}(x_1) + C_1 x_1 + C_2 = 0$$
  $$v_{\text{num}}(x_2) + C_1 x_2 + C_2 = 0$$
  $$\implies C_1 = -\frac{v_{\text{num}}(x_2) - v_{\text{num}}(x_1)}{x_2 - x_1}, \quad C_2 = -v_{\text{num}}(x_1) - C_1 x_1$$
  $$\theta(x) = \theta_{\text{num}}(x) + C_1, \quad v(x) = v_{\text{num}}(x) + C_1 x + C_2$$

- **Viga en Voladizo (empotramiento en $x = 0$):**
  $$\theta(0) = 0 \implies C_1 = 0$$
  $$v(0) = 0 \implies C_2 = 0$$
  $$\theta(x) = \theta_{\text{num}}(x), \quad v(x) = v_{\text{num}}(x)$$

---

## 3. Integración con el Módulo `pysections` (`sections.py`)

El proyecto reutiliza e integra directamente el módulo `sections.py` ubicado en la carpeta del curso. Dicho módulo calcula las propiedades mecánicas de secciones transversales arbitrarias representadas como polígonos cerrados 2D mediante la aplicación computacional del **Teorema de Green / Fórmula del Agrimensor de Gauss**:

$$\text{Área } A = \frac{1}{2} \sum_{i=0}^{n-1} (x_i y_{i+1} - x_{i+1} y_i)$$

$$\text{Centroide } \bar{x} = \frac{1}{6A} \sum_{i=0}^{n-1} (x_i + x_{i+1})(x_i y_{i+1} - x_{i+1} y_i), \quad \bar{y} = \frac{1}{6A} \sum_{i=0}^{n-1} (y_i + y_{i+1})(x_i y_{i+1} - x_{i+1} y_i)$$

$$I_x = \frac{1}{12} \sum_{i=0}^{n-1} (y_i^2 + y_i y_{i+1} + y_{i+1}^2)(x_i y_{i+1} - x_{i+1} y_i) - A \bar{y}^2$$

### Secciones Disponibles en la Aplicación
1. **Rectangular de Concreto (`crear_seccion_rectangular`):** Adaptador que utiliza la clase `Deck` de `sections.py` para vigas rectangulares estándar de ancho $b$ y altura $h$.
2. **Perfil I de Acero Estructural (`PerfilI`):** Subclase especializada desarrollada en `app/secciones.py` que hereda de `_SinglePolygonSection` en `sections.py`. Genera automáticamente los 12 vértices del polígono baricéntrico del perfil I dado su ancho de patín ($b_f$), peralte total ($d$), espesor de patín ($t_f$) y espesor de alma ($t_w$).
3. **Viga Cajón / Viga Puente Bulb-Tee (`BulbTeeGirderBridge`):** Adaptador directo para vigas preesforzadas de puentes vehiculares provistas por `sections.py`.

---

## 4. Criterios de Verificación Normativa (NSR-10 / AISC)

Para cada cálculo efectuado, el motor evalúa automáticamente dos estados límite:
1. **Esfuerzo Normal Máximo por Flexión ($\sigma_{\text{max}}$):**
   $$\sigma_{\text{max}} = \frac{M_{\text{max}} \cdot c}{I} \le \sigma_{\text{adm}}$$
   Donde $c = \frac{h}{2}$ (distancia a la fibra extrema). Si $\sigma_{\text{max}} \le \sigma_{\text{adm}}$ $\to$ **CUMPLE**.
2. **Deflexión Elástica Máxima ($|v|_{\text{max}}$):**
   $$|v|_{\text{max}} \le \delta_{\text{adm}} = \frac{L}{k}$$
   Valores normativos seleccionables en el menú desplegable:
   - $L / 180$: Elementos que no soportan cielos rasos ni acabados sensibles.
   - $L / 240$: Vigas de piso estándar sometidas a cargas vivas.
   - $L / 360$: Límite estricto NSR-10 (Título B.4) para evitar agrietamiento en mampostería.
   - $L / 480$: Elementos que soportan acabados extremadamente rígidos o frágiles.

---

## 5. Arquitectura del Software

El código sigue una estricta separación de responsabilidades en capas (Clean Architecture / MVC):

```
analisis_vigas/
│
├── main.py                     # Punto de entrada de la aplicación de escritorio Flet
├── requirements.txt            # Dependencias fijadas con versión exacta
├── .gitignore                  # Exclusiones de Git (.venv, pycache, db, reportes)
├── ejecutar.bat                # Lanzador automatizado en 1 clic para Windows
├── README.md                   # Documentación técnica integral
│
├── app/
│   ├── __init__.py
│   ├── sections.py             # Motor geométrico original pysections (Gauss / Green)
│   ├── secciones.py            # Adaptadores y extensión PerfilI (_SinglePolygonSection)
│   ├── modelo.py               # Modelo físico y matemático (NumPy / SciPy cumulative_trapezoid)
│   ├── db.py                   # Persistencia relacional SQLite (2 tablas, FK, CASCADE, CRUD)
│   ├── graficas.py             # Generación de diagramas orientados a objetos (Matplotlib)
│   ├── reporte.py              # Exportación automática de memorias Word (.docx) con docxtpl
│   │
│   └── ui/                     # Capa de Interfaz Gráfica (Flet Material 3)
│       ├── __init__.py
│       ├── calculo_view.py     # Vista de entrada de datos, cálculo y visualización gráfica
│       └── historial_view.py   # Vista de base de datos, búsqueda, comparación y reapertura
│
├── plantillas/
│   └── memoria.docx            # Plantilla Word con estilos institucionales y tags Jinja2
│
├── herramientas/
│   └── crear_plantilla.py      # Generador programático de la plantilla docx
│
├── ejemplos/
│   ├── memoria_ejemplo.docx    # Memoria de cálculo completa de muestra generada
│   └── capturas/
│       └── diagramas_ejemplo.png # Gráfica técnica de alta resolución exportada
│
└── tests/
    ├── __init__.py
    └── test_modelo.py          # Suite de 5 pruebas unitarias con pytest (Beer & Johnston)
```

---

## 6. Base de Datos Relacional SQLite

El módulo `app/db.py` implementa un esquema normalizado con **2 tablas**, clave foránea con integridad referencial y borrado en cascada (`ON DELETE CASCADE`), y todas las sentencias SQL parametrizadas con `?`:

```sql
CREATE TABLE IF NOT EXISTS proyectos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE NOT NULL,
    descripcion TEXT,
    fecha_creacion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calculos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id INTEGER NOT NULL,
    nombre TEXT NOT NULL,
    tipo_viga TEXT NOT NULL,
    longitud REAL NOT NULL,
    datos_entrada TEXT NOT NULL,       -- Configuración en formato JSON
    resumen_resultados TEXT NOT NULL,  -- V_max, M_max, flecha en JSON
    cumple_global INTEGER NOT NULL,
    autor TEXT,
    fecha TEXT NOT NULL,
    FOREIGN KEY (proyecto_id) REFERENCES proyectos(id) ON DELETE CASCADE
);
```

### Funcionalidades CRUD Completas:
1. **Create:** Guarda automáticamente o a petición el proyecto, cálculo, sección y cargas.
2. **Read:** Lista cálculos con búsqueda interactiva por texto en tiempo real.
3. **Reopen:** Al pulsar *"Reabrir"*, los datos JSON de entrada se deserializan y recargan inmediatamente en el formulario de cálculo.
4. **Delete:** Modal de confirmación que elimina el cálculo y sus relaciones en cascada.
5. **Compare:** Selección mediante casillas de verificación de 2 cálculos guardados para generar una gráfica comparativa superpuesta de deflexiones y momentos.

---

## 7. Pruebas Unitarias Automatizadas (`pytest`)

El archivo `tests/test_modelo.py` contiene 5 pruebas de validación rigurosa frente a soluciones exactas de la literatura (*Mecánica de Materiales*, Ferdinand P. Beer & E. Russell Johnston Jr. / R. C. Hibbeler):

| Caso de Prueba | Modelo / Configuración | Parámetros | Solución Analítica Cerrada | Resultado SciPy / NumPy |
| :--- | :--- | :--- | :--- | :--- |
| **Caso 1** | Simplemente apoyada con carga puntual central | $L=6\text{ m}, P=24\text{ kN}, E=200\text{ GPa}$ | $M_{\text{max}} = \frac{PL}{4} = 36\text{ kN}\cdot\text{m}$, $\delta_{\text{max}} = \frac{PL^3}{48EI} = 1.055\text{ mm}$ | **100% Coincidente** ($< 0.5\%$ error) |
| **Caso 2** | Simplemente apoyada con carga uniforme | $L=8\text{ m}, w=15\text{ kN/m}, E=25\text{ GPa}$ | $M_{\text{max}} = \frac{wL^2}{8} = 120\text{ kN}\cdot\text{m}$, $\delta_{\text{max}} = \frac{5wL^4}{384EI} = 3.906\text{ mm}$ | **100% Coincidente** ($< 0.2\%$ error) |
| **Caso 3** | Voladizo con carga puntual en extremo libre | $L=3\text{ m}, P=10\text{ kN}, E=200\text{ GPa}$ | $M_{\text{max}} = PL = 30\text{ kN}\cdot\text{m}$, $\delta_{\text{max}} = \frac{PL^3}{3EI} = 2.457\text{ mm}$ | **100% Coincidente** ($< 0.2\%$ error) |
| **Caso 4** | Geometría y propiedades de Perfil I | $b_f=200, d=400, t_f=20, t_w=10\text{ mm}$ | $A = 2 b_f t_f + (d - 2t_f) t_w$, $I = \frac{1}{12} b_f d^3 - \frac{1}{12} (b_f - t_w)(d - 2t_f)^3$ | **100% Idéntico a pysections** |
| **Caso 5** | Operaciones CRUD en SQLite | Guardado, consulta, filtrado y eliminación con cascada | Base de datos temporal aislada con `tmp_path` | **100% Validado** |

---

## 8. Guía de Instalación y Ejecución

### Opción A: Ejecución en 1 Clic (Recomendada para Windows)
Haga doble clic en el archivo:
```bat
ejecutar.bat
```
El script creará automáticamente el entorno virtual `.venv` si no existe, verificará las dependencias de `requirements.txt` y lanzará la aplicación de escritorio.

### Opción B: Ejecución Manual desde la Terminal (PowerShell / CMD)
1. Navegue al directorio del proyecto:
   ```powershell
   cd "D:\Desktop\TODO\Universidad Distrital\SEMETRE 10 ING\Programación II\analisis_vigas"
   ```
2. Cree y active un entorno virtual de Python:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
3. Instale las dependencias fijadas:
   ```powershell
   pip install -r requirements.txt
   ```
4. Ejecute la aplicación de escritorio:
   ```powershell
   python main.py
   ```
5. Ejecute la suite de pruebas unitarias:
   ```powershell
   pytest tests/test_modelo.py -v
   ```

---

## 9. Referencias Bibliográficas y Normativas
- **Asociación Colombiana de Ingeniería Sísmica (AIS).** *Reglamento Colombiano de Construcción Sismo Resistente (NSR-10)*. Título B (Cargas) y Título C (Concreto Estructural). Bogotá, Colombia.
- **American Institute of Steel Construction (AISC).** *Specification for Structural Steel Buildings (AISC 360-16)*. Chicago, IL, 2016.
- **Beer, F. P., Johnston, E. R., DeWolf, J. T., & Mazurek, D. F.** *Mecánica de Materiales*. 8ª Edición, McGraw-Hill Education, 2020.
- **Hibbeler, R. C.** *Análisis Estructural*. 9ª Edición, Pearson Educación, 2016.
