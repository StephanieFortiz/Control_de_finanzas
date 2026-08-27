const { getPool } = require('./_db');
const { requireAuth } = require('./_auth');

module.exports = async (req, res) => {
  if (!requireAuth(req, res)) return;
  const db = getPool();

  try {
    if (req.method === 'GET') {
      if (req.query.tx_ids) {
        const txIds = String(req.query.tx_ids)
          .split(',')
          .map((s) => Number(s.trim()))
          .filter((n) => !Number.isNaN(n));

        if (txIds.length === 0) return res.status(200).json({ porTransaccion: {} });

        const result = await db.query(
          `SELECT p.*, ua.nombre AS acreedor_nombre, ud.nombre AS deudor_nombre
           FROM prestamo p
           LEFT JOIN usuario ua ON p.acreedor_id = ua.id
           LEFT JOIN usuario ud ON p.deudor_id   = ud.id
           WHERE p.transaccion_id = ANY($1) AND p.estado = 'pendiente'`,
          [txIds]
        );

        const porTransaccion = {};
        for (const p of result.rows) {
          if (p.transaccion_id) porTransaccion[p.transaccion_id] = p;
        }
        return res.status(200).json({ porTransaccion });
      }

      if (req.query.prestamo_id) {
        const prestamoId = Number(req.query.prestamo_id);
        const result = await db.query(
          'SELECT * FROM pago_prestamo WHERE prestamo_id = $1 ORDER BY fecha, id',
          [prestamoId]
        );
        return res.status(200).json({ pagos: result.rows });
      }

      return res.status(400).json({ error: 'Falta tx_ids o prestamo_id.' });
    }

    if (req.method === 'POST') {
      const { prestamo_id, monto, fecha, notas, tipo, numero_mes } = req.body || {};

      if (!prestamo_id || !monto || monto <= 0 || !fecha) {
        return res.status(400).json({ error: 'Faltan campos requeridos o son inválidos.' });
      }

      const prestamoRes = await db.query(
        'SELECT monto_pendiente FROM prestamo WHERE id = $1', [prestamo_id]
      );
      if (prestamoRes.rows.length === 0) {
        return res.status(404).json({ error: `No existe el préstamo con id=${prestamo_id}.` });
      }

      const pendienteActual = prestamoRes.rows[0].monto_pendiente;
      const nuevoPendiente = Math.max(Math.round((pendienteActual - monto) * 100) / 100, 0);
      const nuevoEstado = nuevoPendiente <= 0 ? 'pagado' : 'pendiente';

      await db.query(
        'UPDATE prestamo SET monto_pendiente = $1, estado = $2 WHERE id = $3',
        [nuevoPendiente, nuevoEstado, prestamo_id]
      );

      const ins = await db.query(
        `INSERT INTO pago_prestamo (prestamo_id, monto, fecha, notas, tipo, numero_mes)
         VALUES ($1, $2, $3, $4, $5, $6) RETURNING id`,
        [prestamo_id, monto, fecha, notas || '', tipo || 'pago', numero_mes || null]
      );

      return res.status(201).json({ ok: true, id: ins.rows[0].id, nuevo_pendiente: nuevoPendiente, nuevo_estado: nuevoEstado });
    }

    res.setHeader('Allow', 'GET, POST');
    return res.status(405).json({ error: 'Método no soportado.' });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: err.message });
  }
};
