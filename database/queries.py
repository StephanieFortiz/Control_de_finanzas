"""
queries.py
----------
Todas las funciones que la app usa para leer y escribir datos.
Ningún otro archivo debe tocar la base de datos directamente —
todo pasa por aquí.

Convenciones:
  - Funciones que leen datos:    obtener_*  → retornan lista de dicts
  - Funciones que escriben:      crear_*    → retornan el id del nuevo registro
  - Funciones que modifican:     actualizar_*
  - Funciones que borran:        eliminar_*
  - Funciones de cálculo:        calcular_*
"""

import psycopg2.extras
from datetime import date, datetime
from typing import Optional
from database.schema import get_connection


def _rows(conn, query, params=()):
    """Ejecuta un SELECT y retorna lista de dicts."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]


def _row(conn, query, params=()):
    """Ejecuta un SELECT y retorna un solo dict (o None)."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        r = cur.fetchone()
        return dict(r) if r else None


# ======================================================================
# USUARIOS
# ======================================================================

def obtener_usuarios() -> list[dict]:
    conn = get_connection()
    result = _rows(conn, "SELECT * FROM usuario ORDER BY id")
    conn.close()
    return result


def crear_usuario(nombre: str, color_perfil: str = "#378ADD") -> int:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO usuario (nombre, color_perfil) VALUES (%s, %s) RETURNING id",
            (nombre, color_perfil)
        )
        nuevo_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return nuevo_id


# ======================================================================
# CUENTAS
# ======================================================================

def obtener_cuentas(usuario_id: Optional[int] = None) -> list[dict]:
    conn = get_connection()
    if usuario_id:
        result = _rows(conn,
            "SELECT c.*, u.nombre as usuario_nombre FROM cuenta c "
            "JOIN usuario u ON c.usuario_id = u.id "
            "WHERE c.usuario_id = %s AND c.activa = 1 ORDER BY c.nombre",
            (usuario_id,)
        )
    else:
        result = _rows(conn,
            "SELECT c.*, u.nombre as usuario_nombre FROM cuenta c "
            "JOIN usuario u ON c.usuario_id = u.id "
            "WHERE c.activa = 1 ORDER BY u.nombre, c.nombre"
        )
    conn.close()
    return result


def crear_cuenta(usuario_id: int, nombre: str, tipo: str,
                 saldo_inicial: float = 0.0) -> int:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO cuenta (usuario_id, nombre, tipo, saldo_inicial) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (usuario_id, nombre, tipo, saldo_inicial)
        )
        nuevo_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return nuevo_id


# ======================================================================
# TARJETAS DE CRÉDITO
# ======================================================================

def obtener_tarjetas(usuario_id: Optional[int] = None) -> list[dict]:
    conn = get_connection()
    if usuario_id:
        result = _rows(conn,
            "SELECT t.*, u.nombre as usuario_nombre FROM tarjeta_credito t "
            "JOIN usuario u ON t.usuario_id = u.id "
            "WHERE t.usuario_id = %s AND t.activa = 1 ORDER BY t.nombre",
            (usuario_id,)
        )
    else:
        result = _rows(conn,
            "SELECT t.*, u.nombre as usuario_nombre FROM tarjeta_credito t "
            "JOIN usuario u ON t.usuario_id = u.id "
            "WHERE t.activa = 1 ORDER BY u.nombre, t.nombre"
        )
    conn.close()
    return result


def crear_tarjeta(usuario_id: int, nombre: str, banco: str,
                  dia_corte: int, dia_pago: int, limite: float = 0.0) -> int:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tarjeta_credito (usuario_id, nombre, banco, dia_corte, dia_pago, limite) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (usuario_id, nombre, banco, dia_corte, dia_pago, limite)
        )
        nuevo_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return nuevo_id


# ======================================================================
# CATEGORÍAS
# ======================================================================

def obtener_categorias(tipo: Optional[str] = None, incluir_inactivas: bool = False) -> list[dict]:
    conn = get_connection()
    filtros = []
    params  = []
    if tipo:
        filtros.append("tipo = %s")
        params.append(tipo)
    if not incluir_inactivas:
        filtros.append("activa = 1")

    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    result = _rows(conn,
        f"SELECT * FROM categoria {where} ORDER BY tipo, nombre",
        params
    )
    conn.close()
    return result


def crear_categoria(nombre: str, icono: str, color: str, tipo: str) -> int:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO categoria (nombre, icono, color, tipo) VALUES (%s, %s, %s, %s) RETURNING id",
            (nombre, icono, color, tipo)
        )
        nuevo_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return nuevo_id


def actualizar_categoria(
    categoria_id: int, nombre: str, icono: str, color: str, tipo: str, activa: bool
) -> None:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE categoria SET nombre=%s, icono=%s, color=%s, tipo=%s, activa=%s WHERE id=%s",
            (nombre, icono, color, tipo, 1 if activa else 0, categoria_id)
        )
    conn.commit()
    conn.close()


# ======================================================================
# TRANSACCIONES
# ======================================================================

def crear_transaccion(
    usuario_id: int,
    monto: float,
    fecha: str,
    tipo: str,
    descripcion: str = "",
    cuenta_id: Optional[int] = None,
    tarjeta_id: Optional[int] = None,
    categoria_id: Optional[int] = None,
    notas: str = "",
    meses_sin_intereses: int = 0,
) -> int:
    if cuenta_id is None and tarjeta_id is None:
        raise ValueError("Debes especificar cuenta_id o tarjeta_id.")
    if cuenta_id is not None and tarjeta_id is not None:
        raise ValueError("Una transacción no puede tener cuenta y tarjeta al mismo tiempo.")

    monto_por_mes = round(monto / meses_sin_intereses, 2) if meses_sin_intereses > 0 else 0.0

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO transaccion
               (usuario_id, cuenta_id, tarjeta_id, categoria_id,
                monto, fecha, descripcion, tipo,
                notas, meses_sin_intereses, monto_por_mes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (usuario_id, cuenta_id, tarjeta_id, categoria_id,
             monto, fecha, descripcion, tipo,
             notas, meses_sin_intereses, monto_por_mes)
        )
        nuevo_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return nuevo_id


def obtener_transacciones(
    usuario_id: Optional[int] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    tipo: Optional[str] = None,
    cuenta_id: Optional[int] = None,
    tarjeta_id: Optional[int] = None,
) -> list[dict]:
    query = """
        SELECT
            t.*,
            u.nombre          AS usuario_nombre,
            c.nombre          AS cuenta_nombre,
            tc.nombre         AS tarjeta_nombre,
            tc.banco          AS tarjeta_banco,
            cat.nombre        AS categoria_nombre,
            cat.icono         AS categoria_icono,
            cat.color         AS categoria_color,
            p.id              AS prestamo_id,
            p.monto_pendiente AS prestamo_pendiente,
            p.monto_original  AS prestamo_monto_original,
            p.estado          AS prestamo_estado,
            ua.nombre         AS prestamo_acreedor,
            ud.nombre         AS prestamo_deudor,
            p.nombre_externo  AS prestamo_externo
        FROM transaccion t
        JOIN usuario u              ON t.usuario_id   = u.id
        LEFT JOIN cuenta c          ON t.cuenta_id    = c.id
        LEFT JOIN tarjeta_credito tc ON t.tarjeta_id  = tc.id
        LEFT JOIN categoria cat     ON t.categoria_id = cat.id
        LEFT JOIN prestamo p        ON p.transaccion_id = t.id
        LEFT JOIN usuario ua        ON p.acreedor_id  = ua.id
        LEFT JOIN usuario ud        ON p.deudor_id    = ud.id
        WHERE 1=1
    """
    params = []

    if usuario_id:
        query += " AND t.usuario_id = %s"
        params.append(usuario_id)
    if desde:
        query += " AND t.fecha >= %s"
        params.append(desde)
    if hasta:
        query += " AND t.fecha <= %s"
        params.append(hasta)
    if tipo:
        query += " AND t.tipo = %s"
        params.append(tipo)
    if cuenta_id:
        query += " AND t.cuenta_id = %s"
        params.append(cuenta_id)
    if tarjeta_id:
        query += " AND t.tarjeta_id = %s"
        params.append(tarjeta_id)
    query += " ORDER BY t.fecha DESC, t.id DESC"

    conn = get_connection()
    result = _rows(conn, query, params)
    conn.close()
    return result


def obtener_transaccion(transaccion_id: int) -> Optional[dict]:
    conn = get_connection()
    result = _row(conn,
        """SELECT t.*,
               c.nombre  AS cuenta_nombre,
               tc.nombre AS tarjeta_nombre
           FROM transaccion t
           LEFT JOIN cuenta c          ON t.cuenta_id  = c.id
           LEFT JOIN tarjeta_credito tc ON t.tarjeta_id = tc.id
           WHERE t.id = %s""",
        (transaccion_id,)
    )
    conn.close()
    return result


def actualizar_transaccion(
    transaccion_id: int,
    descripcion: str,
    monto: float,
    fecha: str,
    tipo: str,
    categoria_id: Optional[int],
    cuenta_id: Optional[int],
    tarjeta_id: Optional[int],
    notas: str,
    meses_sin_intereses: int,
) -> None:
    if cuenta_id is None and tarjeta_id is None:
        raise ValueError("Debes especificar cuenta_id o tarjeta_id.")
    if cuenta_id is not None and tarjeta_id is not None:
        raise ValueError("Una transacción no puede tener cuenta y tarjeta al mismo tiempo.")

    monto_por_mes = round(monto / meses_sin_intereses, 2) if meses_sin_intereses > 0 else 0.0

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE transaccion SET
                descripcion         = %s,
                monto               = %s,
                fecha               = %s,
                tipo                = %s,
                categoria_id        = %s,
                cuenta_id           = %s,
                tarjeta_id          = %s,
                notas               = %s,
                meses_sin_intereses = %s,
                monto_por_mes       = %s
               WHERE id = %s""",
            (descripcion, monto, fecha, tipo, categoria_id,
             cuenta_id, tarjeta_id,
             notas, meses_sin_intereses, monto_por_mes,
             transaccion_id)
        )
    conn.commit()
    conn.close()


def eliminar_transaccion(transaccion_id: int):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM transaccion WHERE id = %s", (transaccion_id,))
    conn.commit()
    conn.close()


# ======================================================================
# PRÉSTAMOS
# ======================================================================

def crear_prestamo(
    monto: float,
    fecha: str,
    acreedor_id: Optional[int] = None,
    deudor_id: Optional[int] = None,
    nombre_externo: Optional[str] = None,
    notas: str = "",
    transaccion_id: Optional[int] = None,
    fecha_estimada_pago: Optional[str] = None,
) -> int:
    if acreedor_id is None and nombre_externo is None:
        raise ValueError("Debe haber un acreedor (usuario o nombre externo).")

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO prestamo
               (acreedor_id, deudor_id, nombre_externo,
                monto_original, monto_pendiente, fecha, notas,
                transaccion_id, fecha_estimada_pago)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (acreedor_id, deudor_id, nombre_externo,
             monto, monto,
             fecha, notas, transaccion_id, fecha_estimada_pago)
        )
        nuevo_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return nuevo_id


def obtener_prestamos(
    usuario_id: Optional[int] = None,
    estado: Optional[str] = None
) -> list[dict]:
    query = """
        SELECT
            p.*,
            ua.nombre  AS acreedor_nombre,
            ud.nombre  AS deudor_nombre,
            t.descripcion AS transaccion_descripcion,
            t.monto       AS transaccion_monto,
            t.fecha       AS transaccion_fecha
        FROM prestamo p
        LEFT JOIN usuario ua   ON p.acreedor_id    = ua.id
        LEFT JOIN usuario ud   ON p.deudor_id      = ud.id
        LEFT JOIN transaccion t ON p.transaccion_id = t.id
        WHERE 1=1
    """
    params = []

    if usuario_id:
        query += " AND (p.acreedor_id = %s OR p.deudor_id = %s)"
        params.extend([usuario_id, usuario_id])
    if estado:
        query += " AND p.estado = %s"
        params.append(estado)

    query += " ORDER BY p.fecha DESC"

    conn = get_connection()
    result = _rows(conn, query, params)
    conn.close()
    return result


def registrar_pago_prestamo(prestamo_id: int, monto: float,
                             fecha: str, notas: str = "") -> int:
    conn = get_connection()
    prestamo = _row(conn,
        "SELECT monto_pendiente FROM prestamo WHERE id = %s", (prestamo_id,)
    )

    if not prestamo:
        conn.close()
        raise ValueError(f"No existe el préstamo con id={prestamo_id}.")

    nuevo_pendiente = round(prestamo["monto_pendiente"] - monto, 2)
    nuevo_estado = "pagado" if nuevo_pendiente <= 0 else "pendiente"

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE prestamo SET monto_pendiente = %s, estado = %s WHERE id = %s",
            (max(nuevo_pendiente, 0), nuevo_estado, prestamo_id)
        )
        cur.execute(
            "INSERT INTO pago_prestamo (prestamo_id, monto, fecha, notas) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (prestamo_id, monto, fecha, notas)
        )
        nuevo_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return nuevo_id


def eliminar_prestamo(prestamo_id: int):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM pago_prestamo WHERE prestamo_id = %s", (prestamo_id,))
        cur.execute("DELETE FROM prestamo WHERE id = %s", (prestamo_id,))
    conn.commit()
    conn.close()


def obtener_transacciones_para_prestamo(
    usuario_id: Optional[int] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
) -> list[dict]:
    """
    Retorna gastos (tipo=gasto) que aún no tienen un préstamo ligado,
    para mostrarlos en el selector de "crear préstamo desde gasto".
    """
    query = """
        SELECT
            t.*,
            u.nombre       AS usuario_nombre,
            cat.nombre     AS categoria_nombre,
            cat.icono      AS categoria_icono,
            c.nombre       AS cuenta_nombre,
            tc.nombre      AS tarjeta_nombre,
            tc.banco       AS tarjeta_banco
        FROM transaccion t
        JOIN usuario u          ON t.usuario_id   = u.id
        LEFT JOIN categoria cat ON t.categoria_id = cat.id
        LEFT JOIN cuenta c      ON t.cuenta_id    = c.id
        LEFT JOIN tarjeta_credito tc ON t.tarjeta_id = tc.id
        WHERE t.tipo = 'gasto'
          AND NOT EXISTS (
              SELECT 1 FROM prestamo p WHERE p.transaccion_id = t.id
          )
    """
    params = []
    if usuario_id:
        query += " AND t.usuario_id = %s"
        params.append(usuario_id)
    if desde:
        query += " AND t.fecha >= %s"
        params.append(desde)
    if hasta:
        query += " AND t.fecha <= %s"
        params.append(hasta)
    query += " ORDER BY t.fecha DESC, t.id DESC"

    conn = get_connection()
    result = _rows(conn, query, params)
    conn.close()
    return result


def obtener_prestamos_de_transaccion(transaccion_id: int) -> list[dict]:
    """Retorna todos los préstamos vinculados a una transacción específica."""
    conn = get_connection()
    result = _rows(conn,
        """SELECT p.*,
               ua.nombre AS acreedor_nombre,
               ud.nombre AS deudor_nombre
           FROM prestamo p
           LEFT JOIN usuario ua ON p.acreedor_id = ua.id
           LEFT JOIN usuario ud ON p.deudor_id   = ud.id
           WHERE p.transaccion_id = %s
           ORDER BY p.id""",
        (transaccion_id,)
    )
    conn.close()
    return result


# ======================================================================
# LIQUIDACIONES (cierre de cuentas entre pareja)
# ======================================================================

def calcular_balance_pareja(periodo: str) -> dict:
    """
    Calcula el balance entre los dos usuarios basado en préstamos
    pendientes entre ellos.

    Retorna un dict con:
      - usuario_1, usuario_2: los dos usuarios
      - debe_u1: monto que u1 le debe a u2
      - debe_u2: monto que u2 le debe a u1
      - balance: neto (positivo = u1 le debe a u2)
      - prestamos: lista de préstamos entre usuarios con detalle
    """
    usuarios = obtener_usuarios()
    if len(usuarios) < 2:
        return {"error": "Se necesitan al menos 2 usuarios para calcular el balance."}

    u1, u2 = usuarios[0], usuarios[1]

    conn = get_connection()
    prestamos = _rows(conn,
        """SELECT p.*, t.descripcion AS tx_descripcion, t.monto AS tx_monto,
                      t.fecha AS tx_fecha
           FROM prestamo p
           LEFT JOIN transaccion t ON p.transaccion_id = t.id
           WHERE p.estado = 'pendiente'
             AND (
                 (p.acreedor_id = %s AND p.deudor_id = %s)
              OR (p.acreedor_id = %s AND p.deudor_id = %s)
             )
           ORDER BY p.fecha DESC""",
        (u1["id"], u2["id"], u2["id"], u1["id"])
    )
    conn.close()

    debe_u1 = sum(p["monto_pendiente"] for p in prestamos
                  if p["acreedor_id"] == u2["id"] and p["deudor_id"] == u1["id"])
    debe_u2 = sum(p["monto_pendiente"] for p in prestamos
                  if p["acreedor_id"] == u1["id"] and p["deudor_id"] == u2["id"])

    balance = round(debe_u1 - debe_u2, 2)

    if balance > 0:
        desc = f"{u1['nombre']} le debe ${abs(balance):.2f} a {u2['nombre']}"
    elif balance < 0:
        desc = f"{u2['nombre']} le debe ${abs(balance):.2f} a {u1['nombre']}"
    else:
        desc = "Están a mano — no se deben nada."

    return {
        "usuario_1":   u1,
        "usuario_2":   u2,
        "debe_u1":     round(debe_u1, 2),
        "debe_u2":     round(debe_u2, 2),
        "balance":     balance,
        "descripcion": desc,
        "prestamos":   prestamos,
    }


def registrar_liquidacion(usuario_origen_id: int, usuario_destino_id: int,
                           monto: float, fecha: str, periodo: str,
                           notas: str = "") -> int:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO liquidacion
               (usuario_origen_id, usuario_destino_id, monto, fecha, periodo, notas)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (usuario_origen_id, usuario_destino_id, monto, fecha, periodo, notas)
        )
        nuevo_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return nuevo_id


def obtener_liquidaciones() -> list[dict]:
    conn = get_connection()
    result = _rows(conn,
        """SELECT l.*, uo.nombre AS origen_nombre, ud.nombre AS destino_nombre
           FROM liquidacion l
           JOIN usuario uo ON l.usuario_origen_id  = uo.id
           JOIN usuario ud ON l.usuario_destino_id = ud.id
           ORDER BY l.periodo DESC, l.fecha DESC"""
    )
    conn.close()
    return result


# ======================================================================
# CUENTAS Y TARJETAS — actualizaciones y vistas completas
# ======================================================================

def actualizar_cuenta(
    cuenta_id: int, nombre: str, tipo: str, saldo_inicial: float, activa: bool
) -> None:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE cuenta SET nombre=%s, tipo=%s, saldo_inicial=%s, activa=%s WHERE id=%s",
            (nombre, tipo, saldo_inicial, 1 if activa else 0, cuenta_id)
        )
    conn.commit()
    conn.close()


def obtener_cuentas_todas(usuario_id: Optional[int] = None) -> list[dict]:
    """Como obtener_cuentas pero incluye las inactivas (para gestión)."""
    conn = get_connection()
    if usuario_id:
        result = _rows(conn,
            "SELECT c.*, u.nombre as usuario_nombre FROM cuenta c "
            "JOIN usuario u ON c.usuario_id = u.id "
            "WHERE c.usuario_id = %s ORDER BY c.activa DESC, c.nombre",
            (usuario_id,)
        )
    else:
        result = _rows(conn,
            "SELECT c.*, u.nombre as usuario_nombre FROM cuenta c "
            "JOIN usuario u ON c.usuario_id = u.id "
            "ORDER BY c.activa DESC, u.nombre, c.nombre"
        )
    conn.close()
    return result


def actualizar_tarjeta(
    tarjeta_id: int, nombre: str, banco: str,
    dia_corte: int, dia_pago: int, limite: float, activa: bool
) -> None:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE tarjeta_credito
               SET nombre=%s, banco=%s, dia_corte=%s, dia_pago=%s, limite=%s, activa=%s
               WHERE id=%s""",
            (nombre, banco, dia_corte, dia_pago, limite, 1 if activa else 0, tarjeta_id)
        )
    conn.commit()
    conn.close()


def obtener_tarjetas_todas(usuario_id: Optional[int] = None) -> list[dict]:
    """Como obtener_tarjetas pero incluye las inactivas (para gestión)."""
    conn = get_connection()
    if usuario_id:
        result = _rows(conn,
            "SELECT t.*, u.nombre as usuario_nombre FROM tarjeta_credito t "
            "JOIN usuario u ON t.usuario_id = u.id "
            "WHERE t.usuario_id = %s ORDER BY t.activa DESC, t.nombre",
            (usuario_id,)
        )
    else:
        result = _rows(conn,
            "SELECT t.*, u.nombre as usuario_nombre FROM tarjeta_credito t "
            "JOIN usuario u ON t.usuario_id = u.id "
            "ORDER BY t.activa DESC, u.nombre, t.nombre"
        )
    conn.close()
    return result


# ======================================================================
# APOYOS EN GASTOS → PRÉSTAMOS AUTOMÁTICOS
# ======================================================================

def crear_prestamos_desde_apoyos(
    transaccion_id: int,
    usuario_deudor_id: int,
    fecha: str,
    descripcion_gasto: str,
    apoyos: list[dict],
) -> list[int]:
    """
    Crea un préstamo automático por cada apoyo registrado en un gasto.

    Cada elemento de `apoyos` es un dict con:
      - monto:           float  — cuánto aporta esa persona
      - tipo:            str    — "usuario" | "externo"
      - usuario_id:      int    — si tipo == "usuario"
      - nombre_externo:  str    — si tipo == "externo"
    """
    ids_creados = []
    for apoyo in apoyos:
        if apoyo["monto"] <= 0:
            continue
        notas_prestamo = f"Apoyo en: {descripcion_gasto}"

        if apoyo["tipo"] == "usuario":
            pid = crear_prestamo(
                monto=apoyo["monto"],
                fecha=fecha,
                acreedor_id=apoyo["usuario_id"],
                deudor_id=usuario_deudor_id,
                notas=notas_prestamo,
                transaccion_id=transaccion_id,
            )
        else:
            pid = crear_prestamo(
                monto=apoyo["monto"],
                fecha=fecha,
                acreedor_id=None,
                deudor_id=usuario_deudor_id,
                nombre_externo=apoyo["nombre_externo"],
                notas=notas_prestamo,
                transaccion_id=transaccion_id,
            )
        ids_creados.append(pid)
    return ids_creados
