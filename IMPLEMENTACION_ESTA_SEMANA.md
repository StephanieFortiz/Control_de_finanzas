# Implementación de esta semana: caché + widget de captura rápida

Este documento resume cómo poner en marcha las tres mejoras hechas al proyecto:

1. **Caché en Streamlit** (`database/queries.py`, `app.py`) — ya está en el código, no requiere configuración adicional. Reduce el tiempo de carga porque deja de golpear la base de datos de Supabase en cada rerun.
2. **Widget web de captura rápida** (`widget/index.html`) — una página HTML independiente (no depende de Streamlit) para registrar un gasto (o un préstamo/apoyo ligado) desde el celular en segundos, sin abrir la app completa.
3. **Backend serverless** (`widget/api/data.js` y `widget/api/prestamo.js`) — funciones en Vercel que conectan directo a Postgres (igual que la app de Streamlit), usando el **connection pooler** de Supabase. El widget ya no llama a la REST API pública de Supabase — eso evita el incidente que tuvieron con su API Gateway (`PGRST002` / 503), porque esa capa ya no está en el camino.

---

## Paso 1: Configurar las variables de entorno en Vercel

El backend necesita credenciales de Postgres — como variables de entorno de Vercel, **nunca en el HTML ni en git**. A diferencia de la `anon key` de antes, esta sí es la contraseña real de tu base de datos.

⚠️ **Usa las credenciales del connection pooler, no las de `.streamlit/secrets.toml`.** El host directo (`db.xxx.supabase.co`) solo resuelve por IPv6, y Vercel no tiene salida IPv6 — por eso el primer intento dio `ENOTFOUND`. El pooler sí es compatible con IPv4. Sácalo de Supabase → botón **Connect** → pestaña **Transaction pooler**.

Desde la carpeta `widget/`:

```powershell
vercel env add PGHOST production
vercel env add PGPORT production
vercel env add PGDATABASE production
vercel env add PGUSER production
vercel env add PGPASSWORD production
```

Cada comando te va a pedir el valor:

| Variable | Valor |
|---|---|
| `PGHOST` | `aws-1-us-east-1.pooler.supabase.com` |
| `PGPORT` | `6543` |
| `PGDATABASE` | `postgres` |
| `PGUSER` | `postgres.mehwuyolvfjvmlobcsms` |
| `PGPASSWORD` | tu contraseña de Postgres (la misma de `.streamlit/secrets.toml`, sin comillas) |

Alternativa sin CLI: Vercel → tu proyecto `fin-oscap` → **Settings → Environment Variables** → agrégalas ahí una por una (Environment: *Production*).

---

## Paso 2: (Opcional) Ajustar el usuario por defecto del widget

Abre [widget/index.html](widget/index.html) y busca, dentro del `<script>`:

```js
const USUARIO_ID_DEFECTO = 1;
```

Es el `id` (en la tabla `usuario`) que queda preseleccionado al abrir el formulario — el widget igual trae un selector de "Usuario" por si hace falta cambiarlo ahí mismo. Para ver los ids, en Supabase ve a **Table Editor → usuario**. Si ya está en el valor correcto, no necesitas tocar nada.

---

## Qué campos tiene el formulario

El widget replica los campos principales de "Nueva transacción" en Streamlit:

- **Descripción, Monto, Usuario, Tipo (gasto/ingreso), Categoría, Fecha, Medio (cuenta/tarjeta), Notas.**
- **Meses sin intereses** — aparece solo si el medio es una tarjeta; calcula `monto_por_mes` igual que la app.
- **💸 Es préstamo o apoyo** — checkbox opcional al final. Al marcarlo aparece: con quién (pareja / persona externa), qué pasó (te apoyan / tú pagaste por alguien), monto del apoyo (con botones "Completo"/"La mitad", o escribe uno fijo), y cómo se paga (un solo pago / abonos libres / conforme a MSI — esta última solo si la transacción usa MSI de tarjeta). Se guarda como un registro en `prestamo` ligado a la transacción, vía `widget/api/prestamo.js` — se ve en la app en **🤝 Préstamos**.

Simplificación respecto a la app: no incluye la opción de "Porcentaje" para el monto del apoyo (en la app sí existe) — si la necesitas, usa el campo de monto fijo y calcula el porcentaje tú misma, o pide que la agreguemos.

---

## Paso 3 (opcional/heredado): RLS en Supabase

⚠️ **Ya no es necesario para el widget.** Esto era para cuando el widget llamaba a la REST API de Supabase con la `anon key`. Ahora el backend (`widget/api/data.js`) se conecta directo a Postgres con el usuario `postgres`, que no pasa por RLS — así que este paso no bloquea ni habilita nada del flujo actual. Déjalo aquí solo por si en el futuro vuelves a exponer datos por REST/anon key para algo más.

Por defecto, si RLS está desactivado, cualquiera con la URL del proyecto puede leer/escribir todo. Con RLS activado, defines exactamente qué puede hacer la `anon key`.

Ve a Supabase → **SQL Editor** y ejecuta:

Este bloque es seguro de correr las veces que quieras — primero borra las policies si ya existían (`DROP POLICY IF EXISTS`) y luego las vuelve a crear, así que no truena si ya lo habías corrido antes:

```sql
-- Activar RLS en las tablas que usa el widget
ALTER TABLE usuario ENABLE ROW LEVEL SECURITY;
ALTER TABLE categoria ENABLE ROW LEVEL SECURITY;
ALTER TABLE cuenta ENABLE ROW LEVEL SECURITY;
ALTER TABLE tarjeta_credito ENABLE ROW LEVEL SECURITY;
ALTER TABLE transaccion ENABLE ROW LEVEL SECURITY;

-- Quitar policies previas (por si ya habías corrido este script antes)
DROP POLICY IF EXISTS "lectura_publica_usuario" ON usuario;
DROP POLICY IF EXISTS "lectura_publica_categoria" ON categoria;
DROP POLICY IF EXISTS "lectura_publica_cuenta" ON cuenta;
DROP POLICY IF EXISTS "lectura_publica_tarjeta" ON tarjeta_credito;
DROP POLICY IF EXISTS "insertar_gasto_publico" ON transaccion;
DROP POLICY IF EXISTS "insertar_transaccion_publica" ON transaccion;
DROP POLICY IF EXISTS "test_widget_select" ON transaccion;
DROP POLICY IF EXISTS "test_widget_delete" ON transaccion;

-- Permitir LECTURA pública de usuarios, categorías, cuentas y tarjetas
-- (el widget las necesita para llenar los selects)
CREATE POLICY "lectura_publica_usuario"
  ON usuario FOR SELECT
  USING (true);

CREATE POLICY "lectura_publica_categoria"
  ON categoria FOR SELECT
  USING (true);

CREATE POLICY "lectura_publica_cuenta"
  ON cuenta FOR SELECT
  USING (true);

CREATE POLICY "lectura_publica_tarjeta"
  ON tarjeta_credito FOR SELECT
  USING (true);

-- Permitir SOLO INSERT público en transaccion (no update/delete/select general).
-- El widget puede registrar tanto gastos como ingresos.
CREATE POLICY "insertar_transaccion_publica"
  ON transaccion FOR INSERT
  WITH CHECK (tipo IN ('gasto', 'ingreso'));

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

Con esto, el widget puede leer catálogos e insertar gastos/ingresos, pero **no puede leer, editar ni borrar** transacciones reales existentes — eso lo sigue haciendo solo la app de Streamlit (que se conecta directo por Postgres con las credenciales de `secrets.toml`, sin pasar por RLS). Las dos últimas policies son solo para que `test_widget.py` pueda auto-limpiarse; no dan acceso a datos reales porque exigen esa descripción exacta.

Si más adelante quieres restringir aún más (por ejemplo, que solo pueda insertar transacciones del usuario de tu novio), cambia el `WITH CHECK`:

```sql
WITH CHECK (tipo IN ('gasto', 'ingreso') AND usuario_id = 2)  -- reemplaza 2 por su id real
```

---

## Paso 4: Desplegar en Vercel

⚠️ Ahora tiene que ser Vercel (o algo con funciones serverless) — **GitHub Pages ya no sirve**, porque es hosting puramente estático y no puede correr `widget/api/data.js`.

1. Instala la CLI si no la tienes: `npm i -g vercel`
2. Desde la carpeta `widget/`, corre: `vercel --prod`
   - La primera vez instala la dependencia `pg` automáticamente a partir de `widget/package.json`.
   - Como el proyecto `fin-oscap` ya existe (de tu primer deploy), va a detectarlo solo.
3. Cuando termine te da la URL, ej. `https://fin-oscap.vercel.app`.
4. Abre esa URL en el celular de tu novio y agrégala a la pantalla de inicio ("Agregar a pantalla de inicio") para que se sienta como una app.

Si cambiaste algo en `widget/index.html` o `widget/api/data.js`, siempre tienes que repetir `vercel --prod` para que se vea reflejado — Vercel no se entera solo de los cambios en tu disco a menos que conectes un repo de Git (ver el aviso al inicio de esta conversación sobre "vercel.link/git").

---

## Paso 5: Testing

**Smoke test del backend, sin abrir el widget** — reemplaza la URL por la tuya:

```powershell
curl "https://fin-oscap.vercel.app/api/data?usuario_id=1&tipo=gasto"
```

Debe regresar un JSON con `usuarios`, `categorias`, `cuentas` y `tarjetas`. Si da error 500, el mensaje suele decir si es de conexión (revisa las variables de entorno del Paso 1) o de alguna columna/tabla.

**Prueba end-to-end:**

1. Abre la URL desplegada en el celular de tu novio.
2. Que registre un gasto de prueba (ej. "Café — $50"). Si quieres probar también el préstamo, márcalo como apoyo antes de guardar y confirma que aparece en **🤝 Préstamos** en Streamlit.
3. Verifica en la app de Streamlit: abre **Dashboard** o **Transacciones** y confirma que el gasto aparece.
   - Si no aparece de inmediato, recuerda que `obtener_transacciones` tiene caché de 5 minutos (`ttl=300`) — espera ese tiempo o reinicia la app (`R` en Streamlit) para forzar refresco.
4. Borra la transacción de prueba desde la app si no era un gasto real.

`test_widget.py` sigue probando el camino viejo (REST de Supabase + anon key) — útil para cuando el incidente de Supabase se resuelva y quieras confirmar que ese camino también sigue sano, pero no cubre `widget/api/data.js`. El `curl` de arriba es el equivalente para el camino nuevo.

---

## Velocidades esperadas

| | Antes | Después |
|---|---|---|
| Carga inicial de la app (`app.py`) | 8–10 seg | 2–3 seg |
| Cambiar de vista (Dashboard ↔ Transacciones) | 3–5 seg | Casi instantáneo (datos en caché) |
| Registrar un gasto (tu novio, desde el widget) | No existía — usaba la app completa | ~10 seg desde que abre el link hasta guardar |

La primera carga después de que expire el caché (o tras crear/editar/borrar algo) sigue tardando lo normal, porque se vuelve a consultar Supabase — es esperado, es lo que garantiza que los datos no queden obsoletos.
