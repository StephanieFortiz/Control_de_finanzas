"""
schema.py
---------
Crea y/o verifica todas las tablas de la base de datos PostgreSQL (Supabase).
Se ejecuta una sola vez al iniciar la app.
Si las tablas ya existen, no borra nada — solo agrega lo que falte.
"""

import os
import psycopg2
import psycopg2.extras
import streamlit as st


def get_connection() -> psycopg2.extensions.connection:
    """
    Retorna una conexión a PostgreSQL usando parámetros individuales de st.secrets.
    Usar parámetros separados evita problemas de codificación en contraseñas con
    caracteres especiales (&, !, *, @, etc.).
    """
    try:
        db = st.secrets["database"]
        return psycopg2.connect(
            host=db["host"],
            port=int(db["port"]),
            dbname=db["dbname"],
            user=db["user"],
            password=db["password"],
        )
    except Exception:
        return psycopg2.connect(os.environ.get("DATABASE_URL", ""))


def crear_tablas():
    """
    Crea todas las tablas si no existen.
    Seguro de ejecutar múltiples veces (IF NOT EXISTS).
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuario (
            id            SERIAL PRIMARY KEY,
            nombre        TEXT   NOT NULL,
            color_perfil  TEXT   NOT NULL DEFAULT '#378ADD'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cuenta (
            id             SERIAL PRIMARY KEY,
            usuario_id     INTEGER NOT NULL REFERENCES usuario(id),
            nombre         TEXT    NOT NULL,
            tipo           TEXT    NOT NULL DEFAULT 'debito',
            saldo_inicial  REAL    NOT NULL DEFAULT 0.0,
            activa         INTEGER NOT NULL DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tarjeta_credito (
            id          SERIAL PRIMARY KEY,
            usuario_id  INTEGER NOT NULL REFERENCES usuario(id),
            nombre      TEXT    NOT NULL,
            banco       TEXT    NOT NULL,
            dia_corte   INTEGER NOT NULL,
            dia_pago    INTEGER NOT NULL,
            limite      REAL    NOT NULL DEFAULT 0.0,
            activa      INTEGER NOT NULL DEFAULT 1
        )
    """)

    # activa incluida desde el inicio — no hace falta migración posterior
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categoria (
            id      SERIAL PRIMARY KEY,
            nombre  TEXT    NOT NULL UNIQUE,
            icono   TEXT    NOT NULL DEFAULT '📦',
            color   TEXT    NOT NULL DEFAULT '#888780',
            tipo    TEXT    NOT NULL DEFAULT 'gasto',
            activa  INTEGER NOT NULL DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transaccion (
            id                   SERIAL PRIMARY KEY,
            usuario_id           INTEGER NOT NULL REFERENCES usuario(id),
            cuenta_id            INTEGER          REFERENCES cuenta(id),
            tarjeta_id           INTEGER          REFERENCES tarjeta_credito(id),
            categoria_id         INTEGER          REFERENCES categoria(id),
            monto                REAL    NOT NULL,
            fecha                TEXT    NOT NULL,
            descripcion          TEXT    NOT NULL DEFAULT '',
            tipo                 TEXT    NOT NULL DEFAULT 'gasto',
            notas                TEXT    NOT NULL DEFAULT '',
            meses_sin_intereses  INTEGER NOT NULL DEFAULT 0,
            monto_por_mes        REAL    NOT NULL DEFAULT 0.0,
            creado_en            TEXT    NOT NULL DEFAULT NOW()::text
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS prestamo (
            id                   SERIAL PRIMARY KEY,
            acreedor_id          INTEGER REFERENCES usuario(id),
            deudor_id            INTEGER REFERENCES usuario(id),
            nombre_externo       TEXT,
            monto_original       REAL NOT NULL,
            monto_pendiente      REAL NOT NULL,
            fecha                TEXT NOT NULL,
            estado               TEXT NOT NULL DEFAULT 'pendiente',
            notas                TEXT NOT NULL DEFAULT '',
            transaccion_id       INTEGER REFERENCES transaccion(id),
            fecha_estimada_pago  TEXT,
            creado_en            TEXT NOT NULL DEFAULT NOW()::text
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pago_prestamo (
            id          SERIAL PRIMARY KEY,
            prestamo_id INTEGER NOT NULL REFERENCES prestamo(id),
            monto       REAL    NOT NULL,
            fecha       TEXT    NOT NULL,
            notas       TEXT    NOT NULL DEFAULT '',
            creado_en   TEXT    NOT NULL DEFAULT NOW()::text
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS liquidacion (
            id                  SERIAL PRIMARY KEY,
            usuario_origen_id   INTEGER NOT NULL REFERENCES usuario(id),
            usuario_destino_id  INTEGER NOT NULL REFERENCES usuario(id),
            monto               REAL    NOT NULL,
            fecha               TEXT    NOT NULL,
            periodo             TEXT    NOT NULL,
            notas               TEXT    NOT NULL DEFAULT '',
            creado_en           TEXT    NOT NULL DEFAULT NOW()::text
        )
    """)

    # Categorías predefinidas — solo si la tabla está vacía
    cur.execute("SELECT COUNT(*) FROM categoria")
    if cur.fetchone()[0] == 0:
        categorias_default = [
            ("Comida y restaurantes", "🍽️", "#D85A30", "gasto"),
            ("Citas",                 "❤️", "#921E1E", "gasto"),
            ("Auto",                  "🚗", "#378ADD", "gasto"),
            ("Salud",                 "💊", "#E24B4A", "gasto"),
            ("Entretenimiento",       "🎬", "#EF9F27", "gasto"),
            ("Ropa y calzado",        "👕", "#D4537E", "gasto"),
            ("Educación",             "📚", "#534AB7", "gasto"),
            ("Viajes",                "✈️", "#0F6E56", "gasto"),
            ("Celular",               "📱", "#D3F512", "gasto"),
            ("Regalos",               "🎁", "#BEF99E", "gasto"),
            ("Suscripciones",         "🏷️", "#FEA8F1", "gasto"),
            ("Personal",              "👩", "#613873", "gasto"),
            ("Oficina",               "💼", "#423939", "gasto"),
            ("Otros gastos",          "📦", "#888780", "gasto"),
            ("Sueldo",                "💰", "#27500A", "ingreso"),
            ("Otros ingresos",        "📈", "#085041", "ingreso"),
        ]
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO categoria (nombre, icono, color, tipo) VALUES %s",
            categorias_default
        )

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Base de datos lista.")


def migrar_bd():
    """
    Aplica migraciones seguras a una BD existente.
    Agrega columnas nuevas si no existen — nunca borra datos.
    Se ejecuta automáticamente al iniciar la app.
    """
    conn = get_connection()
    cur = conn.cursor()

    migraciones = [
        ("transaccion", "notas",                "TEXT NOT NULL DEFAULT ''"),
        ("transaccion", "meses_sin_intereses",  "INTEGER NOT NULL DEFAULT 0"),
        ("transaccion", "monto_por_mes",        "REAL NOT NULL DEFAULT 0.0"),
        ("prestamo",    "transaccion_id",       "INTEGER REFERENCES transaccion(id)"),
        ("prestamo",    "fecha_estimada_pago",  "TEXT"),
        ("categoria",   "activa",               "INTEGER NOT NULL DEFAULT 1"),
    ]

    for tabla, columna, definicion in migraciones:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
        """, (tabla, columna))
        if cur.fetchone() is None:
            cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")
            print(f"  Migración: {tabla}.{columna} agregada.")

    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    crear_tablas()
