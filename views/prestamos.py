"""
views/prestamos.py
"""
import streamlit as st
from datetime import date
from database.queries import (
    obtener_usuarios, obtener_prestamos,
    crear_prestamo, registrar_pago_prestamo,
    obtener_transacciones_para_prestamo,
)
from utils.calculos import MESES_ES


def _badge_estado(estado: str) -> str:
    estilos = {
        "pendiente": "background:#FAEEDA;color:#633806",
        "pagado":    "background:#EAF3DE;color:#27500A",
        "cancelado": "background:#F1EFE8;color:#444441",
    }
    s = estilos.get(estado, estilos["pendiente"])
    return (f"<span style='{s};font-size:11px;"
            f"padding:2px 8px;border-radius:4px'>{estado.capitalize()}</span>")


def render():
    st.title("🤝 Préstamos")
    usuarios = obtener_usuarios()
    if len(usuarios) < 2:
        st.warning("Primero crea los perfiles en ⚙️ Configuración.")
        return

    usuario_activo = st.session_state.get("usuario_activo", usuarios[0])
    otro_usuario   = next(u for u in usuarios if u["id"] != usuario_activo["id"])

    tab_pend, tab_hist, tab_desde_gasto, tab_nuevo = st.tabs(
        ["📋 Pendientes", "📂 Historial", "🧾 Desde un gasto", "➕ Nuevo manual"]
    )
    with tab_pend:
        _render_pendientes(usuario_activo, otro_usuario)
    with tab_hist:
        _render_historial(usuario_activo)
    with tab_desde_gasto:
        _render_desde_gasto(usuario_activo, otro_usuario, usuarios)
    with tab_nuevo:
        _render_nuevo_manual(usuario_activo, otro_usuario, usuarios)


# ── Pendientes ───────────────────────────────────────────────────────────

def _render_pendientes(usuario_activo: dict, otro_usuario: dict):
    prestamos = obtener_prestamos(usuario_id=usuario_activo["id"], estado="pendiente")
    if not prestamos:
        st.info("No tienes préstamos pendientes.")
        return

    yo_debo  = [p for p in prestamos if p["deudor_id"]   == usuario_activo["id"]]
    me_deben = [p for p in prestamos if p["acreedor_id"] == usuario_activo["id"]]

    c1, c2 = st.columns(2)
    c1.metric("Yo debo",  f"${sum(p['monto_pendiente'] for p in yo_debo):,.2f}",
              delta=f"{len(yo_debo)} préstamo(s)", delta_color="inverse")
    c2.metric("Me deben", f"${sum(p['monto_pendiente'] for p in me_deben):,.2f}",
              delta=f"{len(me_deben)} préstamo(s)", delta_color="off")
    st.divider()

    for titulo, lista in [("Lo que yo debo", yo_debo), ("Lo que me deben", me_deben)]:
        if not lista:
            continue
        st.markdown(f"**{titulo}**")
        for p in lista:
            _render_tarjeta_prestamo(p, usuario_activo, puede_abonar=True)


# ── Historial ────────────────────────────────────────────────────────────

def _render_historial(usuario_activo: dict):
    todos    = obtener_prestamos(usuario_id=usuario_activo["id"])
    cerrados = [p for p in todos if p["estado"] in ("pagado", "cancelado")]
    if not cerrados:
        st.caption("Sin préstamos liquidados aún.")
        return
    for p in cerrados:
        _render_tarjeta_prestamo(p, usuario_activo, puede_abonar=False)


# ── Tarjeta de préstamo ──────────────────────────────────────────────────

def _render_tarjeta_prestamo(p: dict, usuario_activo: dict, puede_abonar: bool):
    progreso = 1 - (p["monto_pendiente"] / p["monto_original"]) if p["monto_original"] > 0 else 1

    if p["acreedor_id"] == usuario_activo["id"]:
        contraparte = p["deudor_nombre"] or p["nombre_externo"] or "Externo"
        direccion   = f"Le presté a {contraparte}"
    elif p["deudor_id"] == usuario_activo["id"]:
        contraparte = p["acreedor_nombre"] or p["nombre_externo"] or "Externo"
        direccion   = f"Me prestó {contraparte}"
    else:
        direccion = p["nombre_externo"] or "Externo"

    # Badge de fecha estimada si existe
    fecha_est_html = ""
    if p.get("fecha_estimada_pago"):
        fecha_est_html = (
            f" <span style='background:#E6F1FB;color:#0C447C;font-size:11px;"
            f"padding:2px 7px;border-radius:4px'>Pago est. {p['fecha_estimada_pago']}</span>"
        )

    # Badge de gasto vinculado
    gasto_html = ""
    if p.get("tx_descripcion"):
        gasto_html = (
            f"<br><span style='font-size:11px;color:#888'>🧾 Gasto: "
            f"{p['tx_descripcion']} · ${p['tx_monto']:,.2f}</span>"
        )

    col_a, col_b, col_c = st.columns([3, 2, 1])
    with col_a:
        st.markdown(
            f"**{p['notas'] or direccion}** {_badge_estado(p['estado'])}"
            f"{fecha_est_html}  \n"
            f"<span style='font-size:12px;color:gray'>{direccion} · {p['fecha']}</span>"
            f"{gasto_html}",
            unsafe_allow_html=True,
        )
    with col_b:
        color_b = "#639922" if progreso >= 1 else "#378ADD"
        st.markdown(
            f"Pendiente: \${p['monto_pendiente']:,.2f}  \n"
            f"<span style='font-size:11px;color:gray'>de ${p['monto_original']:,.2f}</span>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='background:#eee;border-radius:4px;height:5px;margin-top:4px'>"
            f"<div style='background:{color_b};width:{progreso*100:.1f}%;"
            f"height:5px;border-radius:4px'></div></div>",
            unsafe_allow_html=True,
        )
    with col_c:
        if puede_abonar and p["estado"] == "pendiente":
            if st.button("💸 Abonar", key=f"abonar_{p['id']}"):
                st.session_state[f"abonando_{p['id']}"] = True

    if st.session_state.get(f"abonando_{p['id']}"):
        with st.form(key=f"form_abono_{p['id']}"):
            st.markdown(f"**Registrar abono** — pendiente: ${p['monto_pendiente']:,.2f}")
            cm, cf = st.columns(2)
            with cm:
                monto_ab = st.number_input("Monto ($)", min_value=0.01,
                                           max_value=float(p["monto_pendiente"]),
                                           value=float(p["monto_pendiente"]),
                                           step=100.0, format="%.2f")
            with cf:
                fecha_ab = st.date_input("Fecha", value=date.today())
            notas_ab = st.text_input("Notas (opcional)", placeholder="Ej: Transferencia BBVA")
            c_ok, c_cancel = st.columns(2)
            with c_ok:
                guardar = st.form_submit_button("Guardar abono", type="primary")
            with c_cancel:
                cancelar = st.form_submit_button("Cancelar")
            if guardar:
                registrar_pago_prestamo(p["id"], monto_ab, str(fecha_ab), notas_ab)
                st.session_state.pop(f"abonando_{p['id']}", None)
                st.success("✅ Abono registrado.")
                st.rerun()
            if cancelar:
                st.session_state.pop(f"abonando_{p['id']}", None)
                st.rerun()

    st.divider()


# ── Desde un gasto ───────────────────────────────────────────────────────

def _render_desde_gasto(usuario_activo: dict, otro_usuario: dict, usuarios: list):
    st.markdown("#### Crear préstamo desde un gasto existente")
    st.caption(
        "Selecciona un gasto que alguien más te va a apoyar a pagar. "
        "Se creará un préstamo vinculado a ese gasto."
    )

    # ── Filtros fuera del form ─────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filtro_u = st.selectbox(
            "Gastos de", ["Todos"] + [u["nombre"] for u in usuarios],
            key="dg_usuario"
        )
    with col_f2:
        hoy = date.today()
        meses = []
        for i in range(6):
            mes = hoy.month - i; anio = hoy.year
            while mes <= 0: mes += 12; anio -= 1
            meses.append(date(anio, mes, 1))
        mes_labels = [f"{MESES_ES[m.month]} {m.year}" for m in meses]
        mes_sel   = st.selectbox("Mes", ["Todos los meses"] + mes_labels, key="dg_mes")
    with col_f3:
        st.markdown("<div style='margin-top:1.8rem'></div>", unsafe_allow_html=True)
        st.caption("Solo gastos sin préstamo asignado")

    uid_f = None if filtro_u == "Todos" else next(u["id"] for u in usuarios if u["nombre"] == filtro_u)
    desde_f = hasta_f = None
    if mes_sel != "Todos los meses":
        mes_fecha = meses[mes_labels.index(mes_sel)]
        import calendar as _cal
        ultimo = _cal.monthrange(mes_fecha.year, mes_fecha.month)[1]
        desde_f = mes_fecha.strftime("%Y-%m-01")
        hasta_f = f"{mes_fecha.year}-{mes_fecha.month:02d}-{ultimo:02d}"

    gastos = obtener_transacciones_para_prestamo(
        usuario_id=uid_f, desde=desde_f, hasta=hasta_f
    )

    if not gastos:
        st.info("No hay gastos disponibles con estos filtros (o todos ya tienen préstamo asignado).")
        return

    # ── Selector del gasto ─────────────────────────────────────────────
    opciones_gasto = {
        f"{g['fecha']}  ·  {g['descripcion']}  ·  ${g['monto']:,.2f}"
        f"  ({g['usuario_nombre']})": g["id"]
        for g in gastos
    }
    gasto_sel_label = st.selectbox("Selecciona el gasto", list(opciones_gasto.keys()),
                                   key="dg_gasto_sel")
    gasto_sel = next(g for g in gastos if g["id"] == opciones_gasto[gasto_sel_label])

    # Mostrar detalle del gasto seleccionado
    medio = gasto_sel.get("tarjeta_nombre") or gasto_sel.get("cuenta_nombre") or "—"
    if gasto_sel.get("tarjeta_banco"):
        medio = f"{gasto_sel['tarjeta_nombre']} ({gasto_sel['tarjeta_banco']})"
    st.markdown(
        f"<div style='background:var(--color-background-secondary);"
        f"border-left:3px solid #378ADD;border-radius:0 8px 8px 0;"
        f"padding:0.7rem 1rem;margin:4px 0 12px'>"
        f"🧾 <strong>{gasto_sel['descripcion']}</strong>  ·  "
        f"<strong>${gasto_sel['monto']:,.2f}</strong>  ·  {gasto_sel['fecha']}  ·  {medio}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Quién ayuda y cuánto ─────────────────────────────────────────────
    # Widgets condicionales FUERA del form
    col_q1, col_q2 = st.columns(2)
    with col_q1:
        tipo_persona = st.radio(
            "¿Quién te apoya?",
            ["Mi pareja", "Persona externa"],
            horizontal=True, key="dg_tipo_persona"
        )
    with col_q2:
        if tipo_persona == "Persona externa":
            nombre_ext = st.text_input("Nombre", placeholder="Ej: Mamá, Carlos",
                                       key="dg_nombre_ext")
        else:
            nombre_ext = None

    modo_monto = st.radio(
        "Monto del apoyo",
        ["La mitad", "Porcentaje", "Monto fijo"],
        horizontal=True, key="dg_modo_monto"
    )

    monto_gasto = float(gasto_sel["monto"])
    if modo_monto == "La mitad":
        monto_apoyo = round(monto_gasto / 2, 2)
        st.caption(f"→ {tipo_persona if tipo_persona == 'Mi pareja' else nombre_ext or 'Persona externa'}"
                   f" te debe **${monto_apoyo:,.2f}**")
    elif modo_monto == "Porcentaje":
        pct = st.slider("Porcentaje (%)", 1, 100, 50, 1, key="dg_pct")
        monto_apoyo = round(monto_gasto * pct / 100, 2)
        st.caption(f"→ {pct}% de \${monto_gasto:,.2f} = **${monto_apoyo:,.2f}**")
    else:
        monto_apoyo = st.number_input(
            "Monto que te deben ($)", min_value=0.01,
            max_value=float(monto_gasto),
            value=round(monto_gasto / 2, 2),
            step=10.0, format="%.2f", key="dg_monto_fijo"
        )

    tipo_pago = st.radio(
        "¿Cómo te van a pagar?",
        ["Un solo pago", "Pagos parciales (abonos)"],
        horizontal=True, key="dg_tipo_pago"
    )

    # ── Resto en form ─────────────────────────────────────────────────
    fecha_prestamo = date.fromisoformat(gasto_sel["fecha"])

    with st.form("form_desde_gasto", clear_on_submit=True):
        st.caption(f"📅 Fecha del préstamo: **{gasto_sel['fecha']}** (igual que el gasto)")
        fecha_est = None
        if tipo_pago == "Un solo pago":
            fecha_est = st.date_input(
                "Fecha estimada de pago",
                value=date.today().replace(month=date.today().month % 12 + 1)
                if date.today().month < 12
                else date.today().replace(year=date.today().year + 1, month=1),
            )
        else:
            st.caption("Los abonos se registran desde la tab Pendientes.")

        notas_p = st.text_input(
            "Notas (opcional)",
            value=f"Apoyo en: {gasto_sel['descripcion']}",
            placeholder="Descripción del préstamo"
        )

        enviado = st.form_submit_button("Crear préstamo", type="primary")

    if enviado:
        if tipo_persona == "Persona externa" and not (nombre_ext or "").strip():
            st.error("Escribe el nombre de la persona externa.")
            return

        acreedor_id = usuario_activo["id"]
        deudor_id   = otro_usuario["id"] if tipo_persona == "Mi pareja" else None
        nombre_externo = (nombre_ext or "").strip() or None

        crear_prestamo(
            monto=float(monto_apoyo),
            fecha=str(fecha_prestamo),
            acreedor_id=acreedor_id,
            deudor_id=deudor_id,
            nombre_externo=nombre_externo,
            notas=notas_p.strip(),
            transaccion_id=gasto_sel["id"],
            fecha_estimada_pago=str(fecha_est) if fecha_est else None,
        )
        for k in ("dg_usuario", "dg_mes", "dg_gasto_sel", "dg_tipo_persona",
                  "dg_nombre_ext", "dg_modo_monto", "dg_pct", "dg_monto_fijo",
                  "dg_tipo_pago"):
            st.session_state.pop(k, None)
        st.success(
            f"✅ Préstamo creado: "
            f"{'Mi pareja' if tipo_persona == 'Mi pareja' else nombre_ext} "
            f"te debe ${monto_apoyo:,.2f} por {gasto_sel['descripcion']}."
        )
        st.rerun()


# ── Nuevo manual ──────────────────────────────────────────────────────────

def _render_nuevo_manual(usuario_activo: dict, otro_usuario: dict, usuarios: list):
    st.markdown("#### Registrar préstamo manual")
    st.caption("Para préstamos que no están vinculados a un gasto específico.")

    tipo_prestamo = st.radio(
        "Tipo de préstamo",
        ["Entre nosotros", "Con persona externa"],
        horizontal=True, label_visibility="collapsed",
        key="nm_tipo",
    )

    acreedor_id = deudor_id = nombre_externo = None
    valido = True

    if tipo_prestamo == "Entre nosotros":
        opts = [
            f"{usuario_activo['nombre']} le prestó a {otro_usuario['nombre']}",
            f"{otro_usuario['nombre']} le prestó a {usuario_activo['nombre']}",
        ]
        direccion = st.radio("Dirección", opts,
                             label_visibility="collapsed", key="nm_dir")
        if direccion.startswith(usuario_activo["nombre"]):
            acreedor_id, deudor_id = usuario_activo["id"], otro_usuario["id"]
        else:
            acreedor_id, deudor_id = otro_usuario["id"], usuario_activo["id"]
    else:
        c1, c2 = st.columns(2)
        with c1:
            nombre_externo = st.text_input(
                "Nombre de la persona",
                placeholder="Ej: Mamá, Carlos Vecino",
                key="nm_externo",
            )
        with c2:
            rol = st.selectbox(
                f"Rol de {usuario_activo['nombre']}",
                ["Yo presté (soy acreedor)", "Me prestaron (soy deudor)"],
                key="nm_rol",
            )
        if not (nombre_externo or "").strip():
            valido = False
        acreedor_id = usuario_activo["id"] if "acreedor" in rol else None
        deudor_id   = None if "acreedor" in rol else usuario_activo["id"]

    tipo_pago = st.radio(
        "¿Cómo se va a pagar?",
        ["Un solo pago", "Pagos parciales (abonos)"],
        horizontal=True, key="nm_tipo_pago"
    )

    with st.form("form_nuevo_manual", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            monto = st.number_input("Monto ($)", min_value=0.01, step=100.0, format="%.2f")
        with c2:
            fecha = st.date_input("Fecha", value=date.today())

        fecha_est = None
        if tipo_pago == "Un solo pago":
            fecha_est = st.date_input(
                "Fecha estimada de pago",
                value=date.today().replace(month=date.today().month % 12 + 1)
                if date.today().month < 12
                else date.today().replace(year=date.today().year + 1, month=1),
            )
        else:
            st.caption("Los abonos se registran desde la tab Pendientes.")

        notas = st.text_input("Descripción / motivo",
                              placeholder="Ej: Para renta de enero")
        enviado = st.form_submit_button("Guardar préstamo", type="primary")

    if enviado:
        if not valido:
            st.error("Escribe el nombre de la persona.")
        elif monto <= 0:
            st.error("El monto debe ser mayor a cero.")
        else:
            crear_prestamo(
                monto=monto, fecha=str(fecha),
                acreedor_id=acreedor_id, deudor_id=deudor_id,
                nombre_externo=(nombre_externo or "").strip() or None,
                notas=notas.strip(),
                fecha_estimada_pago=str(fecha_est) if fecha_est else None,
            )
            for k in ("nm_tipo", "nm_dir", "nm_externo", "nm_rol", "nm_tipo_pago"):
                st.session_state.pop(k, None)
            st.success(f"✅ Préstamo de ${monto:,.2f} registrado.")
            st.rerun()