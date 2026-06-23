"""
views/dashboard.py
------------------
Dashboard principal. Flujo de lo general a lo particular:
  1. Métricas resumen (ingresos, gastos, ahorro)
  2. Estado de tarjetas (gauges de uso)
  3. Gastos por categoría (dona + detalle desplegable)
  4. Tendencia de gastos en el período (barras diarias + acumulado)
  5. Análisis por tarjeta (uso por transacciones + categoría por tarjeta)
"""

import streamlit as st
import plotly.graph_objects as go
from collections import defaultdict
from datetime import date, timedelta
import calendar as _cal
from database.queries import (
    obtener_usuarios, obtener_transacciones, obtener_tarjetas,
)
from utils.calculos import (
    estado_tarjeta, calcular_periodo_corte, MESES_ES, inyectar_proyecciones_msi,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _monto_efectivo(t: dict) -> float:
    """Para MSI originales usa monto_por_mes; para proyecciones y no-MSI, monto."""
    if t.get("meses_sin_intereses", 0) > 0 and not t.get("es_proyeccion"):
        return t.get("monto_por_mes") or t["monto"]
    return t["monto"]


def _opciones_meses(n: int = 13) -> list[dict]:
    """Genera n meses calendario (más reciente primero, 1 mes adelante incluido)."""
    hoy = date.today()
    meses = []
    for i in range(-1, n):
        mes = hoy.month - i
        anio = hoy.year
        while mes <= 0:
            mes += 12; anio -= 1
        while mes > 12:
            mes -= 12; anio += 1
        ultimo = _cal.monthrange(anio, mes)[1]
        meses.append({
            "label":     f"{MESES_ES[mes]} {anio}",
            "desde":     f"{anio}-{mes:02d}-01",
            "hasta":     f"{anio}-{mes:02d}-{ultimo:02d}",
            "anio":      anio,
            "mes":       mes,
            "es_actual": i == 0,
        })
    return meses


def _gauge_tarjeta(nombre: str, usado: float, limite: float, color: str):
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
                {"range": [0,  60], "color": "#EAF3DE"},
                {"range": [60, 85], "color": "#FAEEDA"},
                {"range": [85,100], "color": "#FCEBEB"},
            ],
            "threshold": {"line": {"color": "#E24B4A", "width": 2},
                          "thickness": 0.8, "value": 85},
        },
    ))
    fig.update_layout(
        height=160, margin=dict(t=30, b=10, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "sans-serif"},
    )
    return fig


# ── Vista principal ────────────────────────────────────────────────────────────

def render():
    st.title("📊 Dashboard")

    usuarios = obtener_usuarios()
    if len(usuarios) < 2:
        st.info("Configura los perfiles en ⚙️ Configuración para comenzar.")
        return

    usuario_activo = st.session_state.get("usuario_activo", usuarios[0])
    hoy   = date.today()
    uid   = usuario_activo["id"]

    # ── Selector de mes ──────────────────────────────────────────────────────
    tarjetas_usuario = obtener_tarjetas(uid)
    meses_opts = _opciones_meses()
    labels_m   = [m["label"] for m in meses_opts]
    idx_actual = next((i for i, m in enumerate(meses_opts) if m["es_actual"]), 0)

    sel      = st.selectbox("Mes", labels_m, index=idx_actual, key="dash_periodo")
    mes_sel  = meses_opts[labels_m.index(sel)]
    desde    = mes_sel["desde"]
    hasta    = mes_sel["hasta"]

    # ── Transacciones del período ────────────────────────────────────────────
    txs = obtener_transacciones(usuario_id=uid, desde=desde, hasta=hasta)

    desde_amplio = date(hoy.year - 3, 1, 1).strftime("%Y-%m-%d")
    txs_msi_base = obtener_transacciones(
        usuario_id=uid, desde=desde_amplio, hasta=hasta, tipo="gasto"
    )
    txs_msi_base = [t for t in txs_msi_base if t.get("meses_sin_intereses", 0) > 0]
    if txs_msi_base:
        txs = inyectar_proyecciones_msi(
            txs, desde=desde, hasta=hasta, txs_msi_origen=txs_msi_base
        )

    gastos_tx   = [t for t in txs if t["tipo"] == "gasto"]
    ingresos_tx = [t for t in txs if t["tipo"] == "ingreso"]

    # ── Estados de tarjetas (calculados antes de métricas para usar en total) ──
    txs_card_base = obtener_transacciones(
        usuario_id=uid, desde=desde_amplio, hasta=hasta
    )
    fecha_ref_mes = date(mes_sel["anio"], mes_sel["mes"], 1)
    tarjetas_con_estado: list[tuple] = []
    for tarjeta in tarjetas_usuario:
        txs_t        = [t for t in txs_card_base if t.get("tarjeta_id") == tarjeta["id"]]
        periodo_card = calcular_periodo_corte(fecha_ref_mes, tarjeta["dia_corte"])
        est          = estado_tarjeta(
            tarjeta, txs_t, fecha_corte_objetivo=periodo_card["fecha_corte"]
        )
        tarjetas_con_estado.append((tarjeta, est))

    # Gastos = suma de pagos de tarjetas del mes + efectivo/débito del mes
    total_tarjetas  = round(sum(est["total_periodo"] for _, est in tarjetas_con_estado), 2)
    gastos_efectivo = round(sum(
        _monto_efectivo(t) for t in gastos_tx if not t.get("tarjeta_id")
    ), 2)
    total_gastos    = round(total_tarjetas + gastos_efectivo, 2)
    total_ingresos  = round(sum(t["monto"] for t in ingresos_tx), 2)
    ahorro          = round(total_ingresos - total_gastos, 2)
    tasa_ahorro     = (ahorro / total_ingresos * 100) if total_ingresos > 0 else 0
    n_cargos_reales = sum(1 for t in gastos_tx if not t.get("es_proyeccion"))

    # ── 1. Métricas resumen ──────────────────────────────────────────────────
    st.markdown(f"#### {mes_sel['label']}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Ingresos",      f"${total_ingresos:,.2f}")
    m2.metric("💸 Gastos",        f"${total_gastos:,.2f}")
    m3.metric(
        "🏦 Ahorro", f"${ahorro:,.2f}",
        delta=f"{tasa_ahorro:.1f}% del ingreso",
        delta_color="normal" if ahorro >= 0 else "inverse",
    )
    m4.metric("🧾 Cargos", str(n_cargos_reales))

    st.divider()

    # ── 2. Estado de tarjetas ────────────────────────────────────────────────
    st.markdown("##### 💳 Estado de tarjetas")

    if not tarjetas_con_estado:
        st.caption("Sin tarjetas registradas.")
    else:
        cols_t = st.columns(min(len(tarjetas_con_estado), 4))
        for col, (tarjeta, est) in zip(cols_t, tarjetas_con_estado):
            color = (
                "#E24B4A" if est["porcentaje_limite"] > 85
                else "#EF9F27" if est["porcentaje_limite"] > 60
                else "#378ADD"
            )
            with col:
                st.plotly_chart(
                    _gauge_tarjeta(
                        tarjeta["nombre"], est["total_periodo"], tarjeta["limite"], color
                    ),
                    use_container_width=True,
                    key=f"gauge_{tarjeta['id']}",
                )
                dias       = est["dias_para_pago"]
                color_dias = "#E24B4A" if dias <= 3 else "#EF9F27" if dias <= 7 else "#639922"
                st.markdown(
                    f"<p style='text-align:center;font-size:12px;margin:-8px 0 4px'>"
                    f"<span style='color:{color_dias}'>"
                    f"Pago en {dias}d · {est['fecha_pago'].strftime('%d/%m')}</span><br>"
                    f"<span style='color:gray'>"
                    f"${est['total_periodo']:,.2f} de ${tarjeta['limite']:,.2f}</span></p>",
                    unsafe_allow_html=True,
                )

    st.divider()

    if not gastos_tx:
        st.caption("Sin gastos registrados en este período.")
        return

    # ── Tarjetas con gastos este período ────────────────────────────────────
    tarjetas_en_periodo: dict[int, str] = {}
    for t in gastos_tx:
        tid = t.get("tarjeta_id")
        if tid:
            tarjetas_en_periodo[tid] = t.get("tarjeta_nombre") or str(tid)

    # ── Filtro de tarjeta ────────────────────────────────────────────────────
    if tarjetas_en_periodo:
        opciones_t = sorted(tarjetas_en_periodo.values())
        sel_t = st.multiselect(
            "Filtrar por tarjeta",
            options=opciones_t,
            default=opciones_t,
            key="dash_filtro_tarjeta",
        )
        if not sel_t or set(sel_t) == set(opciones_t):
            gastos_filtrados = gastos_tx
            ids_filtradas    = set(tarjetas_en_periodo.keys())
        else:
            sel_set          = set(sel_t)
            gastos_filtrados = [
                t for t in gastos_tx
                if t.get("tarjeta_nombre") in sel_set or not t.get("tarjeta_id")
            ]
            ids_filtradas = {tid for tid, tn in tarjetas_en_periodo.items() if tn in sel_set}
    else:
        gastos_filtrados = gastos_tx
        ids_filtradas    = set()

    # ── 3. Gastos por categoría ──────────────────────────────────────────────
    st.markdown("##### 📂 Gastos por categoría")

    cat_data: dict[str, dict] = defaultdict(
        lambda: {"monto": 0.0, "color": "#888780", "txs": []}
    )
    for t in gastos_filtrados:
        cat = t.get("categoria_nombre") or "Sin categoría"
        m   = _monto_efectivo(t)
        cat_data[cat]["monto"] += m
        cat_data[cat]["color"]  = t.get("categoria_color") or "#888780"
        cat_data[cat]["txs"].append(t)

    total_filtrado = sum(d["monto"] for d in cat_data.values())
    # ascending → el mayor queda arriba en barra horizontal
    cats_sorted     = sorted(cat_data.items(), key=lambda x: x[1]["monto"])
    cats_sorted_desc = list(reversed(cats_sorted))

    col_bar, col_detalle = st.columns([1, 1])

    with col_bar:
        fig_cat = go.Figure(go.Bar(
            x=[c[1]["monto"] for c in cats_sorted],
            y=[c[0] for c in cats_sorted],
            orientation="h",
            marker_color=[c[1]["color"] for c in cats_sorted],
            text=[f"${c[1]['monto']:,.0f}" for c in cats_sorted],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>$%{x:,.2f}<extra></extra>",
        ))
        fig_cat.update_layout(
            height=max(250, len(cats_sorted) * 38 + 60),
            margin=dict(t=10, b=10, l=0, r=90),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="#f0f0f0", tickprefix="$"),
            yaxis=dict(showgrid=False),
            showlegend=False,
        )
        st.plotly_chart(fig_cat, use_container_width=True)

    with col_detalle:
        for nombre, data in cats_sorted_desc:
            monto_cat = data["monto"]
            pct       = monto_cat / total_filtrado * 100 if total_filtrado > 0 else 0
            txs_cat   = sorted(data["txs"], key=_monto_efectivo, reverse=True)

            with st.expander(f"**{nombre}**  ·  ${monto_cat:,.2f}  ·  {pct:.1f}%"):
                for t in txs_cat:
                    m_t       = _monto_efectivo(t)
                    tarjeta_n = t.get("tarjeta_nombre") or "—"
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;"
                        f"align-items:center;padding:4px 0;"
                        f"border-bottom:1px solid #f0f0f0;font-size:13px'>"
                        f"<span style='flex:1;padding-right:8px'>{t['descripcion']}</span>"
                        f"<span style='white-space:nowrap'>"
                        f"<span style='color:#E24B4A;font-weight:500'>${m_t:,.2f}</span>"
                        f"  <span style='color:#aaa;font-size:11px'>{tarjeta_n}</span>"
                        f"</span></div>",
                        unsafe_allow_html=True,
                    )

    st.divider()

    # ── 4. Tendencia semanal (año a la fecha) ────────────────────────────────
    st.markdown("##### 📈 Gasto mensual — año a la fecha")

    desde_ytd = f"{hoy.year}-01-01"
    hasta_ytd = hoy.isoformat()

    txs_ytd = obtener_transacciones(usuario_id=uid, desde=desde_ytd, hasta=hasta_ytd)
    txs_msi_ytd = obtener_transacciones(
        usuario_id=uid, desde=desde_amplio, hasta=hasta_ytd, tipo="gasto"
    )
    txs_msi_ytd = [t for t in txs_msi_ytd if t.get("meses_sin_intereses", 0) > 0]
    if txs_msi_ytd:
        txs_ytd = inyectar_proyecciones_msi(
            txs_ytd, desde=desde_ytd, hasta=hasta_ytd, txs_msi_origen=txs_msi_ytd
        )
    gastos_ytd = [t for t in txs_ytd if t["tipo"] == "gasto"]

    gastos_por_mes: dict[str, float] = defaultdict(float)
    for t in gastos_ytd:
        mes_key = t["fecha"][:7]  # "YYYY-MM"
        gastos_por_mes[mes_key] += _monto_efectivo(t)

    meses_ord  = sorted(gastos_por_mes)
    montos_mes = [gastos_por_mes[m] for m in meses_ord]
    acum_sem: list[float] = []
    acc = 0.0
    for m in montos_mes:
        acc += m
        acum_sem.append(round(acc, 2))

    labels_sem = [
        MESES_ES[int(m[5:7])] + " " + m[:4] for m in meses_ord
    ]

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Bar(
        x=labels_sem, y=montos_mes,
        name="Gasto mensual",
        marker_color="#378ADD",
        opacity=0.65,
        hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
    ))
    fig_trend.add_trace(go.Scatter(
        x=labels_sem, y=acum_sem,
        name="Acumulado",
        line=dict(color="#E24B4A", width=2.5),
        mode="lines+markers",
        marker=dict(size=5, color="#E24B4A"),
        yaxis="y2",
        hovertemplate="<b>%{x}</b><br>Acum: $%{y:,.2f}<extra></extra>",
    ))
    fig_trend.update_layout(
        height=300,
        margin=dict(t=10, b=10, l=0, r=70),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, tickangle=-40),
        yaxis=dict(showgrid=True, gridcolor="#f0f0f0", tickprefix="$", title="Mensual"),
        yaxis2=dict(overlaying="y", side="right", showgrid=False, tickprefix="$", title="Acumulado"),
        legend=dict(orientation="h", y=1.08, x=0, bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    st.divider()

    # ── 5. Análisis por tarjeta ───────────────────────────────────────────────
    if not tarjetas_en_periodo:
        return

    st.markdown("##### 🃏 Análisis por tarjeta")

    # 5a. Uso por número de transacciones
    col_uso, col_space = st.columns([1, 1])
    with col_uso:
        conteo: dict[str, int] = defaultdict(int)
        for t in gastos_filtrados:
            if not t.get("es_proyeccion") and t.get("tarjeta_id"):
                conteo[t.get("tarjeta_nombre") or str(t["tarjeta_id"])] += 1

        nombres_t  = sorted(conteo, key=lambda k: conteo[k], reverse=True)
        valores_t  = [conteo[n] for n in nombres_t]
        colores_t  = ["#378ADD", "#EF9F27", "#639922", "#E24B4A",
                      "#9B59B6", "#1ABC9C", "#E67E22", "#2ECC71"]

        fig_uso = go.Figure(go.Bar(
            x=nombres_t, y=valores_t,
            marker_color=colores_t[:len(nombres_t)],
            text=valores_t, textposition="outside",
            hovertemplate="<b>%{x}</b><br>%{y} cargos<extra></extra>",
        ))
        fig_uso.update_layout(
            title=dict(text="Cargos por tarjeta", font_size=14),
            height=280,
            margin=dict(t=45, b=10, l=0, r=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor="#f0f0f0", title="# cargos"),
            xaxis=dict(showgrid=False),
            showlegend=False,
        )
        st.plotly_chart(fig_uso, use_container_width=True)

    st.divider()

    # 5b. Gastos por categoría — barras agrupadas por tarjeta
    st.markdown("###### Gastos por categoría en cada tarjeta")

    # Todas las categorías presentes en las tarjetas filtradas
    cat_totales_5b: dict[str, float] = defaultdict(float)
    for t in gastos_filtrados:
        if t.get("tarjeta_id") in ids_filtradas:
            cat_totales_5b[t.get("categoria_nombre") or "Sin categoría"] += _monto_efectivo(t)

    # Ascending → el mayor queda arriba en la barra horizontal
    cats_5b = sorted(cat_totales_5b.keys(), key=lambda c: cat_totales_5b[c])

    card_colors_5b = ["#378ADD", "#EF9F27", "#639922", "#E24B4A", "#9B59B6", "#1ABC9C"]
    fig_group = go.Figure()

    for i, (tid, tnombre) in enumerate(tarjetas_en_periodo.items()):
        if tid not in ids_filtradas:
            continue
        cat_m: dict[str, float] = defaultdict(float)
        for t in gastos_filtrados:
            if t.get("tarjeta_id") == tid:
                cat_m[t.get("categoria_nombre") or "Sin categoría"] += _monto_efectivo(t)

        fig_group.add_trace(go.Bar(
            name=tnombre,
            y=cats_5b,
            x=[cat_m.get(c, 0.0) for c in cats_5b],
            orientation="h",
            marker_color=card_colors_5b[i % len(card_colors_5b)],
            text=[f"${cat_m[c]:,.0f}" if cat_m.get(c, 0) > 0 else "" for c in cats_5b],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>%{fullData.name}: $%{x:,.2f}<extra></extra>",
        ))

    n_cats_5b  = len(cats_5b)
    n_cards_5b = sum(1 for tid in tarjetas_en_periodo if tid in ids_filtradas)
    fig_group.update_layout(
        barmode="group",
        height=max(280, n_cats_5b * 32 * max(n_cards_5b, 1) + 80),
        margin=dict(t=10, b=10, l=0, r=100),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="#f0f0f0", tickprefix="$"),
        yaxis=dict(showgrid=False),
        legend=dict(orientation="h", y=1.04, x=0, bgcolor="rgba(0,0,0,0)"),
        hovermode="y unified",
    )
    st.plotly_chart(fig_group, use_container_width=True)