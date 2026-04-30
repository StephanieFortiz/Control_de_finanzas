"""
views/tarjetas.py
-----------------
Vista del motor de tarjetas de crédito. Muestra:
  - Resumen por tarjeta: total del período, días para pago, alerta
  - Desglose de transacciones agrupadas por estado de cuenta
"""

import streamlit as st
from datetime import date
from database.queries import obtener_usuarios, obtener_tarjetas, obtener_transacciones
from utils.calculos import estado_tarjeta, agrupar_por_periodo, calcular_fecha_pago, MESES_ES


def _color_alerta(alerta: str) -> str:
    return {"urgente": "#E24B4A", "proximo": "#EF9F27", "ok": "#639922"}[alerta]


def _label_alerta(dias: int) -> str:
    if dias < 0:
        return f"Venció hace {abs(dias)} días"
    if dias == 0:
        return "Vence hoy"
    if dias <= 3:
        return f"Vence en {dias} días"
    if dias <= 7:
        return f"Vence en {dias} días"
    return f"Vence en {dias} días"


def render():
    st.title("💳 Tarjetas de crédito")

    usuarios = obtener_usuarios()
    if len(usuarios) < 2:
        st.warning("Primero crea los perfiles en ⚙️ Configuración.")
        return

    usuario_activo = st.session_state.get("usuario_activo", usuarios[0])
    hoy = date.today()

    tarjetas = obtener_tarjetas(usuario_activo["id"])
    if not tarjetas:
        st.info("No tienes tarjetas registradas. Agrégalas en ⚙️ Configuración.")
        return

    nombres_tabs = [t["nombre"] for t in tarjetas]
    tabs = st.tabs(nombres_tabs)

    for tab, tarjeta in zip(tabs, tarjetas):
        with tab:
            _render_tarjeta(tarjeta, usuario_activo, hoy)


def _render_tarjeta(tarjeta: dict, usuario_activo: dict, hoy: date):
    desde = date(hoy.year - 3, 1, 1).strftime("%Y-%m-%d")
    txs = obtener_transacciones(
        usuario_id=usuario_activo["id"],
        desde=desde,
        hasta=hoy.strftime("%Y-%m-%d"),
    )
    txs_tarjeta = [t for t in txs if t.get("tarjeta_id") == tarjeta["id"]]

    estado = estado_tarjeta(tarjeta, txs_tarjeta, hoy)
    periodo = estado["periodo_actual"]
    color_alerta = _color_alerta(estado["alerta"])

    # Encabezado
    col_info, col_alerta = st.columns([3, 1])
    with col_info:
        st.markdown(
            f"**{tarjeta['banco']}** · Corte día **{tarjeta['dia_corte']}** · "
            f"Pago día **{tarjeta['dia_pago']}**"
        )
        st.caption(
            f"Período actual: {periodo['periodo_label']} "
            f"({periodo['fecha_inicio'].strftime('%d/%m')} → "
            f"{periodo['fecha_corte'].strftime('%d/%m/%Y')})"
        )
    with col_alerta:
        st.markdown(
            f"<div style='text-align:right;font-size:13px;"
            f"color:{color_alerta};font-weight:500'>"
            f"{_label_alerta(estado['dias_para_pago'])}<br>"
            f"<span style='font-size:11px;color:gray'>"
            f"Pago: {estado['fecha_pago'].strftime('%d/%m/%Y')}</span></div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # Métricas
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Cargos este período", f"${estado['total_periodo']:,.2f}")
    m2.metric("Límite disponible",
              f"${max(tarjeta['limite'] - estado['total_periodo'], 0):,.2f}")
    m3.metric("% del límite usado", f"{estado['porcentaje_limite']}%")
    m4.metric("Días para corte", str(estado["dias_para_corte"]))

    if tarjeta["limite"] > 0:
        pct = min(estado["porcentaje_limite"] / 100, 1.0)
        color_barra = (
            "#E24B4A" if pct > 0.85 else "#EF9F27" if pct > 0.60 else "#639922"
        )
        st.markdown(
            f"<div style='background:#eee;border-radius:6px;height:8px;margin:4px 0 16px'>"
            f"<div style='background:{color_barra};width:{pct*100:.1f}%;"
            f"height:8px;border-radius:6px'></div></div>",
            unsafe_allow_html=True,
        )

    # Transacciones del período actual
    st.markdown(f"##### Cargos en {periodo['periodo_label']}")
    txs_actuales = estado["transacciones"]
    if not txs_actuales:
        st.caption("Sin cargos en este período aún.")
    else:
        for t in sorted(txs_actuales, key=lambda x: x["fecha"], reverse=True):
            _fila_transaccion(t)

    st.divider()

    # Historial por períodos
    st.markdown("##### Historial de estados de cuenta")
    grupos = agrupar_por_periodo(txs_tarjeta, tarjeta["dia_corte"])

    if not grupos:
        st.caption("Sin historial disponible.")
        return

    for label, grupo in grupos.items():
        es_actual = label == periodo["periodo_label"]
        # Calcular fecha de pago para este grupo
        fc = grupo["fecha_corte"]
        fp_str = calcular_fecha_pago(fc, tarjeta["dia_pago"]).strftime("%d/%m/%Y")

        encabezado = (
            f"**{label}**{'  · (período actual)' if es_actual else ''}  —  "
            f"Total: **${grupo['total']:,.2f}**  ·  "
            f"Corte: {fc.strftime('%d/%m/%Y')}  ·  "
            f"Pago límite: {fp_str}"
        )
        with st.expander(encabezado, expanded=es_actual):
            if not grupo["transacciones"]:
                st.caption("Sin transacciones.")
            else:
                for t in sorted(grupo["transacciones"],
                                key=lambda x: x["fecha"], reverse=True):
                    _fila_transaccion(t)


def _fila_transaccion(t: dict):
    ca, cb, cc = st.columns([3, 1.5, 1])
    with ca:
        es_proyeccion = t.get("es_proyeccion", False)
        msi_tag = ""
        if t.get("meses_sin_intereses", 0) > 0:
            if es_proyeccion:
                num = t.get("mensualidad_num", "")
                total_meses = t.get("meses_sin_intereses", "")
                msi_tag = (
                    f" <span style='background:#E6F1FB;color:#0C447C;"
                    f"font-size:11px;padding:1px 6px;border-radius:4px'>"
                    f"MSI {num}/{total_meses} · proyectado</span>"
                )
            else:
                msi_tag = (
                    f" <span style='background:#EAF3DE;color:#27500A;"
                    f"font-size:11px;padding:1px 6px;border-radius:4px'>"
                    f"{t['meses_sin_intereses']}MSI</span>"
                )
        notas_html = (
            f"<br><span style='font-size:11px;color:#888'>📝 {t['notas']}</span>"
            if t.get("notas") and not es_proyeccion else ""
        )
        icono = "🔄" if es_proyeccion else t.get("categoria_icono", "📦")
        st.markdown(
            f"{icono} **{t['descripcion']}**"
            f"{msi_tag}{notas_html}",
            unsafe_allow_html=True,
        )
    with cb:
        if t.get("meses_sin_intereses", 0) > 0:
            st.markdown(
                f"<span style='color:#E24B4A;font-weight:500'>"
                f"-\${t['monto_por_mes']:,.2f}/mes</span>  \n"
                f"<span style='font-size:11px;color:gray'>"
                f"Total: ${t['monto']:,.2f}</span>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<span style='color:#E24B4A;font-weight:500'>"
                f"-${t['monto']:,.2f}</span>",
                unsafe_allow_html=True,
            )
    with cc:
        st.caption(t["fecha"])