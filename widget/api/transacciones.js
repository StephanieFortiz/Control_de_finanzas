const { getPool } = require('./_db');
const { requireAuth } = require('./_auth');
const { inyectarProyeccionesMsi } = require('./_msi');

const QUERY_BASE = `
  SELECT
      t.*,
      u.nombre          AS usuario_nombre,
      c.nombre          AS cuenta_nombre,
      tc.nombre         AS tarjeta_nombre,
      tc.banco          AS tarjeta_banco,
      tc.dia_corte      AS tarjeta_dia_corte,
      cat.nombre        AS categoria_nombre,
      cat.icono         AS categoria_icono,
      cat.color         AS categoria_color,
      p.id              AS prestamo_id,
      p.monto_pendiente AS prestamo_pendiente,
      p.monto_original  AS prestamo_monto_original,
      p.estado          AS prestamo_estado,
      ua.nombre         AS prestamo_acreedor,
      ud.nombre         AS prestamo_deudor,
      p.nombre_externo  AS prestamo_externo
  FROM transaccion t
  JOIN usuario u               ON t.usuario_id   = u.id
  LEFT JOIN cuenta c           ON t.cuenta_id    = c.id
  LEFT JOIN tarjeta_credito tc ON t.tarjeta_id   = tc.id
  LEFT JOIN categoria cat      ON t.categoria_id = cat.id
  LEFT JOIN prestamo p         ON p.transaccion_id = t.id AND p.estado = 'pendiente'
  LEFT JOIN usuario ua         ON p.acreedor_id  = ua.id
  LEFT JOIN usuario ud         ON p.deudor_id    = ud.id
  WHERE 1=1
`;

async function obtenerTransacciones(db, { usuarioId, desde, hasta, tipo, cuentaId, tarjetaId }) {
  let query = QUERY_BASE;
  const params = [];

  if (usuarioId) { params.push(usuarioId); query += ` AND t.usuario_id = $${params.length}`; }
  if (desde)     { params.push(desde);     query += ` AND t.fecha >= $${params.length}`; }
  if (hasta)     { params.push(hasta);     query += ` AND t.fecha <= $${params.length}`; }
  if (tipo)      { params.push(tipo);      query += ` AND t.tipo = $${params.length}`; }
  if (cuentaId)  { params.push(cuentaId);  query += ` AND t.cuenta_id = $${params.length}`; }
  if (tarjetaId) { params.push(tarjetaId); query += ` AND t.tarjeta_id = $${params.length}`; }
  query += ' ORDER BY t.fecha DESC, t.id DESC';

  const res = await db.query(query, params);
  return res.rows;
}

module.exports = async (req, res) => {
  if (!requireAuth(req, res)) return;
  const db = getPool();

  try {
    if (req.method === 'GET' && req.query.id) {
      const id = Number(req.query.id);
      const result = await db.query(
        `SELECT t.*, c.nombre AS cuenta_nombre, tc.nombre AS tarjeta_nombre
         FROM transaccion t
         LEFT JOIN cuenta c           ON t.cuenta_id  = c.id
         LEFT JOIN tarjeta_credito tc ON t.tarjeta_id = tc.id
         WHERE t.id = $1`,
        [id]
      );
      if (result.rows.length === 0) return res.status(404).json({ error: 'No existe la transacción.' });
      return res.status(200).json({ transaccion: result.rows[0] });
    }

    if (req.method === 'GET') {
      const usuarioId = req.query.usuario_id ? Number(req.query.usuario_id) : null;
      const desde = req.query.desde || null;
      const hasta = req.query.hasta || null;
      const categoriaId = req.query.categoria_id ? Number(req.query.categoria_id) : null;
      const cuentaId = req.query.cuenta_id ? Number(req.query.cuenta_id) : null;
      const tarjetaId = req.query.tarjeta_id ? Number(req.query.tarjeta_id) : null;

      if (!desde || !hasta) {
        return res.status(400).json({ error: 'desde y hasta son requeridos.' });
      }

      let txs = await obtenerTransacciones(db, { usuarioId, desde, hasta, cuentaId, tarjetaId });

      if (!cuentaId) {
        const hoy = new Date();
        const desdeAmplio = `${hoy.getUTCFullYear() - 3}-01-01`;
        const txsMsiBase = (await obtenerTransacciones(db, {
          usuarioId, desde: desdeAmplio, hasta, tipo: 'gasto', tarjetaId,
        })).filter((t) => (t.meses_sin_intereses || 0) > 0);

        if (txsMsiBase.length > 0) {
          txs = inyectarProyeccionesMsi(txs, desde, hasta, txsMsiBase);
        }
      }

      if (categoriaId) {
        txs = txs.filter((t) => t.categoria_id === categoriaId);
      }

      return res.status(200).json({ transacciones: txs });
    }

    if (req.method === 'PUT') {
      const {
        id, descripcion, monto, fecha, tipo, categoria_id,
        cuenta_id, tarjeta_id, notas, meses_sin_intereses,
      } = req.body || {};

      if (!id || !descripcion || !monto || monto <= 0 || !fecha || !['gasto', 'ingreso'].includes(tipo)) {
        return res.status(400).json({ error: 'Faltan campos requeridos o son inválidos.' });
      }
      if (!cuenta_id && !tarjeta_id) {
        return res.status(400).json({ error: 'Debes especificar cuenta_id o tarjeta_id.' });
      }
      if (cuenta_id && tarjeta_id) {
        return res.status(400).json({ error: 'No puede tener cuenta y tarjeta al mismo tiempo.' });
      }

      const meses = meses_sin_intereses || 0;
      const montoPorMes = meses > 0 ? Math.round((monto / meses) * 100) / 100 : 0;

      await db.query(
        `UPDATE transaccion SET
           descripcion = $1, monto = $2, fecha = $3, tipo = $4,
           categoria_id = $5, cuenta_id = $6, tarjeta_id = $7,
           notas = $8, meses_sin_intereses = $9, monto_por_mes = $10
         WHERE id = $11`,
        [
          descripcion, monto, fecha, tipo,
          categoria_id || null, cuenta_id || null, tarjeta_id || null,
          notas || '', meses, montoPorMes, id,
        ]
      );

      return res.status(200).json({ ok: true });
    }

    if (req.method === 'DELETE') {
      const id = req.query.id ? Number(req.query.id) : null;
      if (!id) return res.status(400).json({ error: 'Falta id.' });

      try {
        await db.query('DELETE FROM transaccion WHERE id = $1', [id]);
      } catch (err) {
        if (err.code === '23503') {
          return res.status(409).json({
            error: 'No se puede eliminar: esta transacción tiene un préstamo ligado. Elimina primero el préstamo desde 🤝 Préstamos.',
          });
        }
        throw err;
      }

      return res.status(200).json({ ok: true });
    }

    res.setHeader('Allow', 'GET, PUT, DELETE');
    return res.status(405).json({ error: 'Método no soportado.' });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: err.message });
  }
};
