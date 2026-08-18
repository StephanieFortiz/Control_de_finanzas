# Implementación de esta semana: caché + widget de captura rápida

Este documento resume cómo poner en marcha las dos mejoras hechas al proyecto:

1. **Caché en Streamlit** (`database/queries.py`, `app.py`) — ya está en el código, no requiere configuración adicional. Reduce el tiempo de carga porque deja de golpear la base de datos de Supabase en cada rerun.
2. **Widget web de captura rápida** (`widget/index.html`) — una página HTML independiente (no depende de Streamlit) para que tu novio registre un gasto desde el celular en ~10 segundos, sin abrir la app completa.

---

## Paso 1: Obtener credenciales de Supabase

1. Entra a [supabase.com](https://supabase.com) → tu proyecto de Finanzas.
2. Ve a **Settings → API**.
3. Copia dos valores:
   - **Project URL** → algo como `https://xxxxxxxxxxxx.supabase.co`
   - **anon public key** (la clave pública, NO la `service_role`) → un string largo tipo JWT.

⚠️ La `anon key` es segura de exponer en un HTML público **siempre y cuando** tengas RLS (Row Level Security) configurado correctamente — ver Paso 3. Nunca uses la `service_role key` en el widget.

---

## Paso 2: Configurar el HTML (reemplazar 3 variables)

Abre [widget/index.html](widget/index.html) y busca el bloque `Configuración de Supabase` dentro del `<script>`:

```js
const SUPABASE_URL = 'YOUR_SUPABASE_URL';
const SUPABASE_ANON_KEY = 'YOUR_SUPABASE_ANON_KEY';
const USUARIO_ID_DEFECTO = 1;
```

Reemplaza:
- `YOUR_SUPABASE_URL` → tu Project URL del Paso 1.
- `YOUR_SUPABASE_ANON_KEY` → tu anon public key del Paso 1.
- `USUARIO_ID_DEFECTO` → el `id` de tu novio en la tabla `usuario`. Para verlo, en Supabase ve a **Table Editor → usuario** y busca su fila.

Guarda el archivo.

---

## Paso 3: Habilitar RLS en Supabase (SQL para policies)

Por defecto, si RLS está desactivado, cualquiera con la URL del proyecto puede leer/escribir todo. Con RLS activado, defines exactamente qué puede hacer la `anon key`.

Ve a Supabase → **SQL Editor** y ejecuta:

```sql
-- Activar RLS en las tablas que usa el widget
ALTER TABLE categoria ENABLE ROW LEVEL SECURITY;
ALTER TABLE cuenta ENABLE ROW LEVEL SECURITY;
ALTER TABLE tarjeta_credito ENABLE ROW LEVEL SECURITY;
ALTER TABLE transaccion ENABLE ROW LEVEL SECURITY;

-- Permitir LECTURA pública de categorías, cuentas y tarjetas
-- (el widget las necesita para llenar los selects)
CREATE POLICY "lectura_publica_categoria"
  ON categoria FOR SELECT
  USING (true);

CREATE POLICY "lectura_publica_cuenta"
  ON cuenta FOR SELECT
  USING (true);

CREATE POLICY "lectura_publica_tarjeta"
  ON tarjeta_credito FOR SELECT
  USING (true);

-- Permitir SOLO INSERT público en transaccion (no update/delete/select general)
CREATE POLICY "insertar_gasto_publico"
  ON transaccion FOR INSERT
  WITH CHECK (tipo = 'gasto');

-- Permitir que test_widget.py verifique y borre ÚNICAMENTE sus propias filas
-- de prueba (marcadas con descripcion = '[TEST_WIDGET]'). No expone el resto
-- del historial de gastos a la anon key.
CREATE POLICY "test_widget_select"
  ON transaccion FOR SELECT
  USING (descripcion = '[TEST_WIDGET]');

CREATE POLICY "test_widget_delete"
  ON transaccion FOR DELETE
  USING (descripcion = '[TEST_WIDGET]');
```

Con esto, el widget puede leer catálogos e insertar gastos, pero **no puede leer, editar ni borrar** transacciones reales existentes — eso lo sigue haciendo solo la app de Streamlit (que se conecta directo por Postgres con las credenciales de `secrets.toml`, sin pasar por RLS). Las dos últimas policies son solo para que `test_widget.py` pueda auto-limpiarse; no dan acceso a datos reales porque exigen esa descripción exacta.

Si más adelante quieres restringir aún más (por ejemplo, que solo pueda insertar transacciones del usuario de tu novio), cambia el `WITH CHECK`:

```sql
WITH CHECK (tipo = 'gasto' AND usuario_id = 2)  -- reemplaza 2 por su id real
```

---

## Paso 4: Desplegar en Vercel o GitHub Pages

El widget es un solo archivo HTML estático — no necesita build ni backend propio.

### Opción A — Vercel (recomendado, más rápido)

1. Instala la CLI si no la tienes: `npm i -g vercel`
2. Desde la carpeta `widget/`, corre: `vercel --prod`
3. Sigue las instrucciones (crea cuenta gratis si no tienes). Vercel te da una URL tipo `https://tu-widget.vercel.app`.
4. Abre esa URL en el celular de tu novio y agrégala a la pantalla de inicio ("Agregar a pantalla de inicio") para que se sienta como una app.

### Opción B — GitHub Pages (gratis, sin CLI)

1. Sube la carpeta `widget/` a un repositorio de GitHub (puede ser este mismo repo).
2. Ve a **Settings → Pages** del repo.
3. En "Source", selecciona la rama y la carpeta `/widget` (o `/root` si mueves el HTML a la raíz de una rama dedicada).
4. GitHub te da una URL tipo `https://tuusuario.github.io/Finanzas/` (sirve `index.html` en la raíz automáticamente).

En ambos casos, la URL es pública — cualquiera con el link puede abrir el formulario. La seguridad real la da RLS (Paso 3), no la URL en sí.

---

## Paso 5: Testing (tu novio usa el widget, verifica que aparezca en el Dashboard)

1. Antes de desplegar, corre `python test_widget.py` (requiere `pip install requests`, ya agregado a `requirements.txt`) para confirmar que la conexión y el INSERT funcionan. Te pedirá `SUPABASE_URL` y `SUPABASE_ANON_KEY` (o defínelas como variables de entorno antes de correrlo).
2. Abre la URL desplegada en el celular de tu novio.
3. Que registre un gasto de prueba (ej. "Café — $50").
4. Verifica en la app de Streamlit: abre **Dashboard** o **Transacciones** y confirma que el gasto aparece.
   - Si no aparece de inmediato, recuerda que `obtener_transacciones` tiene caché de 5 minutos (`ttl=300`) — espera ese tiempo o reinicia la app (`R` en Streamlit) para forzar refresco.
5. Borra la transacción de prueba desde la app si no era un gasto real.

---

## Velocidades esperadas

| | Antes | Después |
|---|---|---|
| Carga inicial de la app (`app.py`) | 8–10 seg | 2–3 seg |
| Cambiar de vista (Dashboard ↔ Transacciones) | 3–5 seg | Casi instantáneo (datos en caché) |
| Registrar un gasto (tu novio, desde el widget) | No existía — usaba la app completa | ~10 seg desde que abre el link hasta guardar |

La primera carga después de que expire el caché (o tras crear/editar/borrar algo) sigue tardando lo normal, porque se vuelve a consultar Supabase — es esperado, es lo que garantiza que los datos no queden obsoletos.
