-- Esquema de la base de datos (PostgreSQL en Supabase).
-- Refleja las tablas tal como existen en producción. Es seguro correrlo varias
-- veces en el SQL Editor de Supabase: solo crea lo que falte, nunca borra datos.

CREATE TABLE IF NOT EXISTS usuario (
    id            SERIAL PRIMARY KEY,
    nombre        TEXT   NOT NULL,
    color_perfil  TEXT   NOT NULL DEFAULT '#378ADD'
);

CREATE TABLE IF NOT EXISTS cuenta (
    id             SERIAL PRIMARY KEY,
    usuario_id     INTEGER NOT NULL REFERENCES usuario(id),
    nombre         TEXT    NOT NULL,
    tipo           TEXT    NOT NULL DEFAULT 'debito',
    saldo_inicial  REAL    NOT NULL DEFAULT 0.0,
    activa         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tarjeta_credito (
    id          SERIAL PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuario(id),
    nombre      TEXT    NOT NULL,
    banco       TEXT    NOT NULL,
    dia_corte   INTEGER NOT NULL,
    dia_pago    INTEGER NOT NULL,
    limite      REAL    NOT NULL DEFAULT 0.0,
    activa      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS categoria (
    id      SERIAL PRIMARY KEY,
    nombre  TEXT    NOT NULL UNIQUE,
    icono   TEXT    NOT NULL DEFAULT '📦',
    color   TEXT    NOT NULL DEFAULT '#888780',
    tipo    TEXT    NOT NULL DEFAULT 'gasto',   -- 'gasto' | 'ingreso'
    activa  INTEGER NOT NULL DEFAULT 1
);

-- Una transacción va ligada a una cuenta o a una tarjeta, nunca a las dos.
CREATE TABLE IF NOT EXISTS transaccion (
    id                   SERIAL PRIMARY KEY,
    usuario_id           INTEGER NOT NULL REFERENCES usuario(id),
    cuenta_id            INTEGER          REFERENCES cuenta(id),
    tarjeta_id           INTEGER          REFERENCES tarjeta_credito(id),
    categoria_id         INTEGER          REFERENCES categoria(id),
    monto                REAL    NOT NULL,
    fecha                TEXT    NOT NULL,  -- 'YYYY-MM-DD'
    descripcion          TEXT    NOT NULL DEFAULT '',
    tipo                 TEXT    NOT NULL DEFAULT 'gasto',
    notas                TEXT    NOT NULL DEFAULT '',
    meses_sin_intereses  INTEGER NOT NULL DEFAULT 0,
    monto_por_mes        REAL    NOT NULL DEFAULT 0.0,
    creado_en            TEXT    NOT NULL DEFAULT NOW()::text
);

-- Monto real de una mensualidad MSI cuando el banco cobra distinto al redondeo.
CREATE TABLE IF NOT EXISTS ajuste_msi (
    id              SERIAL PRIMARY KEY,
    transaccion_id  INTEGER NOT NULL REFERENCES transaccion(id) ON DELETE CASCADE,
    mensualidad_num INTEGER NOT NULL,
    monto           REAL    NOT NULL,
    UNIQUE (transaccion_id, mensualidad_num)
);

-- acreedor_id / deudor_id en NULL = persona externa (ver nombre_externo).
CREATE TABLE IF NOT EXISTS prestamo (
    id                   SERIAL PRIMARY KEY,
    acreedor_id          INTEGER REFERENCES usuario(id),
    deudor_id            INTEGER REFERENCES usuario(id),
    nombre_externo       TEXT,
    monto_original       REAL NOT NULL,
    monto_pendiente      REAL NOT NULL,
    fecha                TEXT NOT NULL,
    estado               TEXT NOT NULL DEFAULT 'pendiente',  -- 'pendiente' | 'pagado' | 'cancelado'
    notas                TEXT NOT NULL DEFAULT '',
    transaccion_id       INTEGER REFERENCES transaccion(id),
    fecha_estimada_pago  TEXT,
    creado_en            TEXT NOT NULL DEFAULT NOW()::text,
    tipo_pago            TEXT NOT NULL DEFAULT 'abonos',     -- 'unico' | 'abonos' | 'msi'
    meses_msi            INTEGER,
    monto_por_mes        REAL
);

CREATE TABLE IF NOT EXISTS pago_prestamo (
    id          SERIAL PRIMARY KEY,
    prestamo_id INTEGER NOT NULL REFERENCES prestamo(id),
    monto       REAL    NOT NULL,
    fecha       TEXT    NOT NULL,
    notas       TEXT    NOT NULL DEFAULT '',
    creado_en   TEXT    NOT NULL DEFAULT NOW()::text,
    tipo        TEXT    NOT NULL DEFAULT 'pago',  -- 'pago' | 'adelantado' | 'condonado'
    numero_mes  INTEGER
);

-- Heredada de la app de Streamlit; la app actual no la usa.
CREATE TABLE IF NOT EXISTS liquidacion (
    id                  SERIAL PRIMARY KEY,
    usuario_origen_id   INTEGER NOT NULL REFERENCES usuario(id),
    usuario_destino_id  INTEGER NOT NULL REFERENCES usuario(id),
    monto               REAL    NOT NULL,
    fecha               TEXT    NOT NULL,
    periodo             TEXT    NOT NULL,
    notas               TEXT    NOT NULL DEFAULT '',
    creado_en           TEXT    NOT NULL DEFAULT NOW()::text
);

-- Categorías iniciales (no duplica las que ya existan).
INSERT INTO categoria (nombre, icono, color, tipo) VALUES
    ('Comida y restaurantes', '🍽️', '#D85A30', 'gasto'),
    ('Citas',                 '❤️', '#921E1E', 'gasto'),
    ('Auto',                  '🚗', '#378ADD', 'gasto'),
    ('Salud',                 '💊', '#E24B4A', 'gasto'),
    ('Entretenimiento',       '🎬', '#EF9F27', 'gasto'),
    ('Ropa y calzado',        '👕', '#D4537E', 'gasto'),
    ('Educación',             '📚', '#534AB7', 'gasto'),
    ('Viajes',                '✈️', '#0F6E56', 'gasto'),
    ('Celular',               '📱', '#D3F512', 'gasto'),
    ('Regalos',               '🎁', '#BEF99E', 'gasto'),
    ('Suscripciones',         '🏷️', '#FEA8F1', 'gasto'),
    ('Personal',              '👩', '#613873', 'gasto'),
    ('Oficina',               '💼', '#423939', 'gasto'),
    ('Otros gastos',          '📦', '#888780', 'gasto'),
    ('Sueldo',                '💰', '#27500A', 'ingreso'),
    ('Otros ingresos',        '📈', '#085041', 'ingreso')
ON CONFLICT (nombre) DO NOTHING;
