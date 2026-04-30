"""
views/dashboard.py
------------------
Vista principal. Muestra de un vistazo:
  - Resumen del mes: ingresos, gastos, ahorro
  - Gastos por categoría (gráfica de dona)
  - Estado de todas las tarjetas activas
  - Balance de pareja del mes
  - Préstamos pendientes
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import date
from database.queries import (
    obtener_usuarios, obtener_transacciones,
    obtener_tarjetas, obtener_prestamos,
    calcular_balance_pareja, obtener_tarjetas_todas,
)
from utils.calculos import estado_tarjeta, calcular_periodo_corte, MESES_ES, inyectar_proyecciones_msi


def _opciones_meses(n: int = 12, meses_adelante: int = 1) -> list[dict]:
    """Genera meses_adelante meses futuros + los últimos N meses como opciones de selector."""
    hoy = date.today()
    meses = []
    import calendar as _cal
    for i in range(-meses_adelante, n):
        mes = hoy.month - i
        anio = hoy.year
        while mes <= 0:
            mes += 12
            anio -= 1
        while mes > 12:
            mes -= 12
            anio += 1
        ultimo = _cal.monthrange(anio, mes)[1]
        meses.append({
            "label":   f"{MESES_ES[mes]} {anio}",
            "periodo": f"{anio}-{mes:02d}",
            "desde":   f"{anio}-{mes:02d}-01",
            "hasta":   f"{anio}-{mes:02d}-{ultimo:02d}",
            "es_actual": i == 0,
            "es_futuro": i < 0,
            "fecha_ref": date(anio, mes, min(hoy.day, ultimo)),
        })
    return meses


def _gauge_tarjeta(nombre: str, usado: float, limite: float, color: str) -> go.Figure:
    pct = min(usado / limite * 100, 100) if limite > 0 else 0
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number={"suffix": "%", "font": {"size": 18}},
        title={"text": nombre, "font": {"size": 13}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 0, "showticklabels": False},
            "bar": {"color": color, "thickness": 0.25},
            "bgcolor": "#f1efea",
            "steps": [
                {"range": [0, 60],  "color": "#EAF3DE"},
                {"range": [60, 85], "color": "#FAEEDA"},
                {"range": [85, 100],"color": "#FCEBEB"},
            ],
            "threshold": {
                "line": {"color": "#E24B4A", "width": 2},
                "thickness": 0.8,
                "value": 85,
            },
        },
    ))
    fig.update_layout(
        height=160, margin=dict(t=30, b=10, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "sans-serif"},
    )
    return fig


def render():
    st.title("📊 Dashboard")

    usuarios = obtener_usuarios()
    if len(usuarios) < 2:
        st.info("Configura los perfiles en ⚙️ Configuración para comenzar.")
        return

    usuario_activo = st.session_state.get("usuario_activo", usuarios[0])
    hoy = date.today()

    # ── Selectores: mes y vista ─────────────────────────────────────────
    opciones = _opciones_meses()
    labels   = [m["label"] for m in opciones]
    col_mes, col_vista = st.columns([2, 2])
    with col_mes:
        idx_actual = next(i for i, m in enumerate(opciones) if m["es_actual"])
        sel_label = st.selectbox(
            "Mes", labels, index=idx_actual, key="dash_mes",
            help="Puedes ver el dashboard del mes anterior, actual o próximo"
        )
    with col_vista:
        vista = st.radio(
            "Vista", ["👤 Individual", "👫 Pareja"],
            horizontal=True, label_visibility="collapsed"
        )

    mes_sel   = opciones[labels.index(sel_label)]
    desde     = mes_sel["desde"]
    hasta     = mes_sel["hasta"]
    periodo   = mes_sel["periodo"]
    label_mes = mes_sel["label"]
    es_pareja = vista == "👫 Pareja"

    st.markdown(f"#### {label_mes}")
    st.divider()

    # ── Obtener transacciones ───────────────────────────────────────────
    uid = None if es_pareja else usuario_activo["id"]
    txs = obtener_transacciones(usuario_id=uid, desde=desde, hasta=hasta)

    todas_tarjetas = obtener_tarjetas_todas(uid)
    tarjetas_map   = {t["id"]: t for t in todas_tarjetas}
    desde_amplio   = date(hoy.year - 3, 1, 1).strftime("%Y-%m-%d")
    txs_msi_base   = obtener_transacciones(
        usuario_id=uid, desde=desde_amplio, hasta=hasta, tipo="gasto"
    )
    txs_msi_base = [t for t in txs_msi_base if t.get("meses_sin_intereses", 0) > 0]
    if txs_msi_base:
        txs = inyectar_proyecciones_msi(
            txs, dia_corte=None, desde=desde, hasta=hasta,
            txs_msi_origen=txs_msi_base,
            tarjetas_map=tarjetas_map,
        )

    gastos_tx   = [t for t in txs if t["tipo"] == "gasto"]
    ingresos_tx = [t for t in txs if t["tipo"] == "ingreso"]

    total_gastos   = sum(t["monto"] for t in gastos_tx)
    total_ingresos = sum(t["monto"] for t in ingresos_tx)
    ahorro         = total_ingresos - total_gastos
    tasa_ahorro    = (ahorro / total_ingresos * 100) if total_ingresos > 0 else 0

    # ── Métricas principales ────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Ingresos", f"${total_ingresos:,.0f}")
    m2.metric("💸 Gastos",   f"${total_gastos:,.0f}")
    m3.metric(
        "🏦 Ahorro",
        f"${ahorro:,.0f}",
        delta=f"{tasa_ahorro:.1f}% del ingreso",
        delta_color="normal" if ahorro >= 0 else "inverse",
    )
    m4.metric("📝 Transacciones", str(len(txs)))

    st.divider()

    # ── Gráfica de gastos por categoría ────────────────────────────────
    col_graf, col_lista = st.columns([1, 1])

    with col_graf:
        st.markdown("##### Gastos por categoría")
        if not gastos_tx:
            st.caption("Sin gastos registrados este mes.")
        else:
            # Agrupar por categoría
            categorias: dict[str, float] = {}
            colores_cat: dict[str, str]  = {}
            for t in gastos_tx:
                cat = t.get("categoria_nombre") or "Sin categoría"
                categorias[cat] = categorias.get(cat, 0) + t["monto"]
                colores_cat[cat] = t.get("categoria_color") or "#888780"

            cats_sorted = sorted(categorias.items(), key=lambda x: x[1], reverse=True)
            labels = [c[0] for c in cats_sorted]
            values = [c[1] for c in cats_sorted]
            colors = [colores_cat[c[0]] for c in cats_sorted]

            fig = go.Figure(go.Pie(
                labels=labels,
                values=values,
                hole=0.55,
                marker=dict(colors=colors, line=dict(color="#fff", width=2)),
                textinfo="percent",
                textfont=dict(size=11),
                hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>",
            ))
            fig.update_layout(
                height=300,
                margin=dict(t=10, b=10, l=0, r=0),
                paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                annotations=[dict(
                    text=f"${total_gastos:,.0f}",
                    x=0.5, y=0.5, font_size=16, showarrow=False,
                    font=dict(family="sans-serif"),
                )],
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_lista:
        st.markdown("##### Detalle")
        if gastos_tx:
            for nombre, monto in cats_sorted[:8]:
                pct = monto / total_gastos * 100 if total_gastos > 0 else 0
                color = colores_cat[nombre]
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;"
                    f"align-items:center;margin-bottom:6px'>"
                    f"<span style='font-size:13px'>{nombre}</span>"
                    f"<span style='font-size:13px;font-weight:500'>${monto:,.0f}</span>"
                    f"</div>"
                    f"<div style='background:#eee;border-radius:4px;height:4px;margin-bottom:10px'>"
                    f"<div style='background:{color};width:{pct:.1f}%;height:4px;"
                    f"border-radius:4px'></div></div>",
                    unsafe_allow_html=True,
                )

    st.divider()

    # ── Estado de tarjetas ──────────────────────────────────────────────
    st.markdown("##### Estado de tarjetas")

    uids_mostrar = (
        [u["id"] for u in usuarios] if es_pareja else [usuario_activo["id"]]
    )
    tarjetas_todas = []
    for uid_t in uids_mostrar:
        tarjetas_todas.extend(obtener_tarjetas(uid_t))

    if not tarjetas_todas:
        st.caption("Sin tarjetas registradas.")
    else:
        cols_t = st.columns(min(len(tarjetas_todas), 4))
        import calendar as _cal
        anio_sel    = int(periodo[:4])
        mes_sel_num = int(periodo[5:7])
        ultimo_mes  = _cal.monthrange(anio_sel, mes_sel_num)[1]

        # Día 1 del mes seleccionado garantiza que calcular_periodo_corte devuelva
        # el período cuyo CORTE cae dentro de ese mes (mismo monto y misma fecha de pago).
        fecha_ref_mes = date(anio_sel, mes_sel_num, 1)
        hasta_tx = hoy if mes_sel["es_actual"] else date(anio_sel, mes_sel_num, ultimo_mes)

        # Se retroceden 3 años para capturar cargos MSI de hasta 36 meses de antigüedad
        # (ej. iPhone a 24 MSI comprado hace 15 meses quedaría fuera con solo 1 año).
        desde_msi = date(hoy.year - 3, 1, 1).strftime("%Y-%m-%d")
        txs_todas = obtener_transacciones(
            desde=desde_msi,
            hasta=hasta_tx.strftime("%Y-%m-%d"),
        )
        for col, tarjeta in zip(cols_t, tarjetas_todas):
            txs_t = [t for t in txs_todas if t.get("tarjeta_id") == tarjeta["id"]]
            # El período a mostrar se deriva de fecha_ref_mes con el corte de la tarjeta.
            # Los días para pago se calculan desde date.today() (default en estado_tarjeta).
            periodo_card = calcular_periodo_corte(fecha_ref_mes, tarjeta["dia_corte"])
            est = estado_tarjeta(tarjeta, txs_t, fecha_corte_objetivo=periodo_card["fecha_corte"])

            # Cuánto me deben en préstamos vinculados a txs de esta tarjeta en el período
            tarjeta_owner = next(
                (u for u in usuarios if u["id"] == tarjeta["usuario_id"]), usuario_activo
            )
            seen_pids: set = set()
            me_deben_tarjeta = 0.0
            for t in est["transacciones"]:
                pid = t.get("prestamo_id")
                if (pid is not None
                        and pid not in seen_pids
                        and t.get("prestamo_acreedor") == tarjeta_owner["nombre"]):
                    meses = t.get("meses_sin_intereses", 0)
                    prestamo_orig = t.get("prestamo_monto_original") or 0
                    if meses > 0:
                        # MSI: fracción proporcional de la mensualidad
                        tx_total = t["monto"] * meses
                        aporte = round(t["monto"] * (prestamo_orig / tx_total), 2) if tx_total > 0 else 0.0
                    else:
                        aporte = prestamo_orig
                    me_deben_tarjeta += aporte
                    seen_pids.add(pid)
            me_deben_tarjeta = round(me_deben_tarjeta, 2)
            real_a_pagar = round(est["total_periodo"] - me_deben_tarjeta, 2)

            # Mes actual y el corte ya pasó: el período mostrado es el recién abierto
            # (próximo mes), pero el pago más inminente es el del período que acaba de
            # cerrar en el mes actual → mostrar ESE pago, no el del período abierto.
            color = (
                "#E24B4A" if est["porcentaje_limite"] > 85
                else "#EF9F27" if est["porcentaje_limite"] > 60
                else "#378ADD"
            )
            with col:
                st.plotly_chart(
                    _gauge_tarjeta(
                        tarjeta["nombre"],
                        est["total_periodo"],
                        tarjeta["limite"],
                        color,
                    ),
                    use_container_width=True,
                    key=f"gauge_{tarjeta['id']}",
                )
                dias = est["dias_para_pago"]
                color_dias = (
                    "#E24B4A" if dias <= 3
                    else "#EF9F27" if dias <= 7
                    else "#639922"
                )
                st.markdown(
                    f"<p style='text-align:center;font-size:12px;margin:-8px 0 0'>"
                    f"<span style='color:{color_dias}'>"
                    f"Pago en {dias}d · {est['fecha_pago'].strftime('%d/%m')}</span><br>"
                    f"<span style='color:gray'>${est['total_periodo']:,.0f} "
                    f"de ${tarjeta['limite']:,.0f}</span></p>",
                    unsafe_allow_html=True,
                )
                if me_deben_tarjeta > 0:
                    st.markdown(
                        f"<p style='text-align:center;font-size:11px;margin:4px 0 0'>"
                        f"<span style='color:#888'>Me deben </span>"
                        f"<span style='color:#EF9F27;font-weight:600'>"
                        f"${me_deben_tarjeta:,.0f}</span>"
                        f"<span style='color:#888'> · Real: </span>"
                        f"<span style='color:#639922;font-weight:600'>"
                        f"${real_a_pagar:,.0f}</span></p>",
                        unsafe_allow_html=True,
                    )

    st.divider()

    # ── Balance de pareja ───────────────────────────────────────────────
    st.markdown("##### Balance de pareja")
    balance = calcular_balance_pareja(periodo)

    if "error" in balance:
        st.caption(balance["error"])
    else:
        u1n = balance["usuario_1"]["nombre"]
        u2n = balance["usuario_2"]["nombre"]
        bc1, bc2 = st.columns(2)
        bc1.metric(f"{u1n} debe", f"${balance['debe_u1']:,.2f}")
        bc2.metric(f"{u2n} debe", f"${balance['debe_u2']:,.2f}")

        color_bal = "#E24B4A" if balance["balance"] != 0 else "#639922"
        st.markdown(
            f"<div style='background:#f8f7f4;border-radius:10px;padding:1rem 1.2rem;"
            f"margin-top:0.5rem;border-left:4px solid {color_bal}'>"
            f"<span style='font-size:15px;font-weight:500'>{balance['descripcion']}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if balance["balance"] != 0:
            if st.button("⚖️ Ir a liquidar cuentas"):
                st.session_state["pagina_actual"] = "⚖️  Liquidar cuentas"
                st.rerun()

    # ── Préstamos pendientes ────────────────────────────────────────────
    prestamos_p = obtener_prestamos(
        usuario_id=usuario_activo["id"], estado="pendiente"
    )
    if prestamos_p:
        st.divider()
        st.markdown("##### Préstamos pendientes")
        total_debo  = sum(p["monto_pendiente"] for p in prestamos_p
                          if p["deudor_id"] == usuario_activo["id"])
        total_deben = sum(p["monto_pendiente"] for p in prestamos_p
                          if p["acreedor_id"] == usuario_activo["id"])
        pc1, pc2 = st.columns(2)
        pc1.metric("Yo debo",  f"${total_debo:,.2f}",  delta_color="inverse")
        pc2.metric("Me deben", f"${total_deben:,.2f}", delta_color="off")