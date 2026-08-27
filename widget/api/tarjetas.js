const { getPool } = require('./_db');
const { requireAuth } = require('./_auth');
const { estadoTarjeta, agruparPorPeriodo } = require('./_calculos');

function aplicarAjustes(transacciones, ajustes) {
  return transacciones.map((t) => {
    if (!t.es_proyeccion) return t;
    const clave = `${t.id}:${t.mensualidad_num}`;
    if (!(clave in ajustes)) return t;
    return { ...t, monto: ajustes[clave], monto_por_mes: ajustes[clave] };
  });
}

module.exports = async (req, res) => {
  if (!requireAuth(req, res)) return;
  const db = getPool();

  try {
    const usuarioId = req.query.usuario_id ? Number(req.query.usuario_id) : null;
    if (!usuarioId) return res.status(400).json({ error: 'Falta usuario_id.' });

    if (req.method === 'POST') {
      const { transaccion_id, mensualidad_num, monto } = req.body || {};
      if (!transaccion_id || !mensualidad_num || !monto || monto <= 0) {
        return res.status(400).json({ error: 'Faltan campos requeridos o son inválidos.' });
      }
      await db.query(
        `INSERT INTO ajuste_msi (transaccion_id, mensualidad_num, monto)
         VALUES ($1, $2, $3)
         ON CONFLICT (transaccion_id, mensualidad_num) DO UPDATE SET monto = EXCLUDED.monto`,
        [transaccion_id, mensualidad_num, monto]
      );
      return res.status(200).json({ ok: true });
    }

    if (req.method !== 'GET') {
      res.setHeader('Allow', 'GET, POST');
      return res.status(405).json({ error: 'Método no soportado.' });
    }

    const tarjetaId = req.query.tarjeta_id ? Number(req.query.tarjeta_id) : null;

    if (!tarjetaId) {
      const result = await db.query(
        'SELECT * FROM tarjeta_credito WHERE usuario_id = $1 AND activa = 1 ORDER BY nombre',
        [usuarioId]
      );
      return res.status(200).json({ tarjetas: result.rows });
    }

    const tarjetaRes = await db.query(
      'SELECT * FROM tarjeta_credito WHERE id = $1 AND usuario_id = $2', [tarjetaId, usuarioId]
    );
    if (tarjetaRes.rows.length === 0) return res.status(404).json({ error: 'No existe la tarjeta.' });
    const tarjeta = tarjetaRes.rows[0];

    const hoy = new Date().toISOString().slice(0, 10);
    const desde = `${new Date().getUTCFullYear() - 3}-01-01`;

    const txsRes = await db.query(
      `SELECT t.*, cat.icono AS categoria_icono, cat.nombre AS categoria_nombre
       FROM transaccion t
       LEFT JOIN categoria cat ON t.categoria_id = cat.id
       WHERE t.usuario_id = $1 AND t.tarjeta_id = $2 AND t.fecha >= $3 AND t.fecha <= $4
       ORDER BY t.fecha`,
      [usuarioId, tarjetaId, desde, hoy]
    );
    const txsTarjeta = txsRes.rows;

    const msiIds = [...new Set(txsTarjeta.filter((t) => (t.meses_sin_intereses || 0) > 0).map((t) => t.id))];
    let ajustes = {};
    if (msiIds.length > 0) {
      const ajustesRes = await db.query(
        'SELECT transaccion_id, mensualidad_num, monto FROM ajuste_msi WHERE transaccion_id = ANY($1)',
        [msiIds]
      );
      for (const a of ajustesRes.rows) ajustes[`${a.transaccion_id}:${a.mensualidad_num}`] = a.monto;
    }

    const txIdsReales = txsTarjeta.map((t) => t.id);
    let prestamosPorTx = {};
    if (txIdsReales.length > 0) {
      const prestamosRes = await db.query(
        `SELECT p.*, ua.nombre AS acreedor_nombre, ud.nombre AS deudor_nombre
         FROM prestamo p
         LEFT JOIN usuario ua ON p.acreedor_id = ua.id
         LEFT JOIN usuario ud ON p.deudor_id   = ud.id
         WHERE p.transaccion_id = ANY($1) AND p.estado = 'pendiente'`,
        [txIdsReales]
      );
      for (const p of prestamosRes.rows) if (p.transaccion_id) prestamosPorTx[p.transaccion_id] = p;
    }

    const fechaCorteObjetivo = req.query.fecha_corte_objetivo || null;
    const estado = estadoTarjeta(tarjeta, txsTarjeta, hoy, fechaCorteObjetivo);
    estado.transacciones = aplicarAjustes(estado.transacciones, ajustes);

    const grupos = agruparPorPeriodo(txsTarjeta, tarjeta.dia_corte);
    for (const label of Object.keys(grupos)) {
      grupos[label].transacciones = aplicarAjustes(grupos[label].transacciones, ajustes);
    }

    return res.status(200).json({ tarjeta, estado, grupos, ajustes, prestamosPorTx });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: err.message });
  }
};
