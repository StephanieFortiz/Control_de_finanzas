"""
views/transacciones.py
"""
import streamlit as st
import calendar
from datetime import date
from database.queries import (
    obtener_usuarios, obtener_cuentas, obtener_tarjetas,
    obtener_categorias, crear_transaccion, actualizar_transaccion,
    obtener_transacciones, eliminar_transaccion, obtener_transaccion,
    obtener_tarjetas_todas, obtener_prestamos_por_tx_ids,
    obtener_pagos_prestamo, registrar_pago_prestamo,
)
from utils.calculos import MESES_ES, inyectar_proyecciones_msi


def _fmt(monto: float) -> str:
    return f"${monto:,.2f}"


def _form_transaccion(key: str, usuario_activo: dict, usuarios: list,
                      valores: dict = None) -> dict | None:
    """
    Formulario de transacción. Widgets condicionales fuera del st.form:
      - Medio de pago  → cuenta o tarjeta (+ MSI)
      - Tipo           → filtra categorías en tiempo real
    """
    v = valores or {}
    cuentas  = obtener_cuentas(usuario_activo["id"])
    tarjetas = obtener_tarjetas(usuario_activo["id"])

    # ── 1. Medio de pago ───────────────────────────────────────────────
    st.markdown("**Medio de pago**")
    medio = st.radio(
        "Pagar con", ["Cuenta / Efectivo", "Tarjeta de crédito"],
        horizontal=True, label_visibility="collapsed",
        key=f"{key}_medio",
        index=1 if (v.get("tarjeta_id") or not v) else 0,
    )
    cuenta_id = tarjeta_id = None
    meses_sin_intereses = v.get("meses_sin_intereses", 0)

    if medio == "Cuenta / Efectivo":
        if not cuentas:
            st.warning("No tienes cuentas. Agrégalas en ⚙️ Configuración.")
            return None
        opc_c = {f"{c['nombre']} ({c['tipo']})": c["id"] for c in cuentas}
        idx_c = list(opc_c.values()).index(v["cuenta_id"]) if v.get("cuenta_id") in opc_c.values() else 0
        cuenta_id = opc_c[st.selectbox("Cuenta", list(opc_c.keys()), index=idx_c, key=f"{key}_cuenta")]
    else:
        if not tarjetas:
            st.warning("No tienes tarjetas. Agrégalas en ⚙️ Configuración.")
            return None
        opc_t = {f"{t['nombre']} — {t['banco']}": t["id"] for t in tarjetas}
        idx_t = list(opc_t.values()).index(v["tarjeta_id"]) if v.get("tarjeta_id") in opc_t.values() else 0
        tarjeta_id = opc_t[st.selectbox("Tarjeta", list(opc_t.keys()), index=idx_t, key=f"{key}_tarjeta")]
        c1, c2 = st.columns([1, 2])
        with c1:
            usar_msi = st.checkbox("Meses sin intereses", value=meses_sin_intereses > 0, key=f"{key}_usar_msi")
        with c2:
            if usar_msi:
                opts_msi = [3, 6, 9, 12, 18, 20, 24]
                idx_msi  = opts_msi.index(meses_sin_intereses) if meses_sin_intereses in opts_msi else 0
                meses_sin_intereses = st.selectbox("Meses", opts_msi, index=idx_msi,
                                                   label_visibility="collapsed", key=f"{key}_msi")
            else:
                meses_sin_intereses = 0

    # ── 2. Tipo → filtra categorías ────────────────────────────────────
    tipo_opts = ["gasto", "ingreso"]
    tipo_idx  = tipo_opts.index(v["tipo"]) if v.get("tipo") in tipo_opts else 0
    tipo = st.selectbox("Tipo", tipo_opts, index=tipo_idx, key=f"{key}_tipo")

    cats        = obtener_categorias(tipo)
    cat_nombres = [f"{c['icono']} {c['nombre']}" for c in cats]
    cat_ids     = [c["id"] for c in cats]
    cat_idx     = cat_ids.index(v["categoria_id"]) if v.get("categoria_id") in cat_ids else 0
    cat_sel     = st.selectbox("Categoría", cat_nombres, index=cat_idx, key=f"{key}_cat")

    # ── 3. Campos dentro del form ──────────────────────────────────────
    with st.form(f"form_{key}", clear_on_submit=(valores is None)):
        c1, c2 = st.columns([2, 1])
        with c1:
            descripcion = st.text_input("Descripción", value=v.get("descripcion", ""),
                                        placeholder="Ej: Cena en restaurante")
        with c2:
            monto = st.number_input("Monto ($)", min_value=0.01, step=10.0,
                                    format="%.2f", value=float(v.get("monto", 0.01)),
                                    key=f"{key}_monto")
        fecha_val = date.fromisoformat(v["fecha"]) if v.get("fecha") else date.today()
        fecha = st.date_input("Fecha", value=fecha_val)
        notas = st.text_area("Notas (opcional)", value=v.get("notas", ""),
                             placeholder="Ej: Incluye propina",
                             max_chars=300, height=68)
        if meses_sin_intereses > 0:
            st.caption(f"💳 {meses_sin_intereses} meses sin intereses")
        enviado = st.form_submit_button(
            "Guardar cambios" if valores else "Guardar transacción", type="primary")

    if not enviado:
        return None
    if not descripcion.strip():
        st.error("La descripción no puede estar vacía.")
        return None

    return {
        "descripcion":         descripcion.strip(),
        "monto":               monto,
        "fecha":               str(fecha),
        "tipo":                tipo,
        "categoria_id":        cat_ids[cat_nombres.index(cat_sel)],
        "cuenta_id":           cuenta_id,
        "tarjeta_id":          tarjeta_id,
        "notas":               notas.strip(),
        "meses_sin_intereses": int(meses_sin_intereses),
    }


def _limpiar_keys(prefijo: str):
    for sufijo in ("_medio", "_cuenta", "_tarjeta", "_usar_msi", "_msi", "_tipo", "_cat"):
        st.session_state.pop(f"{prefijo}{sufijo}", None)


def render():
    st.title("📋 Transacciones")

    usuarios = obtener_usuarios()
    if len(usuarios) < 2:
        st.warning("Primero crea los dos perfiles en ⚙️ Configuración.")
        return
    usuario_activo = st.session_state.get("usuario_activo", usuarios[0])

    # ── Nueva transacción ──────────────────────────────────────────────
    # Si hay un préstamo pendiente de configurar, mostrar ese panel primero
    if "prest_pendiente" in st.session_state:
        from views.prestamos import seccion_nuevo_prestamo
        seccion_nuevo_prestamo(usuario_activo, usuarios)
        st.divider()
    else:
        st.markdown("#### Nueva transacción")
        es_prestamo = st.checkbox(
            "💸 Es préstamo o apoyo",
            key="nueva_es_prestamo",
            help="Marca si alguien va a pagarte parte de este gasto, o si tú pagaste por alguien",
        )
        res = _form_transaccion("nueva", usuario_activo, usuarios)
        if res:
            tx_id = crear_transaccion(usuario_id=usuario_activo["id"], **res)
            _limpiar_keys("nueva")
            if st.session_state.get("nueva_es_prestamo"):
                st.session_state["prest_pendiente"] = {
                    "tx_id":               tx_id,
                    "monto":               res["monto"],
                    "descripcion":         res["descripcion"],
                    "fecha":               res["fecha"],
                    "meses_sin_intereses": res["meses_sin_intereses"],
                }
                st.session_state.pop("nueva_es_prestamo", None)
            else:
                st.success(f"✅ Guardado: {res['descripcion']} — {_fmt(res['monto'])}")
            st.rerun()

    st.divider()

    # ── Historial ──────────────────────────────────────────────────────
    st.markdown("#### Historial")
    hoy = date.today()

    # Fila 1: usuario, mes, categoría
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        vista_u = st.selectbox("Usuario",
                               ["Todos"] + [u["nombre"] for u in usuarios],
                               key="hist_usuario")
    with col_f2:
        meses_hist = []
        for i in range(6):
            mes = hoy.month - i; anio = hoy.year
            while mes <= 0: mes += 12; anio -= 1
            meses_hist.append(date(anio, mes, 1))
        mes_labels = [f"{MESES_ES[m.month]} {m.year}" for m in meses_hist]
        mes_sel    = st.selectbox("Mes", mes_labels, key="hist_mes")
        mes_fecha  = meses_hist[mes_labels.index(mes_sel)]
    with col_f3:
        cats_hist = obtener_categorias()
        opc_cats  = {"Todas las categorías": None}
        opc_cats.update({f"{c['icono']} {c['nombre']}": c["id"] for c in cats_hist})
        cat_f = opc_cats[st.selectbox("Categoría", list(opc_cats.keys()), key="hist_cat")]

    # Fila 2: cuenta y tarjeta — dependen del usuario seleccionado
    uid_f = None if vista_u == "Todos" else next(u["id"] for u in usuarios if u["nombre"] == vista_u)

    cuentas_f  = obtener_cuentas(uid_f)
    tarjetas_f = obtener_tarjetas(uid_f)

    col_f4, col_f5 = st.columns(2)
    with col_f4:
        opc_cuentas = {"Todas las cuentas": None}
        opc_cuentas.update({f"{c['nombre']} ({c['tipo']})": c["id"] for c in cuentas_f})
        sel_cuenta = st.selectbox("Cuenta", list(opc_cuentas.keys()), key="hist_cuenta")
        cuenta_f   = opc_cuentas[sel_cuenta]
    with col_f5:
        opc_tarjetas = {"Todas las tarjetas": None}
        opc_tarjetas.update({f"{t['nombre']} — {t['banco']}": t["id"] for t in tarjetas_f})
        sel_tarjeta = st.selectbox("Tarjeta", list(opc_tarjetas.keys()), key="hist_tarjeta")
        tarjeta_f   = opc_tarjetas[sel_tarjeta]

    orden = st.selectbox(
        "Ordenar por",
        ["Más reciente agregada", "Fecha (más reciente)", "Fecha (más antigua)",
         "Monto (mayor primero)", "Monto (menor primero)",
         "Categoría A→Z", "Usuario A→Z"],
        key="hist_orden",
    )

    if cuenta_f and tarjeta_f:
        st.caption("ℹ️ Filtrando por cuenta — el filtro de tarjeta se ignora.")
        tarjeta_f = None
    ultimo = calendar.monthrange(mes_fecha.year, mes_fecha.month)[1]
    desde  = mes_fecha.strftime("%Y-%m-01")
    hasta  = f"{mes_fecha.year}-{mes_fecha.month:02d}-{ultimo:02d}"

    txs = obtener_transacciones(
        usuario_id=uid_f, desde=desde, hasta=hasta,
        cuenta_id=cuenta_f, tarjeta_id=tarjeta_f,
    )

    if cuenta_f is None:
        todas_tarjetas = obtener_tarjetas_todas(uid_f)
        tarjetas_map   = {t["id"]: t for t in todas_tarjetas}
        desde_amplio   = date(hoy.year - 3, 1, 1).strftime("%Y-%m-%d")
        txs_msi_base   = obtener_transacciones(
            usuario_id=uid_f, desde=desde_amplio, hasta=hasta,
            tipo="gasto", tarjeta_id=tarjeta_f,
        )
        txs_msi_base = [t for t in txs_msi_base if t.get("meses_sin_intereses", 0) > 0]
        if txs_msi_base:
            txs = inyectar_proyecciones_msi(
                txs, desde=desde, hasta=hasta,
                txs_msi_origen=txs_msi_base,
            )

    if cat_f is not None:
        txs = [t for t in txs if t.get("categoria_id") == cat_f]

    def _monto_ord(t):
        return (t.get("monto_por_mes") or t["monto"]) if t.get("meses_sin_intereses", 0) > 0 else t["monto"]

    if orden == "Más reciente agregada":
        txs = sorted(txs, key=lambda t: t.get("id", 0), reverse=True)
    elif orden == "Fecha (más reciente)":
        txs = sorted(txs, key=lambda t: (t["fecha"], t.get("id", 0)), reverse=True)
    elif orden == "Fecha (más antigua)":
        txs = sorted(txs, key=lambda t: (t["fecha"], t.get("id", 0)))
    elif orden == "Monto (mayor primero)":
        txs = sorted(txs, key=_monto_ord, reverse=True)
    elif orden == "Monto (menor primero)":
        txs = sorted(txs, key=_monto_ord)
    elif orden == "Categoría A→Z":
        txs = sorted(txs, key=lambda t: t.get("categoria_nombre") or "")
    elif orden == "Usuario A→Z":
        txs = sorted(txs, key=lambda t: t.get("usuario_nombre") or "")

    if not txs:
        st.caption("No hay transacciones con estos filtros.")
        return

    # Mapa de préstamos para mostrar botón inline de abono
    tx_ids_reales = [t["id"] for t in txs if not t.get("es_proyeccion")]
    prestamos_tx  = obtener_prestamos_por_tx_ids(tx_ids_reales)

    g_sum = sum(
        (t.get("monto_por_mes") or t["monto"]) if t.get("meses_sin_intereses", 0) > 0 else t["monto"]
        for t in txs if t["tipo"] == "gasto"
    )
    i_sum = sum(t["monto"] for t in txs if t["tipo"] == "ingreso")
    m1, m2, m3 = st.columns(3)
    m1.metric("Gastos", _fmt(g_sum))
    m2.metric("Ingresos", _fmt(i_sum))
    m3.metric("Balance", _fmt(i_sum - g_sum), delta_color="normal")
    st.markdown("")

    for t in txs:
        editando = st.session_state.get(f"editando_{t['id']}", False)
        col_a, col_b, col_c, col_acc = st.columns([3, 1.2, 1.0, 0.8])
        with col_a:
            tag_msi = (
                f" <span style='background:#EAF3DE;color:#27500A;font-size:11px;"
                f"padding:1px 6px;border-radius:4px'>"
                f"{t['meses_sin_intereses']}MSI · ${t['monto_por_mes']:,.2f}/mes</span>"
                if t.get("meses_sin_intereses", 0) > 0 else ""
            )
            nota_html = (
                f"<br><span style='font-size:12px;color:#888'>📝 {t['notas']}</span>"
                if t.get("notas") else ""
            )
            st.markdown(
                f"**{t['descripcion']}**{tag_msi}{nota_html}  \n"
                f"<span style='font-size:12px;color:gray'>"
                f"{t.get('categoria_icono','📦')} {t.get('categoria_nombre','—')} · "
                f"{t.get('tarjeta_nombre') or t.get('cuenta_nombre','—')} · "
                f"{t['usuario_nombre']}</span>",
                unsafe_allow_html=True,
            )
        with col_b:
            color = "#E24B4A" if t["tipo"] == "gasto" else "#639922"
            signo = "-" if t["tipo"] == "gasto" else "+"
            if t.get("meses_sin_intereses", 0) > 0 and not t.get("es_proyeccion"):
                st.markdown(
                    f"<span style='color:{color};font-weight:500'>"
                    f"{signo}\${t['monto_por_mes']:,.2f}/mes</span>  \n"
                    f"<span style='font-size:11px;color:gray'>Total: \${t['monto']:,.2f}</span>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f"<span style='color:{color};font-weight:500'>"
                            f"{signo}{_fmt(t['monto'])}</span>", unsafe_allow_html=True)
        with col_c:
            st.caption(t["fecha"])
        with col_acc:
            if t.get("es_proyeccion"):
                c_e, c_msi = st.columns(2)
                with c_msi:
                    st.caption("MSI")
                with c_e:
                    if st.button("✏️" if not editando else "✖️",
                                 key=f"edit_btn_{t['id']}_proj",
                                 help="Editar cargo original" if not editando else "Cancelar"):
                        st.session_state[f"editando_{t['id']}"] = not editando
                        st.rerun()
            else:
                c_e, c_d = st.columns(2)
                with c_e:
                    if st.button("✏️" if not editando else "✖️",
                                 key=f"edit_btn_{t['id']}",
                                 help="Editar" if not editando else "Cancelar"):
                        st.session_state[f"editando_{t['id']}"] = not editando
                        st.rerun()
                with c_d:
                    if st.button("🗑", key=f"del_{t['id']}", help="Eliminar"):
                        eliminar_transaccion(t["id"])
                        st.rerun()

        if editando:
            st.markdown(
                "<div style='border-left:3px solid #378ADD;padding:0.8rem 1rem 0.2rem;"
                "margin:4px 0 8px;background:var(--color-background-secondary);"
                "border-radius:0 8px 8px 0'>",
                unsafe_allow_html=True,
            )
            if t.get("es_proyeccion"):
                st.caption("ℹ️ Editando el cargo MSI original — los cambios afectan todas las mensualidades.")
            t_bd = obtener_transaccion(t["id"]) or t
            uid_tx     = t_bd.get("usuario_id", usuario_activo["id"])
            usuario_tx = next((u for u in usuarios if u["id"] == uid_tx), usuario_activo)
            cambios = _form_transaccion(f"edit_{t['id']}", usuario_tx, usuarios, valores=t_bd)
            st.markdown("</div>", unsafe_allow_html=True)
            if cambios:
                actualizar_transaccion(transaccion_id=t["id"], **cambios)
                st.session_state.pop(f"editando_{t['id']}", None)
                _limpiar_keys(f"edit_{t['id']}")
                st.success("✅ Transacción actualizada.")
                st.rerun()

        # ── Mini-form de abono si esta tx tiene un préstamo pendiente ──
        prest = prestamos_tx.get(t.get("id"))
        if prest:
            pendiente = prest["monto_pendiente"]
            abn_key   = f"abn_tx_{t['id']}"
            col_tag, col_btn = st.columns([4, 1])
            with col_tag:
                st.markdown(
                    f"<span style='background:#E6F1FB;color:#0C447C;font-size:11px;"
                    f"padding:2px 8px;border-radius:4px'>💸 Préstamo · resta \${pendiente:,.2f}</span>",
                    unsafe_allow_html=True,
                )
            with col_btn:
                if st.button("Abonar", key=f"btn_{abn_key}", help="Registrar abono"):
                    st.session_state[abn_key] = not st.session_state.get(abn_key, False)
                    st.rerun()
            if st.session_state.get(abn_key):
                _mini_form_abono(prest, abn_key)

        st.divider()


def _mini_form_abono(prest: dict, form_key: str):
    """Mini formulario inline de abono para la vista de transacciones."""
    pagos = obtener_pagos_prestamo(prest["id"])
    meses_msi     = prest.get("meses_msi", 0)
    meses_pagados = {pg["numero_mes"] for pg in pagos if pg.get("numero_mes")}

    with st.form(f"mini_abono_{prest['id']}", clear_on_submit=True):
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
            tipo_ab = st.selectbox(
                "Tipo", ["Pago normal", "Pago adelantado", "Pago condonado"]
            )

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