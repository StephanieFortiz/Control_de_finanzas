# Finanzas

Aplicación web para gestión de finanzas personales en pareja: ingresos, gastos, tarjetas de crédito (con meses sin intereses), préstamos entre los dos usuarios o con personas externas.

Producción: https://fin-oscap.vercel.app

## Tecnologías

- **Frontend**: HTML + JavaScript sin framework ni build.
- **Backend**: funciones serverless de [Vercel](https://vercel.com/) (Node.js + [`pg`](https://node-postgres.com/)).
- **Base de datos**: PostgreSQL en [Supabase](https://supabase.com/), vía su connection pooler.
- **Gráficas**: [Apache ECharts](https://echarts.apache.org/), auto-hospedado en `widget/app/vendor/`.

## Módulos

| Página | Qué hace |
|---|---|
| `app/dashboard.html` | Resumen mensual: ingresos, gastos, ahorro, estado de tarjetas y gastos por categoría. |
| `app/transacciones.html` | Nueva transacción (con préstamo/apoyo opcional), historial con filtros, editar, borrar y abonar. |
| `app/tarjetas.html` | Estado de cuenta por fecha de corte, historial por período y ajustes de mensualidades MSI. |
| `app/prestamos.html` | Préstamos pendientes y archivados, abonos y calendario MSI. |
| `app/configuracion.html` | Perfiles, cuentas, tarjetas y categorías. |

La raíz `/` redirige a Transacciones. Todas las páginas de `app/` piden iniciar sesión en `/login.html`.

## Estructura del proyecto

```
Finanzas/
├── schema.sql            # Tablas de la base de datos (correr en el SQL Editor de Supabase)
└── widget/               # Proyecto de Vercel (fin-oscap)
    ├── index.html        # Redirige a la app
    ├── login.html
    ├── app/              # Páginas y su JS (_shared.js tiene utilidades comunes)
    └── api/              # Funciones serverless, una por recurso
        ├── _db.js        # Pool de conexión a Postgres
        ├── _auth.js      # Sesión firmada con cookie
        ├── _calculos.js  # Ciclos de corte/pago de tarjetas
        └── _msi.js       # Proyecciones de meses sin intereses
```

## Configuración en Vercel

El proyecto de Vercel apunta a la carpeta `widget/`. Necesita estas variables de entorno (Production):

| Variable | Valor |
|---|---|
| `PGHOST` | Host del **Transaction pooler** de Supabase (`aws-…pooler.supabase.com`) |
| `PGPORT` | `6543` |
| `PGDATABASE` | `postgres` |
| `PGUSER` | Usuario del pooler (`postgres.<id-del-proyecto>`) |
| `PGPASSWORD` | Contraseña de Postgres |
| `APP_PASSWORD` | Contraseña compartida para entrar a la app |
| `SESSION_SECRET` | Cadena aleatoria para firmar la sesión |

Usa las credenciales del pooler (Supabase → **Connect** → **Transaction pooler**), no las del host directo `db.<proyecto>.supabase.co`: ese solo resuelve por IPv6 y Vercel no tiene salida IPv6.

Para generar `SESSION_SECRET`:

```powershell
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

Se pueden agregar desde Vercel → proyecto → **Settings → Environment Variables**, o con la CLI desde `widget/`:

```powershell
vercel env add PGHOST production
```

## Desplegar

Desde la carpeta `widget/`:

```powershell
npm i -g vercel   # solo la primera vez
vercel --prod
```

Vercel no detecta solo los cambios en tu disco: hay que repetir `vercel --prod` después de cada cambio (a menos que se conecte el repo de Git al proyecto).

## Base de datos nueva

Para crear la base desde cero, abre el SQL Editor de Supabase y corre [`schema.sql`](schema.sql). Crea las tablas que falten y las categorías iniciales; es seguro correrlo más de una vez.

## Licencia

Uso personal — sin licencia pública.
