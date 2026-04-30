"""
app.py
------
Punto de entrada de la app. Configura la página, inicializa la base de
datos y maneja la navegación entre vistas mediante la barra lateral.
"""

import streamlit as st
from database.schema import crear_tablas, migrar_bd
from database.queries import obtener_usuarios

st.set_page_config(
    page_title="Finanzas",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS global mínimo — solo lo que Streamlit no cubre por defecto
st.markdown("""
<style>
    [data-testid="stSidebar"] { min-width: 220px; max-width: 220px; }
    .metric-card {
        background: #f8f7f4;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.5rem;
    }
    .stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# Inicializar la base de datos (se ejecuta solo la primera vez)
crear_tablas()
migrar_bd()

# ── Navegación ──────────────────────────────────────────────────────────
usuarios = obtener_usuarios()
hay_usuarios = len(usuarios) >= 2

with st.sidebar:
    st.markdown("## 💳 Finanzas")
    st.divider()

    if hay_usuarios:
        # Selector de usuario activo
        nombres = [u["nombre"] for u in usuarios]
        seleccion = st.selectbox("👤 Viendo como", nombres, key="usuario_activo_nombre")
        usuario_activo = next(u for u in usuarios if u["nombre"] == seleccion)
        st.session_state["usuario_activo"] = usuario_activo
        st.divider()

    opciones = {
        "📊 Dashboard":        "dashboard",
        "➕ Nueva transacción": "transacciones",
        "💳 Tarjetas":          "tarjetas",
        "🤝 Préstamos":         "prestamos",
        "⚖️  Liquidar cuentas": "liquidaciones",
        "⚙️  Configuración":    "configuracion",
    }

    pagina = st.radio(
        "Navegación",
        list(opciones.keys()),
        label_visibility="collapsed",
        key="pagina_actual"
    )
    vista = opciones[pagina]

    st.divider()
    st.caption("v0.1 — Fase 2")

# ── Renderizar vista seleccionada ────────────────────────────────────────
if not hay_usuarios and vista != "configuracion":
    st.info("👋 Para comenzar, configura los perfiles en **⚙️ Configuración**.")
    vista = "configuracion"

if vista == "dashboard":
    from views.dashboard import render
    render()
elif vista == "transacciones":
    from views.transacciones import render
    render()
elif vista == "tarjetas":
    from views.tarjetas import render
    render()
elif vista == "prestamos":
    from views.prestamos import render
    render()
elif vista == "liquidaciones":
    from views.liquidaciones import render
    render()
elif vista == "configuracion":
    from views.configuracion import render
    render()