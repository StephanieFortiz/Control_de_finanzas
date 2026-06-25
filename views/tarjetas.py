"""
views/tarjetas.py
-----------------
Vista del motor de tarjetas de crédito. Muestra:
  - Resumen por tarjeta: total del período, días para pago, alerta
  - Desglose de transacciones agrupadas por estado de cuenta
"""

import streamlit as st
from datetime import date
from database.queries import (obtener_usuarios, obtener_tarjetas, obtener_transacciones,
                              obtener_ajustes_msi, guardar_ajuste_msi,
                              obtener_prestamos_por_tx_ids, obtener_pagos_prestamo,
                              registrar_pago_prestamo)
from utils.calculos import estado_tarjeta, agrupar_por_periodo, calcular_fecha_pago


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

    msi_ids      = list({t["id"] for t in txs_tarjeta if t.get("meses_sin_intereses", 0) > 0})
    ajustes      = obtener_ajustes_msi(msi_ids)
    tx_ids_real  = [t["id"] for t in txs_tarjeta]
    prestamos_tx = obtener_prestamos_por_tx_ids(tx_ids_real)

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
            _fila_transaccion(t, ajustes, prestamos_tx, mostrar_editar=False)

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
                    _fila_transaccion(t, ajustes, prestamos_tx)


def _fila_transaccion(t: dict, ajustes: dict = None, prestamos_tx: dict = None, mostrar_editar: bool = True):
    es_proyeccion = t.get("es_proyeccion", False)

    # Aplicar ajuste de monto si existe para esta mensualidad
    if ajustes and es_proyeccion:
        key = (t.get("id"), t.get("mensualidad_num"))
        if key in ajustes:
            t = {**t, "monto": ajustes[key], "monto_por_mes": ajustes[key]}

    ca, cb, cc, cd = st.columns([2.8, 1.5, 1, 0.4])
    with ca:
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
            if t.get("notas") else ""
        )
        icono = "🔄" if es_proyeccion else t.get("categoria_icono", "📦")
        st.markdown(
            f"{icono} **{t['descripcion']}**"
            f"{msi_tag}{notas_html}",
            unsafe_allow_html=True,
        )
    with cb:
        if t.get("meses_sin_intereses", 0) > 0:
            monto_total = t.get("monto_original", t["monto"])
            st.markdown(
                f"<span style='color:#E24B4A;font-weight:500'>"
                f"-\${t['monto_por_mes']:,.2f}/mes</span>  \n"
                f"<span style='font-size:11px;color:gray'>"
                f"Total: ${monto_total:,.2f}</span>",
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
    with cd:
        if es_proyeccion and mostrar_editar:
            edit_key = f"aj_{t.get('id')}_{t.get('mensualidad_num')}"
            editando = st.session_state.get(edit_key, False)
            if st.button("✏️" if not editando else "✖️", key=f"btn_{edit_key}",
                         help="Ajustar monto" if not editando else "Cancelar"):
                st.session_state[edit_key] = not editando
                st.rerun()

    if es_proyeccion and mostrar_editar:
        edit_key = f"aj_{t.get('id')}_{t.get('mensualidad_num')}"
        if st.session_state.get(edit_key, False):
            with st.form(f"form_{edit_key}"):
                num = t.get("mensualidad_num", "")
                total_meses = t.get("meses_sin_intereses", "")
                st.caption(f"Ajuste de monto — mensualidad {num}/{total_meses}")
                nuevo_monto = st.number_input(
                    "Monto", value=float(t["monto_por_mes"]),
                    min_value=0.01, step=0.01, format="%.2f",
                    label_visibility="collapsed",
                )
                if st.form_submit_button("Guardar ajuste", type="primary"):
                    guardar_ajuste_msi(t["id"], t["mensualidad_num"], nuevo_monto)
                    st.session_state[edit_key] = False
                    st.rerun()

    # ── Badge de préstamo + mini-form de abono ──────────────────────────
    tid = t.get("id")
    prest = (prestamos_tx or {}).get(tid) if not es_proyeccion else None
    if prest:
        pendiente = prest["monto_pendiente"]
        abn_key   = f"abn_tar_{tid}"
        col_tag, col_btn = st.columns([4, 1])
        with col_tag:
            st.markdown(
                f"<span style='background:#E6F1FB;color:#0C447C;font-size:11px;"
                f"padding:2px 8px;border-radius:4px'>💸 Préstamo · resta \${pendiente:,.2f}</span>",
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("Abonar", key=f"btn_{abn_key}"):
                st.session_state[abn_key] = not st.session_state.get(abn_key, False)
                st.rerun()
        if st.session_state.get(abn_key):
            _mini_form_abono_tar(prest, abn_key)


def _mini_form_abono_tar(prest: dict, form_key: str):
    pagos = obtener_pagos_prestamo(prest["id"])
    meses_msi     = prest.get("meses_msi", 0)
    meses_pagados = {pg["numero_mes"] for pg in pagos if pg.get("numero_mes")}

    with st.form(f"mini_abono_tar_{prest['id']}", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            monto_ab = st.number_input(
                "Monto ($)", min_value=0.01,
                value=float(prest.get("monto_por_mes") or prest["monto_pendiente"]),
                step=50.0, format="%.2f",
            )
        with c2:
            fecha_ab = st.date_input("Fecha", value=date.today())
        with c3:
            tipo_ab = st.selectbox("Tipo", ["Pago normal", "Pago adelantado", "Pago condonado"])
        numero_mes = None
        if meses_msi > 0:
            disponibles = [m for m in range(1, meses_msi + 1) if m not in meses_pagados]
            if disponibles:
                numero_mes = st.selectbox("Mes MSI", disponibles)
        notas_ab = st.text_input("Notas (opcional)")
        c_ok, c_cancel = st.columns(2)
        with c_ok:
            guardar  = st.form_submit_button("Guardar abono", type="primary")
        with c_cancel:
            cancelar = st.form_submit_button("Cancelar")

    tipo_db = {"Pago normal": "pago", "Pago adelantado": "adelantado", "Pago condonado": "condonado"}[tipo_ab]
    if guardar:
        registrar_pago_prestamo(
            prestamo_id=prest["id"], monto=monto_ab,
            fecha=str(fecha_ab), notas=notas_ab,
            tipo=tipo_db, numero_mes=numero_mes,
        )
        st.session_state.pop(form_key, None)
        st.success("✅ Abono registrado.")
        st.rerun()
    if cancelar:
        st.session_state.pop(form_key, None)
        st.rerun()