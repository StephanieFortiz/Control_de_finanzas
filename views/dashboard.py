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
from datetime import date
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


def _opciones_periodos(dia_corte: int, n: int = 14) -> list[dict]:
    """Genera n períodos de estado de cuenta (más reciente primero)."""
    hoy = date.today()
    periodos: list[dict] = []
    seen: set[str] = set()

    for i in range(-1, n + 4):
        mes = hoy.month - i
        anio = hoy.year
        while mes <= 0:
            mes += 12
            anio -= 1

        p = calcular_periodo_corte(date(anio, mes, 1), dia_corte)
        label = p["periodo_label"]
        if label in seen:
            continue
        seen.add(label)

        fi, fc = p["fecha_inicio"], p["fecha_corte"]
        periodos.append({
            "label":     f"{label}  ({fi.strftime('%d/%m')} – {fc.strftime('%d/%m/%y')})",
            "label_short": label,
            "desde":     fi.isoformat(),
            "hasta":     fc.isoformat(),
            "anio":      fc.year,
            "mes":       fc.month,
            "es_actual": fi <= hoy <= fc,
        })

        if len(periodos) >= n:
            break

    return periodos


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

    # ── Selector de período ──────────────────────────────────────────────────
    tarjetas_usuario = obtener_tarjetas(uid)
    dia_corte_ref    = tarjetas_usuario[0]["dia_corte"] if tarjetas_usuario else 1

    periodos  = _opciones_periodos(dia_corte_ref)
    labels    = [p["label"] for p in periodos]
    idx_actual = next((i for i, p in enumerate(periodos) if p["es_actual"]), 0)

    sel          = st.selectbox("Período", labels, index=idx_actual, key="dash_periodo")
    periodo_sel  = periodos[labels.index(sel)]
    desde        = periodo_sel["desde"]
    hasta        = periodo_sel["hasta"]

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

    total_gastos   = round(sum(_monto_efectivo(t) for t in gastos_tx), 2)
    total_ingresos = round(sum(t["monto"] for t in ingresos_tx), 2)
    ahorro         = round(total_ingresos - total_gastos, 2)
    tasa_ahorro    = (ahorro / total_ingresos * 100) if total_ingresos > 0 else 0
    n_cargos_reales = sum(1 for t in gastos_tx if not t.get("es_proyeccion"))

    # ── 1. Métricas resumen ──────────────────────────────────────────────────
    st.markdown(f"#### {periodo_sel['label_short']}")
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

    if not tarjetas_usuario:
        st.caption("Sin tarjetas registradas.")
    else:
        txs_card_base = obtener_transacciones(
            usuario_id=uid, desde=desde_amplio, hasta=hasta
        )
        fecha_ref_mes = date(periodo_sel["anio"], periodo_sel["mes"], 1)
        cols_t = st.columns(min(len(tarjetas_usuario), 4))

        for col, tarjeta in zip(cols_t, tarjetas_usuario):
            txs_t       = [t for t in txs_card_base if t.get("tarjeta_id") == tarjeta["id"]]
            periodo_card = calcular_periodo_corte(fecha_ref_mes, tarjeta["dia_corte"])
            est          = estado_tarjeta(
                tarjeta, txs_t, fecha_corte_objetivo=periodo_card["fecha_corte"]
            )
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

    # ── 3. Gastos por categoría ──────────────────────────────────────────────
    st.markdown("##### 📂 Gastos por categoría")

    cat_data: dict[str, dict] = defaultdict(
        lambda: {"monto": 0.0, "color": "#888780", "txs": []}
    )
    for t in gastos_tx:
        cat = t.get("categoria_nombre") or "Sin categoría"
        m   = _monto_efectivo(t)
        cat_data[cat]["monto"] += m
        cat_data[cat]["color"]  = t.get("categoria_color") or "#888780"
        cat_data[cat]["txs"].append(t)

    cats_sorted = sorted(cat_data.items(), key=lambda x: x[1]["monto"], reverse=True)

    col_dona, col_detalle = st.columns([1, 1])

    with col_dona:
        fig_dona = go.Figure(go.Pie(
            labels=[c[0] for c in cats_sorted],
            values=[c[1]["monto"] for c in cats_sorted],
            hole=0.55,
            marker=dict(
                colors=[c[1]["color"] for c in cats_sorted],
                line=dict(color="#fff", width=2),
            ),
            textinfo="percent",
            textfont=dict(size=11),
            hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>",
        ))
        fig_dona.update_layout(
            height=300, margin=dict(t=10, b=10, l=0, r=0),
            paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
            annotations=[dict(
                text=f"${total_gastos:,.2f}", x=0.5, y=0.5,
                font_size=16, showarrow=False, font=dict(family="sans-serif"),
            )],
        )
        st.plotly_chart(fig_dona, use_container_width=True)

    with col_detalle:
        for nombre, data in cats_sorted:
            monto_cat = data["monto"]
            pct       = monto_cat / total_gastos * 100 if total_gastos > 0 else 0
            txs_cat   = sorted(data["txs"], key=_monto_efectivo, reverse=True)

            with st.expander(f"**{nombre}**  ·  ${monto_cat:,.2f}  ·  {pct:.1f}%"):
                for t in txs_cat:
                    m_t      = _monto_efectivo(t)
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

    # ── 4. Tendencia de gastos en el período ─────────────────────────────────
    st.markdown("##### 📈 Tendencia de gastos")

    gastos_por_dia: dict[str, float] = defaultdict(float)
    for t in gastos_tx:
        gastos_por_dia[t["fecha"]] += _monto_efectivo(t)

    fechas_ord = sorted(gastos_por_dia)
    montos_dia = [gastos_por_dia[f] for f in fechas_ord]
    acumulado  = []
    acc = 0.0
    for m in montos_dia:
        acc += m
        acumulado.append(round(acc, 2))

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Bar(
        x=fechas_ord, y=montos_dia,
        name="Gasto diario",
        marker_color="#378ADD",
        opacity=0.65,
        hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
    ))
    fig_trend.add_trace(go.Scatter(
        x=fechas_ord, y=acumulado,
        name="Acumulado",
        line=dict(color="#E24B4A", width=2.5),
        mode="lines+markers",
        marker=dict(size=5, color="#E24B4A"),
        yaxis="y2",
        hovertemplate="<b>%{x}</b><br>Acum: $%{y:,.2f}<extra></extra>",
    ))
    fig_trend.update_layout(
        height=280,
        margin=dict(t=10, b=10, l=0, r=60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, tickformat="%d %b", tickangle=-30),
        yaxis=dict(
            showgrid=True, gridcolor="#f0f0f0",
            tickprefix="$", title="Diario",
        ),
        yaxis2=dict(
            overlaying="y", side="right",
            showgrid=False, tickprefix="$", title="Acumulado",
        ),
        legend=dict(orientation="h", y=1.08, x=0, bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
        barmode="stack",
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    st.divider()

    # ── 5. Análisis por tarjeta ───────────────────────────────────────────────
    tarjetas_en_periodo: dict[int, str] = {}
    for t in gastos_tx:
        tid = t.get("tarjeta_id")
        if tid:
            tarjetas_en_periodo[tid] = t.get("tarjeta_nombre") or str(tid)

    if not tarjetas_en_periodo:
        return

    st.markdown("##### 🃏 Análisis por tarjeta")

    # 5a. Uso por número de transacciones
    col_uso, col_space = st.columns([1, 1])
    with col_uso:
        conteo: dict[str, int] = defaultdict(int)
        for t in gastos_tx:
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

    # 5b. Gastos por categoría en cada tarjeta
    st.markdown("###### Gastos por categoría en cada tarjeta")

    items  = list(tarjetas_en_periodo.items())
    chunks = [items[i:i+3] for i in range(0, len(items), 3)]

    for chunk in chunks:
        cols_chunk = st.columns(len(chunk))
        for col, (tid, tnombre) in zip(cols_chunk, chunk):
            txs_t = [t for t in gastos_tx if t.get("tarjeta_id") == tid]

            cat_t: dict[str, dict] = defaultdict(
                lambda: {"monto": 0.0, "color": "#888780"}
            )
            for t in txs_t:
                cat = t.get("categoria_nombre") or "Sin categoría"
                cat_t[cat]["monto"] += _monto_efectivo(t)
                cat_t[cat]["color"]  = t.get("categoria_color") or "#888780"

            cats_t  = sorted(cat_t.items(), key=lambda x: x[1]["monto"], reverse=True)
            total_t = sum(v["monto"] for v in cat_t.values())

            with col:
                fig_t = go.Figure(go.Pie(
                    labels=[c[0] for c in cats_t],
                    values=[c[1]["monto"] for c in cats_t],
                    hole=0.5,
                    marker=dict(
                        colors=[c[1]["color"] for c in cats_t],
                        line=dict(color="#fff", width=1.5),
                    ),
                    textinfo="percent",
                    textfont=dict(size=10),
                    hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<extra></extra>",
                ))
                fig_t.update_layout(
                    title=dict(text=tnombre, font_size=13),
                    height=260,
                    margin=dict(t=35, b=5, l=0, r=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    annotations=[dict(
                        text=f"${total_t:,.2f}", x=0.5, y=0.5,
                        font_size=12, showarrow=False,
                    )],
                )
                st.plotly_chart(fig_t, use_container_width=True, key=f"pie_t_{tid}")