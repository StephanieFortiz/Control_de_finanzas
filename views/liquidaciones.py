"""
views/liquidaciones.py
"""
import streamlit as st
from datetime import date
from database.queries import (
    obtener_usuarios, calcular_balance_pareja,
    registrar_liquidacion, obtener_liquidaciones,
)
from utils.calculos import MESES_ES


def _opciones_periodos(n: int = 12) -> list[str]:
    hoy = date.today()
    periodos = []
    for i in range(n):
        mes = hoy.month - i
        anio = hoy.year
        while mes <= 0:
            mes += 12
            anio -= 1
        periodos.append(f"{anio}-{mes:02d}")
    return periodos


def _label_periodo(periodo: str) -> str:
    anio, mes = periodo.split("-")
    return f"{MESES_ES[int(mes)]} {anio}"


def render():
    st.title("⚖️ Liquidar cuentas")

    usuarios = obtener_usuarios()
    if len(usuarios) < 2:
        st.warning("Primero crea los perfiles en ⚙️ Configuración.")
        return

    periodos  = _opciones_periodos()
    labels    = [_label_periodo(p) for p in periodos]
    sel_label = st.selectbox("Período", labels, key="liq_periodo")
    periodo   = periodos[labels.index(sel_label)]

    st.divider()

    balance = calcular_balance_pareja(periodo)

    if "error" in balance:
        st.warning(balance["error"])
        return

    u1 = balance["usuario_1"]
    u2 = balance["usuario_2"]

    # ── Métricas ────────────────────────────────────────────────────────
    m1, m2 = st.columns(2)
    m1.metric(f"{u1['nombre']} debe", f"${balance['debe_u1']:,.2f}")
    m2.metric(f"{u2['nombre']} debe", f"${balance['debe_u2']:,.2f}")

    abs_balance = abs(balance["balance"])

    if balance["balance"] == 0:
        st.success("✅ Están a mano — no se deben nada.")
        _render_prestamos_detalle(balance)
        _render_historial()
        return

    deudor_obj   = u1 if balance["balance"] > 0 else u2
    acreedor_obj = u2 if balance["balance"] > 0 else u1

    st.markdown(
        f"<div style='background:#FAEEDA;border-left:4px solid #EF9F27;"
        f"border-radius:8px;padding:1rem 1.2rem;margin:0.5rem 0'>"
        f"<span style='font-size:16px;font-weight:500;color:#633806'>"
        f"{deudor_obj['nombre']} le debe "
        f"<span style='font-size:20px'>${abs_balance:,.2f}</span> "
        f"a {acreedor_obj['nombre']}</span></div>",
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Desglose de préstamos pendientes ────────────────────────────────
    _render_prestamos_detalle(balance)

    st.divider()

    # ── Registrar liquidación ───────────────────────────────────────────
    st.markdown("#### Registrar pago")
    liquidaciones_prev = [l for l in obtener_liquidaciones() if l["periodo"] == periodo]
    if liquidaciones_prev:
        liq = liquidaciones_prev[0]
        st.success(
            f"✅ Liquidado el {liq['fecha']}: "
            f"**{liq['origen_nombre']}** pagó **${liq['monto']:,.2f}** "
            f"a **{liq['destino_nombre']}**."
        )
    else:
        with st.form("form_liquidacion"):
            st.markdown(
                f"Confirma que **{deudor_obj['nombre']}** le pagó "
                f"**${abs_balance:,.2f}** a **{acreedor_obj['nombre']}**."
            )
            col_m, col_f = st.columns(2)
            with col_m:
                monto_liq = st.number_input(
                    "Monto pagado ($)", min_value=0.01,
                    value=float(round(abs_balance, 2)),
                    step=10.0, format="%.2f",
                )
            with col_f:
                fecha_liq = st.date_input("Fecha del pago", value=date.today())
            notas_liq = st.text_input("Notas (opcional)",
                                      placeholder="Ej: Transferencia BBVA")
            if st.form_submit_button("✅ Confirmar liquidación", type="primary"):
                registrar_liquidacion(
                    usuario_origen_id=deudor_obj["id"],
                    usuario_destino_id=acreedor_obj["id"],
                    monto=monto_liq,
                    fecha=str(fecha_liq),
                    periodo=periodo,
                    notas=notas_liq.strip(),
                )
                st.success(
                    f"✅ {deudor_obj['nombre']} pagó "
                    f"${monto_liq:,.2f} a {acreedor_obj['nombre']}."
                )
                st.rerun()

    _render_historial()


def _render_prestamos_detalle(balance: dict):
    prestamos = balance.get("prestamos", [])
    with st.expander("📋 Préstamos pendientes entre ustedes", expanded=True):
        if not prestamos:
            st.caption("No hay préstamos pendientes entre los dos.")
            return
        for p in prestamos:
            col_a, col_b, col_c = st.columns([3, 1.5, 1.5])
            with col_a:
                titulo = p.get("notas") or "Préstamo"
                gasto_ref = ""
                if p.get("tx_descripcion"):
                    gasto_ref = (
                        f"<br><span style='font-size:11px;color:#888'>"
                        f"🧾 {p['tx_descripcion']} · ${p['tx_monto']:,.2f}</span>"
                    )
                st.markdown(
                    f"**{titulo}**{gasto_ref}  \n"
                    f"<span style='font-size:12px;color:gray'>{p['fecha']}</span>",
                    unsafe_allow_html=True,
                )
            with col_b:
                st.markdown(
                    f"<span style='font-weight:500'>\${p['monto_pendiente']:,.2f}</span>  \n"
                    f"<span style='font-size:11px;color:gray'>de ${p['monto_original']:,.2f}</span>",
                    unsafe_allow_html=True,
                )
            with col_c:
                if p.get("fecha_estimada_pago"):
                    st.caption(f"Pago est. {p['fecha_estimada_pago']}")


def _render_historial():
    st.divider()
    st.markdown("#### Historial de liquidaciones")
    liquidaciones = obtener_liquidaciones()
    if not liquidaciones:
        st.caption("Aún no hay liquidaciones registradas.")
        return
    for liq in liquidaciones:
        st.markdown(
            f"**{_label_periodo(liq['periodo'])}** · "
            f"{liq['origen_nombre']} → {liq['destino_nombre']} · "
            f"**${liq['monto']:,.2f}** · {liq['fecha']}"
            + (f" · _{liq['notas']}_" if liq.get("notas") else ""),
        )