const { Pool } = require('pg');

let pool;
function getPool() {
  if (!pool) {
    pool = new Pool({
      host: process.env.PGHOST,
      port: Number(process.env.PGPORT || 5432),
      database: process.env.PGDATABASE,
      user: process.env.PGUSER,
      password: process.env.PGPASSWORD,
      ssl: { rejectUnauthorized: false },
      max: 1,
    });
  }
  return pool;
}

module.exports = async (req, res) => {
  const db = getPool();

  try {
    if (req.method === 'GET') {
      const tipo = req.query.tipo === 'ingreso' ? 'ingreso' : 'gasto';
      const usuarioId = req.query.usuario_id ? Number(req.query.usuario_id) : null;

      const [usuarios, categorias, cuentas, tarjetas] = await Promise.all([
        db.query('SELECT id, nombre FROM usuario ORDER BY id'),
        db.query(
          'SELECT id, nombre, icono FROM categoria WHERE tipo = $1 AND activa = 1 ORDER BY nombre',
          [tipo]
        ),
        usuarioId
          ? db.query(
              'SELECT id, nombre FROM cuenta WHERE usuario_id = $1 AND activa = 1 ORDER BY nombre',
              [usuarioId]
            )
          : { rows: [] },
        usuarioId
          ? db.query(
              'SELECT id, nombre, banco FROM tarjeta_credito WHERE usuario_id = $1 AND activa = 1 ORDER BY nombre',
              [usuarioId]
            )
          : { rows: [] },
      ]);

      return res.status(200).json({
        usuarios: usuarios.rows,
        categorias: categorias.rows,
        cuentas: cuentas.rows,
        tarjetas: tarjetas.rows,
      });
    }

    if (req.method === 'POST') {
      const {
        usuario_id, cuenta_id, tarjeta_id, categoria_id,
        monto, fecha, descripcion, tipo, notas,
        meses_sin_intereses, monto_por_mes,
      } = req.body || {};

      if (
        !usuario_id || !categoria_id || !monto || monto <= 0 ||
        !fecha || !descripcion || !['gasto', 'ingreso'].includes(tipo)
      ) {
        return res.status(400).json({ error: 'Faltan campos requeridos o son inválidos.' });
      }
      if (!cuenta_id && !tarjeta_id) {
        return res.status(400).json({ error: 'Debes especificar cuenta_id o tarjeta_id.' });
      }
      if (cuenta_id && tarjeta_id) {
        return res.status(400).json({ error: 'No puede tener cuenta y tarjeta al mismo tiempo.' });
      }

      await db.query(
        `INSERT INTO transaccion
           (usuario_id, cuenta_id, tarjeta_id, categoria_id,
            monto, fecha, descripcion, tipo,
            notas, meses_sin_intereses, monto_por_mes)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)`,
        [
          usuario_id, cuenta_id || null, tarjeta_id || null, categoria_id,
          monto, fecha, descripcion, tipo,
          notas || '', meses_sin_intereses || 0, monto_por_mes || 0,
        ]
      );

      return res.status(201).json({ ok: true });
    }

    res.setHeader('Allow', 'GET, POST');
    return res.status(405).json({ error: 'Método no soportado.' });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: err.message });
  }
};
