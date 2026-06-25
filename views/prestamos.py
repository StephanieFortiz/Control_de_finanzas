"""
views/prestamos.py
"""
import streamlit as st
from datetime import date
from database.queries import (
    obtener_usuarios, obtener_prestamos, obtener_pagos_prestamo,
    crear_prestamo, registrar_pago_prestamo, eliminar_prestamo,
)
from utils.calculos import MESES_ES, _fecha_mas_n_meses


def render():
    st.title("🤝 Préstamos")
    usuarios = obtener_usuarios()
    if len(usuarios) < 2:
        st.warning("Primero crea los perfiles en ⚙️ Configuración.")
        return

    usuario_activo = st.session_state.get("usuario_activo", usuarios[0])

    tab_pend, tab_arch = st.tabs(["📋 Pendientes", "📦 Archivados"])
    with tab_pend:
        _tab_pendientes(usuario_activo)
    with tab_arch:
        _tab_archivados(usuario_activo)


# ── Pendientes ───────────────────────────────────────────────────────────────

def _tab_pendientes(usuario_activo: dict):
    uid = usuario_activo["id"]
    prestamos = obtener_prestamos(usuario_id=uid, estado="pendiente")

    yo_debo  = [p for p in prestamos if p["deudor_id"]   == uid]
    me_deben = [p for p in prestamos if p["acreedor_id"] == uid]

    c1, c2 = st.columns(2)
    c1.metric("Yo debo",
              f"${sum(p['monto_pendiente'] for p in yo_debo):,.2f}",
              f"{len(yo_debo)} préstamo(s)", delta_color="inverse")
    c2.metric("Me deben",
              f"${sum(p['monto_pendiente'] for p in me_deben):,.2f}",
              f"{len(me_deben)} préstamo(s)", delta_color="off")

    st.divider()

    filtro = st.radio(
        "Mostrar", ["Todos", "Lo que yo debo", "Lo que me deben"],
        horizontal=True, key="prest_filtro",
    )

    if filtro == "Todos":
        lista = [(p, "debo") for p in yo_debo] + [(p, "me_deben") for p in me_deben]
    elif filtro == "Lo que yo debo":
        lista = [(p, "debo") for p in yo_debo]
    else:
        lista = [(p, "me_deben") for p in me_deben]

    if not lista:
        st.info("No hay préstamos en esta categoría.")
        return

    for p, direccion in lista:
        _render_prestamo(p, usuario_activo, direccion, puede_abonar=True)


# ── Archivados ───────────────────────────────────────────────────────────────

def _tab_archivados(usuario_activo: dict):
    uid = usuario_activo["id"]
    todos = obtener_prestamos(usuario_id=uid)
    archivados = [p for p in todos if p["estado"] in ("pagado", "cancelado")]
    if not archivados:
        st.info("No hay préstamos archivados aún.")
        return
    for p in archivados:
        dir_p = "debo" if p["deudor_id"] == uid else "me_deben"
        _render_prestamo(p, usuario_activo, dir_p, puede_abonar=False)


# ── Tarjeta de préstamo ──────────────────────────────────────────────────────

def _contraparte(p: dict, uid: int) -> str:
    if p["acreedor_id"] == uid:
        return p.get("deudor_nombre") or p.get("nombre_externo") or "Externo"
    return p.get("acreedor_nombre") or p.get("nombre_externo") or "Externo"


def _render_prestamo(p: dict, usuario_activo: dict, direccion: str, puede_abonar: bool):
    uid = usuario_activo["id"]
    contraparte  = _contraparte(p, uid)
    monto_pagado = round(p["monto_original"] - p["monto_pendiente"], 2)
    progreso     = monto_pagado / p["monto_original"] if p["monto_original"] > 0 else 0

    cargo = p.get("tx_descripcion") or p.get("notas") or "—"
    tarjeta_str = ""
    if p.get("tx_tarjeta_nombre"):
        tarjeta_str = f"{p['tx_tarjeta_nombre']} ({p.get('tx_tarjeta_banco','')})"
    elif p.get("tx_cuenta_nombre"):
        tarjeta_str = p["tx_cuenta_nombre"]

    tipo_map = {"unico": "Pago único", "abonos": "Abonos libres",
                "msi": f"MSI · {p.get('meses_msi','?')} meses"}
    tipo_label = tipo_map.get(p.get("tipo_pago", "abonos"), "Abonos libres")
    dir_label  = "⬆️ Me deben" if direccion == "me_deben" else "⬇️ Yo debo"

    color_resta = "#E24B4A" if p["monto_pendiente"] > 0 else "#639922"
    color_bar   = "#639922" if progreso >= 1 else "#378ADD"

    # ── Fila de datos ──
    col_a, col_b, col_c, col_d, col_e, col_f, col_g = st.columns([3, 1.5, 1.2, 1.2, 1.2, 1.5, 1])

    with col_a:
        st.markdown(
            f"**{cargo}**  \n"
            f"<span style='font-size:12px;color:gray'>"
            f"{dir_label} · **{contraparte}** · {tipo_label}</span>",
            unsafe_allow_html=True,
        )
    with col_b:
        st.caption(f"📅 {p['fecha']}")
        if tarjeta_str:
            st.caption(f"💳 {tarjeta_str}")
    with col_c:
        st.markdown(f"**\${p['monto_original']:,.2f}**")
        st.caption("Total")
    with col_d:
        st.markdown(f"**\${monto_pagado:,.2f}**")
        st.caption("Pagado")
    with col_e:
        st.markdown(
            f"<span style='color:{color_resta};font-weight:600'>"
            f"\${p['monto_pendiente']:,.2f}</span>",
            unsafe_allow_html=True,
        )
        st.caption("Resta")
    with col_f:
        st.markdown(
            f"<div style='background:#eee;border-radius:4px;height:8px;margin-top:10px'>"
            f"<div style='background:{color_bar};width:{min(progreso,1)*100:.0f}%;"
            f"height:8px;border-radius:4px'></div></div>"
            f"<span style='font-size:11px;color:gray'>{progreso*100:.0f}% pagado</span>",
            unsafe_allow_html=True,
        )
    with col_g:
        if puede_abonar and p["estado"] == "pendiente":
            if st.button("💸 Abonar", key=f"abn_btn_{p['id']}"):
                st.session_state[f"abonando_{p['id']}"] = not st.session_state.get(f"abonando_{p['id']}", False)
                st.rerun()
        if monto_pagado == 0:
            if st.button("🗑", key=f"del_{p['id']}", help="Eliminar préstamo"):
                st.session_state[f"confirmando_del_{p['id']}"] = True

    # ── Detalle expandible ──
    pagos = obtener_pagos_prestamo(p["id"])
    with st.expander(f"Detalle · {len(pagos)} abono(s) registrado(s)"):
        if p.get("tipo_pago") == "msi" and p.get("meses_msi") and p.get("monto_por_mes"):
            _calendario_msi(p, pagos)
            st.divider()
        if pagos:
            st.markdown("**Abonos registrados:**")
            for pg in pagos:
                tipo_ico = {"pago": "", "adelantado": " 🔼", "condonado": " ✦"}.get(pg.get("tipo", "pago"), "")
                mes_lbl  = f" · mes {pg['numero_mes']}" if pg.get("numero_mes") else ""
                notas_lbl = f"  ·  📝 {pg['notas']}" if pg.get("notas") else ""
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;"
                    f"padding:4px 0;border-bottom:1px solid #f0f0f0;font-size:13px'>"
                    f"<span>{pg['fecha']}{mes_lbl}{tipo_ico}{notas_lbl}</span>"
                    f"<span style='color:#639922;font-weight:500'>\${pg['monto']:,.2f}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Sin abonos registrados aún.")

    # ── Formulario de abono ──
    if st.session_state.get(f"abonando_{p['id']}"):
        _form_abono(p, pagos)

    # ── Confirmación de borrado ──
    if st.session_state.get(f"confirmando_del_{p['id']}"):
        st.warning(f"¿Eliminar el préstamo de **\${p['monto_original']:,.2f}**? Esta acción no se puede deshacer.")
        cx, cy = st.columns(2)
        with cx:
            if st.button("Sí, eliminar", key=f"si_del_{p['id']}", type="primary"):
                eliminar_prestamo(p["id"])
                st.session_state.pop(f"confirmando_del_{p['id']}", None)
                st.rerun()
        with cy:
            if st.button("Cancelar", key=f"no_del_{p['id']}"):
                st.session_state.pop(f"confirmando_del_{p['id']}", None)
                st.rerun()

    st.divider()


# ── Calendario MSI ───────────────────────────────────────────────────────────

def _calendario_msi(p: dict, pagos: list):
    fecha_inicio  = date.fromisoformat(p["fecha"])
    meses         = p["meses_msi"]
    monto_mes     = p.get("monto_por_mes", 0.0)

    meses_pagados    = {pg["numero_mes"] for pg in pagos if pg.get("numero_mes")}
    meses_condonados = {pg["numero_mes"] for pg in pagos
                        if pg.get("numero_mes") and pg.get("tipo") == "condonado"}

    st.markdown("**Calendario de pagos MSI:**")
    cols_per_row = 4
    for row_start in range(0, meses, cols_per_row):
        row_nums = list(range(row_start + 1, min(row_start + cols_per_row + 1, meses + 1)))
        cols = st.columns(len(row_nums))
        for col, n in zip(cols, row_nums):
            fecha_n = _fecha_mas_n_meses(fecha_inicio, n - 1)
            lbl_fecha = fecha_n.strftime("%b %Y")
            with col:
                if n in meses_condonados:
                    bg, txt, sub = "#FFF3CD", "#856404", "✦ Condonado"
                elif n in meses_pagados:
                    bg, txt, sub = "#EAF3DE", "#27500A", "✓ Pagado"
                else:
                    bg, txt, sub = "#F8F7F4", "#E24B4A", f"${monto_mes:,.0f}"
                st.markdown(
                    f"<div style='text-align:center;background:{bg};"
                    f"border-radius:8px;padding:6px 4px;margin:2px'>"
                    f"<div style='font-size:11px;color:gray'>Mes {n}</div>"
                    f"<div style='font-size:12px;font-weight:500'>{lbl_fecha}</div>"
                    f"<div style='font-size:11px;color:{txt}'>{sub}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )


# ── Formulario de abono ──────────────────────────────────────────────────────

def _form_abono(p: dict, pagos_existentes: list):
    meses_msi     = p.get("meses_msi", 0)
    meses_pagados = {pg["numero_mes"] for pg in pagos_existentes if pg.get("numero_mes")}

    with st.form(f"form_abono_{p['id']}", clear_on_submit=True):
        st.markdown(f"**Registrar abono** — pendiente: \${p['monto_pendiente']:,.2f}")

        c1, c2 = st.columns(2)
        with c1:
            valor_default = float(p.get("monto_por_mes") or p["monto_pendiente"])
            monto_ab = st.number_input(
                "Monto ($)", min_value=0.01,
                value=valor_default,
                step=50.0, format="%.2f",
            )
        with c2:
            fecha_ab = st.date_input("Fecha", value=date.today())

        c3, c4 = st.columns(2)
        with c3:
            tipo_ab = st.selectbox(
                "Tipo de pago",
                ["Pago normal", "Pago adelantado", "Pago condonado"],
                help="'Condonado' cancela esa parte de la deuda sin cobro real",
            )
        with c4:
            numero_mes = None
            if meses_msi > 0:
                disponibles = [m for m in range(1, meses_msi + 1) if m not in meses_pagados]
                if disponibles:
                    numero_mes = st.selectbox("Mes MSI", disponibles)
                else:
                    st.caption("Todos los meses están cubiertos.")

        notas_ab = st.text_input("Notas (opcional)")

        c_ok, c_cancel = st.columns(2)
        with c_ok:
            guardar  = st.form_submit_button("Guardar abono", type="primary")
        with c_cancel:
            cancelar = st.form_submit_button("Cancelar")

    tipo_db_map = {"Pago normal": "pago", "Pago adelantado": "adelantado", "Pago condonado": "condonado"}

    if guardar:
        registrar_pago_prestamo(
            prestamo_id=p["id"],
            monto=monto_ab,
            fecha=str(fecha_ab),
            notas=notas_ab,
            tipo=tipo_db_map[tipo_ab],
            numero_mes=numero_mes,
        )
        st.session_state.pop(f"abonando_{p['id']}", None)
        st.success("✅ Abono registrado.")
        st.rerun()
    if cancelar:
        st.session_state.pop(f"abonando_{p['id']}", None)
        st.rerun()


# ── Crear préstamo desde transacción (llamado desde transacciones.py) ────────

def seccion_nuevo_prestamo(usuario_activo: dict, usuarios: list):
    """
    Panel para crear un préstamo ligado a la transacción recién guardada.
    Se muestra cuando st.session_state['prest_pendiente'] está definido.
    """
    info = st.session_state.get("prest_pendiente", {})
    if not info:
        return

    tx_monto = info["monto"]
    tx_desc  = info["descripcion"]
    tx_fecha = info["fecha"]
    tx_msi   = info.get("meses_sin_intereses", 0)
    tx_id    = info["tx_id"]

    otros = [u for u in usuarios if u["id"] != usuario_activo["id"]]

    st.success(f"✅ Transacción guardada: **{tx_desc}** — \${tx_monto:,.2f}")
    st.markdown("##### 💸 Configurar préstamo")

    # ¿Quién ayuda?
    c1, c2 = st.columns(2)
    with c1:
        tipo_persona = st.radio(
            "¿Con quién es el préstamo?",
            ["Mi pareja", "Persona externa"],
            horizontal=True, key="np_tipo_persona",
        )
    with c2:
        nombre_ext = None
        if tipo_persona == "Persona externa":
            nombre_ext = st.text_input("Nombre", key="np_nombre_ext",
                                       placeholder="Ej: Edgar, Mamá")

    # Dirección
    dir_prestamo = st.radio(
        "¿Qué pasó?",
        ["Me van a apoyar a pagar este gasto", "Yo pagué por alguien (me van a pagar)"],
        key="np_direccion",
    )

    # Monto del apoyo
    modo_monto = st.radio(
        "Monto del apoyo",
        ["Completo", "La mitad", "Porcentaje", "Monto fijo"],
        horizontal=True, key="np_modo_monto",
    )

    if modo_monto == "Completo":
        monto_prestamo = tx_monto
        st.caption(f"→ Monto total: **\${monto_prestamo:,.2f}**")
    elif modo_monto == "La mitad":
        monto_prestamo = round(tx_monto / 2, 2)
        st.caption(f"→ La mitad de \${tx_monto:,.2f} = **\${monto_prestamo:,.2f}**")
    elif modo_monto == "Porcentaje":
        pct = st.slider("Porcentaje (%)", 1, 100, 50, key="np_pct")
        monto_prestamo = round(tx_monto * pct / 100, 2)
        st.caption(f"→ {pct}% de \${tx_monto:,.2f} = **\${monto_prestamo:,.2f}**")
    else:
        monto_prestamo = st.number_input(
            "Monto del préstamo ($)", min_value=0.01,
            value=round(tx_monto / 2, 2),
            step=10.0, format="%.2f", key="np_monto_fijo",
        )

    # Forma de pago
    opciones_pago = ["Un solo pago", "Pagos parciales (abonos)"]
    if tx_msi > 0:
        opciones_pago.append(f"Conforme a MSI ({tx_msi} meses)")

    tipo_pago_lbl = st.radio(
        "¿Cómo van a pagar?",
        opciones_pago, horizontal=True, key="np_tipo_pago",
    )

    meses_msi = 0
    monto_por_mes = None
    tipo_pago_db  = "unico"

    if tipo_pago_lbl == "Un solo pago":
        tipo_pago_db = "unico"
    elif tipo_pago_lbl == "Pagos parciales (abonos)":
        tipo_pago_db = "abonos"
    else:
        tipo_pago_db  = "msi"
        meses_msi     = tx_msi
        monto_por_mes = round(monto_prestamo / meses_msi, 2)
        st.caption(f"→ {meses_msi} pagos automáticos de **\${monto_por_mes:,.2f}** cada uno")

    st.markdown("")
    c_crear, c_saltar = st.columns(2)
    with c_crear:
        if st.button("💾 Crear préstamo", type="primary", key="np_crear"):
            if tipo_persona == "Persona externa" and not (nombre_ext or "").strip():
                st.error("Escribe el nombre de la persona.")
                return

            otro = otros[0] if otros else None
            es_pareja = tipo_persona == "Mi pareja"
            nombre_e  = None if es_pareja else (nombre_ext or "").strip() or None

            if "Me van a apoyar" in dir_prestamo:
                acreedor_id = otro["id"] if (es_pareja and otro) else None
                deudor_id   = usuario_activo["id"]
            else:
                acreedor_id = usuario_activo["id"]
                deudor_id   = otro["id"] if (es_pareja and otro) else None

            crear_prestamo(
                monto=monto_prestamo,
                fecha=tx_fecha,
                acreedor_id=acreedor_id,
                deudor_id=deudor_id,
                nombre_externo=nombre_e,
                notas=tx_desc,
                transaccion_id=tx_id,
                tipo_pago=tipo_pago_db,
                meses_msi=meses_msi if meses_msi > 0 else None,
                monto_por_mes=monto_por_mes,
            )
            _limpiar_np()
            st.session_state.pop("prest_pendiente", None)
            st.success("✅ Préstamo creado.")
            st.rerun()

    with c_saltar:
        if st.button("Saltar (sin préstamo)", key="np_saltar"):
            _limpiar_np()
            st.session_state.pop("prest_pendiente", None)
            st.rerun()


def _limpiar_np():
    for k in ("np_tipo_persona", "np_nombre_ext", "np_direccion",
              "np_modo_monto", "np_pct", "np_monto_fijo", "np_tipo_pago"):
        st.session_state.pop(k, None)