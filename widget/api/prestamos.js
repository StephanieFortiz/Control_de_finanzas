const { getPool } = require('./_db');
const { requireAuth } = require('./_auth');

const QUERY_BASE = `
  SELECT
      p.*,
      ua.nombre     AS acreedor_nombre,
      ud.nombre     AS deudor_nombre,
      t.descripcion AS tx_descripcion,
      t.monto       AS tx_monto,
      t.fecha       AS tx_fecha,
      c.nombre      AS tx_cuenta_nombre,
      tc.nombre     AS tx_tarjeta_nombre,
      tc.banco      AS tx_tarjeta_banco
  FROM prestamo p
  LEFT JOIN usuario ua          ON p.acreedor_id    = ua.id
  LEFT JOIN usuario ud          ON p.deudor_id      = ud.id
  LEFT JOIN transaccion t       ON p.transaccion_id = t.id
  LEFT JOIN cuenta c            ON t.cuenta_id      = c.id
  LEFT JOIN tarjeta_credito tc  ON t.tarjeta_id     = tc.id
  WHERE 1=1
`;

module.exports = async (req, res) => {
  if (!requireAuth(req, res)) return;
  const db = getPool();

  try {
    if (req.method === 'GET') {
      const usuarioId = req.query.usuario_id ? Number(req.query.usuario_id) : null;
      const estado = req.query.estado || null;

      let query = QUERY_BASE;
      const params = [];
      if (usuarioId) {
        params.push(usuarioId);
        query += ` AND (p.acreedor_id = $${params.length} OR p.deudor_id = $${params.length})`;
      }
      if (estado) {
        params.push(estado);
        query += ` AND p.estado = $${params.length}`;
      }
      query += ' ORDER BY p.fecha DESC';

      const result = await db.query(query, params);
      return res.status(200).json({ prestamos: result.rows });
    }

    if (req.method === 'DELETE') {
      const id = req.query.id ? Number(req.query.id) : null;
      if (!id) return res.status(400).json({ error: 'Falta id.' });

      await db.query('DELETE FROM pago_prestamo WHERE prestamo_id = $1', [id]);
      await db.query('DELETE FROM prestamo WHERE id = $1', [id]);
      return res.status(200).json({ ok: true });
    }

    res.setHeader('Allow', 'GET, DELETE');
    return res.status(405).json({ error: 'Método no soportado.' });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: err.message });
  }
};
