const { getPool } = require('./_db');

module.exports = async (req, res) => {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'Método no soportado.' });
  }

  const db = getPool();

  try {
    const {
      transaccion_id, monto, fecha, notas,
      acreedor_id, deudor_id, nombre_externo,
      tipo_pago, meses_msi, monto_por_mes,
    } = req.body || {};

    if (!monto || monto <= 0 || !fecha || !transaccion_id) {
      return res.status(400).json({ error: 'Faltan campos requeridos o son inválidos.' });
    }
    if (!acreedor_id && !nombre_externo) {
      return res.status(400).json({ error: 'Debe haber un acreedor (usuario o nombre externo).' });
    }
    if (!['unico', 'abonos', 'msi'].includes(tipo_pago)) {
      return res.status(400).json({ error: 'tipo_pago inválido.' });
    }

    const ins = await db.query(
      `INSERT INTO prestamo
         (acreedor_id, deudor_id, nombre_externo,
          monto_original, monto_pendiente, fecha, notas,
          transaccion_id, tipo_pago, meses_msi, monto_por_mes)
       VALUES ($1, $2, $3, $4, $4, $5, $6, $7, $8, $9, $10)
       RETURNING id`,
      [
        acreedor_id || null, deudor_id || null, nombre_externo || null,
        monto, fecha, notas || '',
        transaccion_id, tipo_pago,
        meses_msi || null, monto_por_mes || null,
      ]
    );

    return res.status(201).json({ ok: true, id: ins.rows[0].id });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: err.message });
  }
};
