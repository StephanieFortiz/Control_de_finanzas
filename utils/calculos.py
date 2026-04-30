"""
utils/calculos.py
-----------------
Lógica financiera pura — sin Streamlit, sin BD.
Todas las funciones reciben datos y retornan datos.

Regla de corte implementada:
  Si fecha_gasto <= dia_corte  → entra al estado de cuenta del mes actual
  Si fecha_gasto >  dia_corte  → entra al estado de cuenta del mes siguiente

MSI (meses sin intereses):
  Un cargo a 3 MSI en enero genera una mensualidad en enero, febrero y marzo.
  La función proyectar_msi_en_periodo detecta automáticamente cuáles
  mensualidades caen en el período consultado, aunque el cargo original
  haya sido en un mes anterior.
"""

from datetime import date, timedelta
import calendar

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def _label_periodo(fecha: date) -> str:
    return f"{MESES_ES[fecha.month]} {fecha.year}"


# ======================================================================
# PERÍODOS DE ESTADO DE CUENTA
# ======================================================================

def calcular_periodo_corte(fecha_gasto: date, dia_corte: int) -> dict:
    """
    Dado un gasto y el día de corte de una tarjeta, retorna:
      - fecha_corte:  fecha exacta de cierre del estado de cuenta
      - fecha_inicio: primer día del período (día siguiente al corte anterior)
      - periodo_label: etiqueta legible en español, ej. "Abril 2025"
    """
    anio, mes = fecha_gasto.year, fecha_gasto.month
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    dia_corte_real = min(dia_corte, ultimo_dia)

    if fecha_gasto.day <= dia_corte_real:
        fecha_corte = date(anio, mes, dia_corte_real)
    else:
        if mes == 12:
            anio_sig, mes_sig = anio + 1, 1
        else:
            anio_sig, mes_sig = anio, mes + 1
        ultimo_dia_sig = calendar.monthrange(anio_sig, mes_sig)[1]
        fecha_corte = date(anio_sig, mes_sig, min(dia_corte, ultimo_dia_sig))

    if fecha_corte.month > 1:
        anio_ant, mes_ant = fecha_corte.year, fecha_corte.month - 1
    else:
        anio_ant, mes_ant = fecha_corte.year - 1, 12
    ultimo_ant = calendar.monthrange(anio_ant, mes_ant)[1]
    dia_inicio = min(dia_corte, ultimo_ant)
    fecha_inicio = date(anio_ant, mes_ant, dia_inicio) + timedelta(days=1)

    return {
        "fecha_corte":   fecha_corte,
        "fecha_inicio":  fecha_inicio,
        "periodo_label": _label_periodo(fecha_corte),
    }


def calcular_fecha_pago(fecha_corte: date, dia_pago: int) -> date:
    """Retorna la fecha límite de pago.
    Si dia_pago > dia del corte → pago en el mismo mes del corte.
    Si dia_pago <= dia del corte → pago en el mes siguiente.
    """
    if dia_pago > fecha_corte.day:
        ultimo_dia = calendar.monthrange(fecha_corte.year, fecha_corte.month)[1]
        return date(fecha_corte.year, fecha_corte.month, min(dia_pago, ultimo_dia))
    if fecha_corte.month == 12:
        anio_pago, mes_pago = fecha_corte.year + 1, 1
    else:
        anio_pago, mes_pago = fecha_corte.year, fecha_corte.month + 1
    ultimo_dia = calendar.monthrange(anio_pago, mes_pago)[1]
    return date(anio_pago, mes_pago, min(dia_pago, ultimo_dia))


def dias_para_pago(fecha_pago: date, hoy: date = None) -> int:
    hoy = hoy or date.today()
    return (fecha_pago - hoy).days


def dias_para_corte(fecha_corte: date, hoy: date = None) -> int:
    hoy = hoy or date.today()
    return (fecha_corte - hoy).days


# ======================================================================
# PROYECCIÓN DE MSI EN PERÍODOS FUTUROS
# ======================================================================

def _fecha_corte_n(periodo_inicial_corte: date, n: int, dia_corte: int) -> date:
    """Calcula la fecha de corte del período N (0-based) a partir del período inicial."""
    mes_n = periodo_inicial_corte.month + n
    anio_n = periodo_inicial_corte.year + (mes_n - 1) // 12
    mes_n = ((mes_n - 1) % 12) + 1
    ultimo = calendar.monthrange(anio_n, mes_n)[1]
    return date(anio_n, mes_n, min(dia_corte, ultimo))


def proyectar_msi_en_periodo(
    transacciones_msi: list[dict],
    dia_corte: int,
    fecha_corte_objetivo: date,
) -> list[dict]:
    """
    Dado un conjunto de transacciones con MSI y una fecha de corte objetivo,
    retorna las mensualidades que caen en ese período.

    Incluye tanto la mensualidad original (mensualidad 1) como las proyectadas
    (mensualidades 2, 3, ... N). El campo 'es_proyeccion' distingue entre ambas.

    Ejemplo con corte día 5:
      Cargo 3000 a 3 MSI el 15-ene → período inicial: Febrero (corte 5-feb)
        Mensualidad 1 → 5-feb  → 1000 (es_proyeccion=False)
        Mensualidad 2 → 5-mar  → 1000 (es_proyeccion=True)
        Mensualidad 3 → 5-abr  → 1000 (es_proyeccion=True)
    """
    proyecciones = []

    for t in transacciones_msi:
        meses = t.get("meses_sin_intereses", 0)
        if meses <= 0:
            continue

        fecha_original = date.fromisoformat(t["fecha"])
        monto_mensual = t.get("monto_por_mes", round(t["monto"] / meses, 2))
        periodo_inicial = calcular_periodo_corte(fecha_original, dia_corte)

        for n in range(meses):
            fc_n = _fecha_corte_n(periodo_inicial["fecha_corte"], n, dia_corte)
            if fc_n == fecha_corte_objetivo:
                proyecciones.append({
                    **t,
                    "monto":                monto_mensual,
                    "monto_por_mes":        monto_mensual,
                    "es_proyeccion":        n > 0,
                    "mensualidad_num":      n + 1,
                    "fecha_cargo_original": t["fecha"],
                    "descripcion": (
                        t["descripcion"] if n == 0
                        else f"{t['descripcion']} ({n+1}/{meses})"
                    ),
                })
                break

    return proyecciones


# ======================================================================
# ESTADO ACTUAL DE UNA TARJETA
# ======================================================================

def estado_tarjeta(tarjeta: dict, transacciones: list[dict],
                   hoy: date = None,
                   fecha_corte_objetivo: date = None) -> dict:
    """
    Calcula el estado completo de una tarjeta para un período específico.

    fecha_corte_objetivo: cuando se provee, fuerza el período al estado de cuenta
      cuyo corte es esa fecha (útil para ver meses anteriores o el mes actual sin
      que el día de hoy desplace el período al siguiente).
      Los días para pago/corte siempre se calculan desde hoy real.
    """
    hoy = hoy or date.today()
    dia_corte = tarjeta["dia_corte"]
    dia_pago  = tarjeta["dia_pago"]
    limite    = tarjeta.get("limite", 0) or 0

    if fecha_corte_objetivo is not None:
        if fecha_corte_objetivo.month > 1:
            a_ant, m_ant = fecha_corte_objetivo.year, fecha_corte_objetivo.month - 1
        else:
            a_ant, m_ant = fecha_corte_objetivo.year - 1, 12
        u_ant = calendar.monthrange(a_ant, m_ant)[1]
        fecha_inicio = date(a_ant, m_ant, min(dia_corte, u_ant)) + timedelta(days=1)
        periodo = {
            "fecha_corte":   fecha_corte_objetivo,
            "fecha_inicio":  fecha_inicio,
            "periodo_label": _label_periodo(fecha_corte_objetivo),
        }
    else:
        periodo = calcular_periodo_corte(hoy, dia_corte)

    fecha_pago = calcular_fecha_pago(periodo["fecha_corte"], dia_pago)

    # Transacciones sin MSI que caen directamente en este período
    txs_directas = [
        t for t in transacciones
        if periodo["fecha_inicio"] <= date.fromisoformat(t["fecha"]) <= periodo["fecha_corte"]
        and t.get("meses_sin_intereses", 0) == 0
    ]

    # Todas las transacciones MSI (de cualquier período) que generan
    # una mensualidad en este período
    todos_msi = [t for t in transacciones if t.get("meses_sin_intereses", 0) > 0]
    mensualidades_periodo = proyectar_msi_en_periodo(
        todos_msi, dia_corte, periodo["fecha_corte"]
    )

    txs_periodo = txs_directas + mensualidades_periodo

    # Calcular total
    total = 0.0
    for t in txs_directas:
        if t["tipo"] == "gasto":
            total += t["monto"]
    for m in mensualidades_periodo:
        if m["tipo"] == "gasto":
            total += m["monto"]
    total = round(total, 2)

    d_corte = dias_para_corte(periodo["fecha_corte"], hoy)
    d_pago  = dias_para_pago(fecha_pago, hoy)
    alerta  = (
        "urgente" if d_pago <= 3
        else "proximo" if d_pago <= 7
        else "ok"
    )
    porcentaje_limite = round((total / limite * 100), 1) if limite > 0 else 0.0

    # Separar proyecciones (mensualidades 2+) para que la vista las pueda marcar
    proyecciones = [m for m in mensualidades_periodo if m.get("es_proyeccion", False)]

    return {
        "periodo_actual":    periodo,
        "fecha_pago":        fecha_pago,
        "dias_para_corte":   d_corte,
        "dias_para_pago":    d_pago,
        "total_periodo":     total,
        "transacciones":     txs_periodo,
        "proyecciones":      proyecciones,
        "alerta":            alerta,
        "porcentaje_limite": porcentaje_limite,
        "limite":            limite,
    }


# ======================================================================
# AGRUPAR POR PERÍODO (con proyecciones MSI en meses futuros)
# ======================================================================

def agrupar_por_periodo(transacciones: list[dict],
                        dia_corte: int) -> dict[str, dict]:
    """
    Agrupa transacciones por período de estado de cuenta e inyecta las
    mensualidades MSI proyectadas en sus períodos correspondientes.

    Retorna dict ordenado de más reciente a más antiguo.
    Los períodos futuros con solo proyecciones MSI también aparecen,
    marcados con tiene_proyecciones=True para que la vista los distinga.
    """
    grupos: dict[str, dict] = {}

    def _agregar(t: dict, fecha_corte: date, fecha_inicio: date,
                 label: str, es_proyeccion: bool = False):
        if label not in grupos:
            grupos[label] = {
                "fecha_corte":        fecha_corte,
                "fecha_inicio":       fecha_inicio,
                "total":              0.0,
                "transacciones":      [],
                "tiene_proyecciones": False,
            }
        grupos[label]["transacciones"].append(t)
        if es_proyeccion:
            grupos[label]["tiene_proyecciones"] = True
        if t["tipo"] == "gasto":
            monto_real = (
                t.get("monto_por_mes", t["monto"])
                if t.get("meses_sin_intereses", 0) > 0
                else t["monto"]
            )
            grupos[label]["total"] = round(grupos[label]["total"] + monto_real, 2)

    # Paso 1: agrupar transacciones normales y el primer cargo MSI
    for t in transacciones:
        fecha = date.fromisoformat(t["fecha"])
        periodo = calcular_periodo_corte(fecha, dia_corte)
        _agregar(t, periodo["fecha_corte"], periodo["fecha_inicio"],
                 periodo["periodo_label"], es_proyeccion=False)

    # Paso 2: inyectar mensualidades 2, 3, ..., N en sus períodos futuros
    todos_msi = [t for t in transacciones if t.get("meses_sin_intereses", 0) > 0]

    for t in todos_msi:
        meses = t["meses_sin_intereses"]
        fecha_original = date.fromisoformat(t["fecha"])
        periodo_inicial = calcular_periodo_corte(fecha_original, dia_corte)
        monto_mensual = t.get("monto_por_mes", round(t["monto"] / meses, 2))

        for n in range(1, meses):   # mensualidades 2 en adelante
            fc_n = _fecha_corte_n(periodo_inicial["fecha_corte"], n, dia_corte)

            # Calcular fecha_inicio del período proyectado
            if fc_n.month > 1:
                a_ant, m_ant = fc_n.year, fc_n.month - 1
            else:
                a_ant, m_ant = fc_n.year - 1, 12
            u_ant = calendar.monthrange(a_ant, m_ant)[1]
            fi_n = date(a_ant, m_ant, min(dia_corte, u_ant)) + timedelta(days=1)

            label_n = _label_periodo(fc_n)
            proyeccion = {
                **t,
                "monto":                monto_mensual,
                "monto_por_mes":        monto_mensual,
                "es_proyeccion":        True,
                "mensualidad_num":      n + 1,
                "fecha_cargo_original": t["fecha"],
                "descripcion":          f"{t['descripcion']} ({n+1}/{meses})",
            }
            _agregar(proyeccion, fc_n, fi_n, label_n, es_proyeccion=True)

    return dict(
        sorted(grupos.items(), key=lambda x: x[1]["fecha_corte"], reverse=True)
    )


def inyectar_proyecciones_msi(
    transacciones: list[dict],
    dia_corte: int,
    desde: str,
    hasta: str,
    txs_msi_origen: list[dict] = None,
    tarjetas_map: dict = None,
) -> list[dict]:
    """
    Toma una lista de transacciones del rango visible y agrega las
    mensualidades MSI proyectadas (mes 2 en adelante) que caen en ese rango.

    txs_msi_origen: lista amplia con cargos MSI de meses anteriores.
    tarjetas_map: dict {tarjeta_id: tarjeta_dict} para obtener dia_corte
                  por tarjeta. Si se provee, dia_corte se ignora y se usa
                  el de cada tarjeta. Esto evita duplicados al llamar la
                  función una sola vez para múltiples tarjetas.
    """
    import calendar as _cal

    fecha_desde = date.fromisoformat(desde)
    fecha_hasta = date.fromisoformat(hasta)

    fuente    = txs_msi_origen if txs_msi_origen is not None else transacciones
    todos_msi = [t for t in fuente if t.get("meses_sin_intereses", 0) > 0]
    proyecciones = []

    for t in todos_msi:
        meses      = t["meses_sin_intereses"]
        monto_mens = t.get("monto_por_mes", round(t["monto"] / meses, 2))
        fecha_orig = date.fromisoformat(t["fecha"])

        # Resolver dia_corte: tarjetas_map tiene prioridad sobre el parámetro
        if tarjetas_map and t.get("tarjeta_id"):
            tarjeta_obj = tarjetas_map.get(t["tarjeta_id"])
            dc = tarjeta_obj["dia_corte"] if tarjeta_obj else (dia_corte or 1)
        else:
            dc = dia_corte or 1

        p_inicial = calcular_periodo_corte(fecha_orig, dc)

        for n in range(1, meses):           # mensualidades 2, 3, ..., N
            fc_n = _fecha_corte_n(p_inicial["fecha_corte"], n, dc)

            # Calcular fi_n (inicio del período, es la fecha que se muestra)
            if fc_n.month > 1:
                a_ant, m_ant = fc_n.year, fc_n.month - 1
            else:
                a_ant, m_ant = fc_n.year - 1, 12
            u_ant = _cal.monthrange(a_ant, m_ant)[1]
            fi_n  = date(a_ant, m_ant, min(dc, u_ant)) + timedelta(days=1)

            # Incluir solo si el inicio del período cae dentro del mes filtrado
            if not (fecha_desde <= fi_n <= fecha_hasta):
                continue

            proyecciones.append({
                **t,
                "monto":                monto_mens,
                "monto_por_mes":        monto_mens,
                "es_proyeccion":        True,
                "mensualidad_num":      n + 1,
                "fecha_cargo_original": t["fecha"],
                "fecha":                fi_n.isoformat(),
                "descripcion":          f"{t['descripcion']} ({n+1}/{meses})",
            })

    if not proyecciones:
        return transacciones

    combinadas = transacciones + proyecciones
    combinadas.sort(key=lambda x: (x["fecha"], x.get("id", 0)), reverse=True)
    return combinadas