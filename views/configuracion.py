"""
views/configuracion.py
----------------------
Configuración de perfiles, cuentas, tarjetas y categorías.
Todas las entidades son editables. Cuentas y tarjetas se pueden
desactivar sin borrar el historial. Categorías se pueden crear,
editar, y desactivar.
"""

import streamlit as st
from database.queries import (
    obtener_usuarios, crear_usuario,
    obtener_cuentas_todas, crear_cuenta, actualizar_cuenta,
    obtener_tarjetas_todas, crear_tarjeta, actualizar_tarjeta,
    obtener_categorias, crear_categoria, actualizar_categoria,
)

COLORES_PERFIL = {
    "Azul": "#378ADD", "Coral": "#D85A30", "Verde": "#639922",
    "Morado": "#7F77DD", "Rosa": "#D4537E", "Teal": "#1D9E75",
}
TIPOS_CUENTA = ["debito", "efectivo", "ahorro", "inversion"]

COLORES_CAT = {
    "Naranja":  "#D85A30", "Verde":    "#639922", "Azul":     "#378ADD",
    "Morado":   "#7F77DD", "Rosa":     "#D4537E", "Teal":     "#1D9E75",
    "Amarillo": "#EF9F27", "Rojo":     "#E24B4A", "Gris":     "#888780",
    "Verde osc":"#085041",
}


def _badge(texto: str, activo: bool) -> str:
    if activo:
        return f"<span style='background:#EAF3DE;color:#27500A;font-size:11px;padding:2px 7px;border-radius:4px'>{texto}</span>"
    return f"<span style='background:#F1EFE8;color:#5F5E5A;font-size:11px;padding:2px 7px;border-radius:4px'>Inactiva</span>"


def render():
    st.title("⚙️ Configuración")

    tab_perfiles, tab_cuentas, tab_tarjetas, tab_categorias = st.tabs(
        ["👤 Perfiles", "🏦 Cuentas", "💳 Tarjetas", "🏷️ Categorías"]
    )

    with tab_perfiles:
        _seccion_perfiles()
    with tab_cuentas:
        _seccion_cuentas()
    with tab_tarjetas:
        _seccion_tarjetas()
    with tab_categorias:
        _seccion_categorias()


# ── Perfiles ────────────────────────────────────────────────────────────

def _seccion_perfiles():
    st.markdown("#### Perfiles de usuario")
    usuarios = obtener_usuarios()

    if usuarios:
        cols = st.columns(len(usuarios))
        for col, u in zip(cols, usuarios):
            with col:
                st.markdown(
                    f"<div style='background:{u['color_perfil']}22;"
                    f"border-left:4px solid {u['color_perfil']};"
                    f"border-radius:8px;padding:0.8rem 1rem'>"
                    f"<strong style='color:{u['color_perfil']}'>{u['nombre']}</strong>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    if len(usuarios) < 2:
        st.info("Crea los dos perfiles para comenzar." if not usuarios
                else f"Perfil **{usuarios[0]['nombre']}** creado. Falta el segundo.")
        with st.form("form_usuario"):
            nombre = st.text_input("Nombre", placeholder="Ej: Carlos")
            color_label = st.selectbox("Color", list(COLORES_PERFIL.keys()))
            if st.form_submit_button("Crear perfil", type="primary"):
                if not nombre.strip():
                    st.error("El nombre no puede estar vacío.")
                elif nombre.strip() in [u["nombre"] for u in usuarios]:
                    st.error("Ya existe un perfil con ese nombre.")
                else:
                    crear_usuario(nombre.strip(), COLORES_PERFIL[color_label])
                    st.success(f"Perfil **{nombre}** creado.")
                    st.rerun()


# ── Cuentas ─────────────────────────────────────────────────────────────

def _seccion_cuentas():
    st.markdown("#### Cuentas bancarias")
    usuarios = obtener_usuarios()
    if len(usuarios) < 2:
        st.warning("Primero crea los dos perfiles.")
        return

    cuentas = obtener_cuentas_todas()

    for c in cuentas:
        editando = st.session_state.get(f"edit_cuenta_{c['id']}", False)
        activa   = bool(c["activa"])

        col_info, col_btn = st.columns([5, 1])
        with col_info:
            st.markdown(
                f"**{c['nombre']}** · {c['tipo'].capitalize()} · "
                f"Saldo inicial: ${c['saldo_inicial']:,.2f} "
                f"<span style='color:gray;font-size:13px'>({c['usuario_nombre']})</span> "
                f"{_badge('Activa', activa)}",
                unsafe_allow_html=True,
            )
        with col_btn:
            label = "✖️ Cerrar" if editando else "✏️ Editar"
            if st.button(label, key=f"btn_edit_cuenta_{c['id']}"):
                st.session_state[f"edit_cuenta_{c['id']}"] = not editando
                st.rerun()

        if editando:
            with st.form(f"form_edit_cuenta_{c['id']}"):
                st.markdown("**Editar cuenta**")
                col1, col2 = st.columns(2)
                with col1:
                    nombre_e  = st.text_input("Nombre", value=c["nombre"])
                    saldo_e   = st.number_input("Saldo inicial ($)",
                                               value=float(c["saldo_inicial"]),
                                               min_value=0.0, step=100.0)
                with col2:
                    tipo_e    = st.selectbox("Tipo", TIPOS_CUENTA,
                                            index=TIPOS_CUENTA.index(c["tipo"])
                                            if c["tipo"] in TIPOS_CUENTA else 0)
                    activa_e  = st.checkbox("Cuenta activa", value=activa)

                c1, c2 = st.columns(2)
                with c1:
                    guardar = st.form_submit_button("Guardar", type="primary")
                with c2:
                    cancelar = st.form_submit_button("Cancelar")

                if guardar:
                    if not nombre_e.strip():
                        st.error("El nombre no puede estar vacío.")
                    else:
                        actualizar_cuenta(c["id"], nombre_e.strip(),
                                         tipo_e, saldo_e, activa_e)
                        st.session_state.pop(f"edit_cuenta_{c['id']}", None)
                        st.success("✅ Cuenta actualizada.")
                        st.rerun()
                if cancelar:
                    st.session_state.pop(f"edit_cuenta_{c['id']}", None)
                    st.rerun()

    st.divider()
    with st.expander("➕ Agregar cuenta"):
        with st.form("form_cuenta_nueva"):
            usuario_sel = st.selectbox("Pertenece a", [u["nombre"] for u in usuarios])
            col1, col2 = st.columns(2)
            with col1:
                nombre_c = st.text_input("Nombre", placeholder="Ej: BBVA débito")
                saldo_c  = st.number_input("Saldo inicial ($)", min_value=0.0, step=100.0)
            with col2:
                tipo_c = st.selectbox("Tipo", TIPOS_CUENTA)
            if st.form_submit_button("Guardar cuenta"):
                if not nombre_c.strip():
                    st.error("El nombre no puede estar vacío.")
                else:
                    uid = next(u["id"] for u in usuarios if u["nombre"] == usuario_sel)
                    crear_cuenta(uid, nombre_c.strip(), tipo_c, saldo_c)
                    st.success(f"Cuenta **{nombre_c}** guardada.")
                    st.rerun()


# ── Tarjetas ─────────────────────────────────────────────────────────────

def _seccion_tarjetas():
    st.markdown("#### Tarjetas de crédito")
    usuarios = obtener_usuarios()
    if len(usuarios) < 2:
        st.warning("Primero crea los dos perfiles.")
        return

    tarjetas = obtener_tarjetas_todas()

    for t in tarjetas:
        editando = st.session_state.get(f"edit_tarjeta_{t['id']}", False)
        activa   = bool(t["activa"])

        col_info, col_btn = st.columns([5, 1])
        with col_info:
            st.markdown(
                f"**{t['nombre']}** · {t['banco']} · "
                f"Corte: día {t['dia_corte']} · Pago: día {t['dia_pago']} · "
                f"Límite: ${t['limite']:,.0f} "
                f"<span style='color:gray;font-size:13px'>({t['usuario_nombre']})</span> "
                f"{_badge('Activa', activa)}",
                unsafe_allow_html=True,
            )
        with col_btn:
            label = "✖️ Cerrar" if editando else "✏️ Editar"
            if st.button(label, key=f"btn_edit_tarjeta_{t['id']}"):
                st.session_state[f"edit_tarjeta_{t['id']}"] = not editando
                st.rerun()

        if editando:
            with st.form(f"form_edit_tarjeta_{t['id']}"):
                st.markdown("**Editar tarjeta**")
                col1, col2 = st.columns(2)
                with col1:
                    nombre_e    = st.text_input("Nombre", value=t["nombre"])
                    dia_corte_e = st.number_input("Día de corte",
                                                  min_value=1, max_value=31,
                                                  value=int(t["dia_corte"]))
                    limite_e    = st.number_input("Límite ($)",
                                                  min_value=0.0, step=1000.0,
                                                  value=float(t["limite"]))
                with col2:
                    banco_e     = st.text_input("Banco", value=t["banco"])
                    dia_pago_e  = st.number_input("Día límite de pago",
                                                  min_value=1, max_value=31,
                                                  value=int(t["dia_pago"]))
                    activa_e    = st.checkbox("Tarjeta activa", value=activa)

                c1, c2 = st.columns(2)
                with c1:
                    guardar = st.form_submit_button("Guardar", type="primary")
                with c2:
                    cancelar = st.form_submit_button("Cancelar")

                if guardar:
                    if not nombre_e.strip() or not banco_e.strip():
                        st.error("Nombre y banco son obligatorios.")
                    else:
                        actualizar_tarjeta(t["id"], nombre_e.strip(), banco_e.strip(),
                                          dia_corte_e, dia_pago_e, limite_e, activa_e)
                        st.session_state.pop(f"edit_tarjeta_{t['id']}", None)
                        st.success("✅ Tarjeta actualizada.")
                        st.rerun()
                if cancelar:
                    st.session_state.pop(f"edit_tarjeta_{t['id']}", None)
                    st.rerun()

    st.divider()
    with st.expander("➕ Agregar tarjeta"):
        with st.form("form_tarjeta_nueva"):
            usuario_t = st.selectbox("Pertenece a", [u["nombre"] for u in usuarios])
            col1, col2 = st.columns(2)
            with col1:
                nombre_t  = st.text_input("Nombre", placeholder="Ej: BBVA Azul")
                dia_corte = st.number_input("Día de corte", min_value=1, max_value=31, value=1)
                limite_t  = st.number_input("Límite ($)", min_value=0.0, step=1000.0)
            with col2:
                banco_t   = st.text_input("Banco", placeholder="Ej: BBVA")
                dia_pago  = st.number_input("Día límite de pago", min_value=1, max_value=31, value=20)
            st.caption("💡 El día de corte es cuando cierra tu estado de cuenta.")
            if st.form_submit_button("Guardar tarjeta"):
                if not nombre_t.strip() or not banco_t.strip():
                    st.error("Nombre y banco son obligatorios.")
                else:
                    uid = next(u["id"] for u in usuarios if u["nombre"] == usuario_t)
                    crear_tarjeta(uid, nombre_t.strip(), banco_t.strip(),
                                 dia_corte, dia_pago, limite_t)
                    st.success(f"Tarjeta **{nombre_t}** guardada.")
                    st.rerun()


# ── Categorías ───────────────────────────────────────────────────────────

def _seccion_categorias():
    st.markdown("#### Categorías")
    mostrar_inactivas = st.checkbox("Mostrar categorías desactivadas", key="cat_inactivas")
    cats = obtener_categorias(incluir_inactivas=mostrar_inactivas)

    for c in cats:
        editando = st.session_state.get(f"edit_cat_{c['id']}", False)
        activa   = bool(c.get("activa", 1))

        col_info, col_btn = st.columns([5, 1])
        with col_info:
            st.markdown(
                f"{c['icono']} **{c['nombre']}** · {c['tipo'].capitalize()} "
                f"{_badge('Activa', activa)}",
                unsafe_allow_html=True,
            )
        with col_btn:
            label = "✖️ Cerrar" if editando else "✏️ Editar"
            if st.button(label, key=f"btn_edit_cat_{c['id']}"):
                st.session_state[f"edit_cat_{c['id']}"] = not editando
                st.rerun()

        if editando:
            with st.form(f"form_edit_cat_{c['id']}"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    nombre_e = st.text_input("Nombre", value=c["nombre"])
                    icono_e  = st.text_input("Ícono (emoji)", value=c["icono"])
                with col2:
                    tipo_e = st.selectbox("Tipo", ["gasto", "ingreso"],
                                         index=0 if c["tipo"] == "gasto" else 1)
                    color_label = st.selectbox(
                        "Color", list(COLORES_CAT.keys()),
                        index=list(COLORES_CAT.values()).index(c["color"])
                              if c["color"] in COLORES_CAT.values() else 0
                    )
                with col3:
                    activa_e = st.checkbox("Categoría activa", value=activa)
                    st.markdown(
                        f"<div style='background:{COLORES_CAT[color_label]}22;"
                        f"border-left:3px solid {COLORES_CAT[color_label]};"
                        f"border-radius:6px;padding:8px;margin-top:4px'>"
                        f"{icono_e} {nombre_e or 'Vista previa'}</div>",
                        unsafe_allow_html=True,
                    )

                c1, c2 = st.columns(2)
                with c1:
                    guardar = st.form_submit_button("Guardar", type="primary")
                with c2:
                    cancelar = st.form_submit_button("Cancelar")

                if guardar:
                    if not nombre_e.strip():
                        st.error("El nombre no puede estar vacío.")
                    else:
                        actualizar_categoria(c["id"], nombre_e.strip(), icono_e.strip(),
                                           COLORES_CAT[color_label], tipo_e, activa_e)
                        st.session_state.pop(f"edit_cat_{c['id']}", None)
                        st.success("✅ Categoría actualizada.")
                        st.rerun()
                if cancelar:
                    st.session_state.pop(f"edit_cat_{c['id']}", None)
                    st.rerun()

    st.divider()
    with st.expander("➕ Crear categoría propia"):
        with st.form("form_cat_nueva"):
            col1, col2 = st.columns(2)
            with col1:
                nombre_n = st.text_input("Nombre", placeholder="Ej: Mascotas")
                icono_n  = st.text_input("Ícono (emoji)", value="📦")
            with col2:
                tipo_n   = st.selectbox("Tipo", ["gasto", "ingreso"])
                color_n  = st.selectbox("Color", list(COLORES_CAT.keys()))
            if st.form_submit_button("Crear categoría"):
                if not nombre_n.strip():
                    st.error("El nombre no puede estar vacío.")
                else:
                    crear_categoria(nombre_n.strip(), icono_n.strip(),
                                   COLORES_CAT[color_n], tipo_n)
                    st.success(f"Categoría **{nombre_n}** creada.")
                    st.rerun()