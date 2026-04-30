import sqlite3, calendar, sys, os
from datetime import date
sys.path.insert(0, os.path.dirname(__file__))
from utils.calculos import estado_tarjeta, calcular_periodo_corte

conn = sqlite3.connect("data/finanzas.db")
conn.row_factory = sqlite3.Row
tarjetas = [dict(r) for r in conn.execute(
    "SELECT t.id, t.nombre, t.banco, t.dia_corte, t.dia_pago, t.limite, u.nombre as usuario "
    "FROM tarjeta_credito t JOIN usuario u ON t.usuario_id=u.id WHERE t.activa=1 ORDER BY t.id"
)]
all_txs = [dict(r) for r in conn.execute(
    "SELECT t.*, tc.nombre as tarjeta_nombre, tc.banco as tarjeta_banco, "
    "cat.nombre as categoria_nombre, cat.icono as categoria_icono, cat.color as categoria_color "
    "FROM transaccion t "
    "LEFT JOIN tarjeta_credito tc ON t.tarjeta_id=tc.id "
    "LEFT JOIN categoria cat ON t.categoria_id=cat.id "
    "WHERE t.tarjeta_id IS NOT NULL"
)]
conn.close()

hoy = date(2026, 4, 25)

for label, anio_sel, mes_sel_num, es_actual in [
    ("MARZO 2026 (past, ref=31-Mar)", 2026, 3, False),
    ("ABRIL 2026 (actual, ref=hoy=25-Abr)", 2026, 4, True),
]:
    print(f"\n{'='*65}")
    print(f"SELECTOR: {label}")
    print(f"{'='*65}")

    ultimo_mes = calendar.monthrange(anio_sel, mes_sel_num)[1]
    if es_actual:
        fecha_ref_mes = hoy
    else:
        fecha_ref_mes = date(anio_sel, mes_sel_num, ultimo_mes)

    for tarjeta in tarjetas:
        txs_t = [t for t in all_txs if t.get("tarjeta_id") == tarjeta["id"]]
        periodo_card = calcular_periodo_corte(fecha_ref_mes, tarjeta["dia_corte"])
        est = estado_tarjeta(tarjeta, txs_t, fecha_corte_objetivo=periodo_card["fecha_corte"])
        p = est["periodo_actual"]
        print(f"  [{tarjeta['usuario']}] {tarjeta['banco']} {tarjeta['nombre']} "
              f"(corte={tarjeta['dia_corte']}, pago={tarjeta['dia_pago']})")
        print(f"    Periodo : {p['fecha_inicio']} al {p['fecha_corte']} ({p['periodo_label']})")
        print(f"    Total   : ${est['total_periodo']:,.2f}   Pago: {est['fecha_pago']}  "
              f"({est['dias_para_pago']:+d}d desde hoy)")
