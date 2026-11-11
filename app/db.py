"""
db.py
Capa de persistencia con SQLite para la aplicación de análisis de vigas.
Universidad Distrital Francisco José de Caldas - Facultad Tecnológica
Programación II

Esquema relacional:
- Tabla 'proyectos': información general y metadatos.
- Tabla 'calculos': resultados y parámetros completos de cada análisis (FK a proyectos).
Consultas 100% parametrizadas (?), prevención de inyecciones y transacciones ACID.
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any

# Ubicación por defecto de la base de datos
RUTA_BASE = Path(__file__).resolve().parent.parent
RUTA_DATOS = RUTA_BASE / "datos"
RUTA_DB = RUTA_DATOS / "vigas.db"


def obtener_conexion(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Retorna una conexión a SQLite con PRAGMA foreign_keys = ON."""
    if db_path is None:
        RUTA_DATOS.mkdir(parents=True, exist_ok=True)
        ruta = str(RUTA_DB)
    else:
        ruta = str(db_path)

    conn = sqlite3.connect(ruta)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def inicializar_bd(db_path: Optional[str] = None):
    """
    Crea las tablas relacionales de la base de datos si no existen.
    Cumple el Requisito no negociable 4 (CREATE TABLE IF NOT EXISTS).
    """
    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()

        # Tabla 1: proyectos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proyectos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                descripcion TEXT,
                autor TEXT DEFAULT 'Ingeniero Calculista',
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Tabla 2: calculos (relacionada con FK a proyectos)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calculos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proyecto_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tipo_viga TEXT NOT NULL,
                longitud REAL NOT NULL,
                datos_entrada_json TEXT NOT NULL,
                resumen_resultados_json TEXT NOT NULL,
                cumple_global INTEGER NOT NULL,
                FOREIGN KEY (proyecto_id) REFERENCES proyectos(id) ON DELETE CASCADE
            );
        """)
        conn.commit()


# =========================================================================
# OPERACIONES CRUD PARA PROYECTOS
# =========================================================================

def crear_o_obtener_proyecto(nombre: str, descripcion: str = "", autor: str = "Ingeniero Calculista", db_path: Optional[str] = None) -> int:
    """Crea un proyecto si no existe, o retorna el ID del existente."""
    nombre = nombre.strip()
    if not nombre:
        nombre = "Proyecto General"

    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM proyectos WHERE nombre = ?", (nombre,))
        fila = cursor.fetchone()
        if fila:
            return fila["id"]

        cursor.execute("""
            INSERT INTO proyectos (nombre, descripcion, autor)
            VALUES (?, ?, ?)
        """, (nombre, descripcion, autor))
        conn.commit()
        return cursor.lastrowid


def listar_proyectos(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista todos los proyectos registrados con el conteo de cálculos asociados."""
    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.nombre, p.descripcion, p.autor, p.fecha_creacion,
                   COUNT(c.id) as total_calculos
            FROM proyectos p
            LEFT JOIN calculos c ON p.id = c.proyecto_id
            GROUP BY p.id
            ORDER BY p.fecha_creacion DESC
        """)
        return [dict(fila) for fila in cursor.fetchall()]


def eliminar_proyecto(proyecto_id: int, db_path: Optional[str] = None) -> bool:
    """Elimina un proyecto y todos sus cálculos en cascada."""
    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM proyectos WHERE id = ?", (proyecto_id,))
        conn.commit()
        return cursor.rowcount > 0


# =========================================================================
# OPERACIONES CRUD PARA CÁLCULOS
# =========================================================================

def guardar_calculo(
    proyecto_nombre: str,
    calculo_nombre: str,
    tipo_viga: str,
    longitud: float,
    datos_entrada: dict,
    resumen_resultados: dict,
    cumple_global: bool,
    descripcion_proyecto: str = "",
    autor: str = "Ingeniero Calculista",
    db_path: Optional[str] = None
) -> int:
    """Guarda un cálculo asociándolo al proyecto especificado."""
    proyecto_id = crear_o_obtener_proyecto(proyecto_nombre, descripcion_proyecto, autor, db_path)

    datos_json = json.dumps(datos_entrada, ensure_ascii=False)
    resumen_json = json.dumps(resumen_resultados, ensure_ascii=False)

    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO calculos (
                proyecto_id, nombre, tipo_viga, longitud,
                datos_entrada_json, resumen_resultados_json, cumple_global
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            proyecto_id,
            calculo_nombre.strip() or "Cálculo sin título",
            tipo_viga,
            float(longitud),
            datos_json,
            resumen_json,
            1 if cumple_global else 0
        ))
        conn.commit()
        return cursor.lastrowid


def listar_calculos(filtro_busqueda: str = "", db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista cálculos guardados con filtro opcional por nombre de proyecto o cálculo."""
    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        if filtro_busqueda.strip():
            patron = f"%{filtro_busqueda.strip()}%"
            cursor.execute("""
                SELECT c.id, c.nombre, c.fecha, c.tipo_viga, c.longitud,
                       c.cumple_global, p.nombre as proyecto_nombre, p.autor,
                       c.resumen_resultados_json
                FROM calculos c
                JOIN proyectos p ON c.proyecto_id = p.id
                WHERE c.nombre LIKE ? OR p.nombre LIKE ?
                ORDER BY c.fecha DESC
            """, (patron, patron))
        else:
            cursor.execute("""
                SELECT c.id, c.nombre, c.fecha, c.tipo_viga, c.longitud,
                       c.cumple_global, p.nombre as proyecto_nombre, p.autor,
                       c.resumen_resultados_json
                FROM calculos c
                JOIN proyectos p ON c.proyecto_id = p.id
                ORDER BY c.fecha DESC
            """)

        filas = []
        for r in cursor.fetchall():
            d = dict(r)
            try:
                d["resumen"] = json.loads(d["resumen_resultados_json"])
            except Exception:
                d["resumen"] = {}
            filas.append(d)
        return filas


def obtener_calculo_por_id(calculo_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Recupera la información completa de un cálculo para reabrirlo o generar reporte."""
    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, p.nombre as proyecto_nombre, p.descripcion as proyecto_desc, p.autor
            FROM calculos c
            JOIN proyectos p ON c.proyecto_id = p.id
            WHERE c.id = ?
        """, (calculo_id,))
        fila = cursor.fetchone()
        if not fila:
            return None

        d = dict(fila)
        d["datos_entrada"] = json.loads(d["datos_entrada_json"])
        d["resumen_resultados"] = json.loads(d["resumen_resultados_json"])
        return d


def eliminar_calculo(calculo_id: int, db_path: Optional[str] = None) -> bool:
    """Elimina un cálculo por su ID."""
    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM calculos WHERE id = ?", (calculo_id,))
        conn.commit()
        return cursor.rowcount > 0
