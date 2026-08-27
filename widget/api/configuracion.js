const { getPool } = require('./_db');
const { requireAuth } = require('./_auth');

module.exports = async (req, res) => {
  if (!requireAuth(req, res)) return;
  const db = getPool();

  try {
    if (req.method === 'GET') {
      const recurso = req.query.recurso;

      if (recurso === 'usuarios') {
        const result = await db.query('SELECT * FROM usuario ORDER BY id');
        return res.status(200).json({ usuarios: result.rows });
      }

      if (recurso === 'cuentas') {
        const result = await db.query(
          `SELECT c.*, u.nombre AS usuario_nombre FROM cuenta c
           JOIN usuario u ON c.usuario_id = u.id
           ORDER BY c.activa DESC, u.nombre, c.nombre`
        );
        return res.status(200).json({ cuentas: result.rows });
      }

      if (recurso === 'tarjetas') {
        const result = await db.query(
          `SELECT t.*, u.nombre AS usuario_nombre FROM tarjeta_credito t
           JOIN usuario u ON t.usuario_id = u.id
           ORDER BY t.activa DESC, u.nombre, t.nombre`
        );
        return res.status(200).json({ tarjetas: result.rows });
      }

      if (recurso === 'categorias') {
        const incluirInactivas = req.query.incluir_inactivas === '1';
        const where = incluirInactivas ? '' : 'WHERE activa = 1';
        const result = await db.query(`SELECT * FROM categoria ${where} ORDER BY tipo, nombre`);
        return res.status(200).json({ categorias: result.rows });
      }

      return res.status(400).json({ error: 'recurso inválido.' });
    }

    if (req.method === 'POST') {
      const { recurso } = req.body || {};

      if (recurso === 'usuario') {
        const { nombre, color_perfil } = req.body;
        if (!nombre || !nombre.trim()) return res.status(400).json({ error: 'El nombre no puede estar vacío.' });
        const ins = await db.query(
          'INSERT INTO usuario (nombre, color_perfil) VALUES ($1, $2) RETURNING id',
          [nombre.trim(), color_perfil || '#378ADD']
        );
        return res.status(201).json({ ok: true, id: ins.rows[0].id });
      }

      if (recurso === 'cuenta') {
        const { usuario_id, nombre, tipo, saldo_inicial } = req.body;
        if (!usuario_id || !nombre || !nombre.trim()) return res.status(400).json({ error: 'Faltan campos requeridos.' });
        const ins = await db.query(
          'INSERT INTO cuenta (usuario_id, nombre, tipo, saldo_inicial) VALUES ($1, $2, $3, $4) RETURNING id',
          [usuario_id, nombre.trim(), tipo || 'debito', saldo_inicial || 0]
        );
        return res.status(201).json({ ok: true, id: ins.rows[0].id });
      }

      if (recurso === 'tarjeta') {
        const { usuario_id, nombre, banco, dia_corte, dia_pago, limite } = req.body;
        if (!usuario_id || !nombre || !nombre.trim() || !banco || !banco.trim()) {
          return res.status(400).json({ error: 'Nombre y banco son obligatorios.' });
        }
        const ins = await db.query(
          `INSERT INTO tarjeta_credito (usuario_id, nombre, banco, dia_corte, dia_pago, limite)
           VALUES ($1, $2, $3, $4, $5, $6) RETURNING id`,
          [usuario_id, nombre.trim(), banco.trim(), dia_corte || 1, dia_pago || 20, limite || 0]
        );
        return res.status(201).json({ ok: true, id: ins.rows[0].id });
      }

      if (recurso === 'categoria') {
        const { nombre, icono, color, tipo } = req.body;
        if (!nombre || !nombre.trim()) return res.status(400).json({ error: 'El nombre no puede estar vacío.' });
        const ins = await db.query(
          'INSERT INTO categoria (nombre, icono, color, tipo) VALUES ($1, $2, $3, $4) RETURNING id',
          [nombre.trim(), (icono || '📦').trim(), color || '#888780', tipo || 'gasto']
        );
        return res.status(201).json({ ok: true, id: ins.rows[0].id });
      }

      return res.status(400).json({ error: 'recurso inválido.' });
    }

    if (req.method === 'PUT') {
      const { recurso, id } = req.body || {};
      if (!id) return res.status(400).json({ error: 'Falta id.' });

      if (recurso === 'cuenta') {
        const { nombre, tipo, saldo_inicial, activa } = req.body;
        if (!nombre || !nombre.trim()) return res.status(400).json({ error: 'El nombre no puede estar vacío.' });
        await db.query(
          'UPDATE cuenta SET nombre=$1, tipo=$2, saldo_inicial=$3, activa=$4 WHERE id=$5',
          [nombre.trim(), tipo, saldo_inicial, activa ? 1 : 0, id]
        );
        return res.status(200).json({ ok: true });
      }

      if (recurso === 'tarjeta') {
        const { nombre, banco, dia_corte, dia_pago, limite, activa } = req.body;
        if (!nombre || !nombre.trim() || !banco || !banco.trim()) {
          return res.status(400).json({ error: 'Nombre y banco son obligatorios.' });
        }
        await db.query(
          `UPDATE tarjeta_credito SET nombre=$1, banco=$2, dia_corte=$3, dia_pago=$4, limite=$5, activa=$6 WHERE id=$7`,
          [nombre.trim(), banco.trim(), dia_corte, dia_pago, limite, activa ? 1 : 0, id]
        );
        return res.status(200).json({ ok: true });
      }

      if (recurso === 'categoria') {
        const { nombre, icono, color, tipo, activa } = req.body;
        if (!nombre || !nombre.trim()) return res.status(400).json({ error: 'El nombre no puede estar vacío.' });
        await db.query(
          'UPDATE categoria SET nombre=$1, icono=$2, color=$3, tipo=$4, activa=$5 WHERE id=$6',
          [nombre.trim(), (icono || '📦').trim(), color, tipo, activa ? 1 : 0, id]
        );
        return res.status(200).json({ ok: true });
      }

      return res.status(400).json({ error: 'recurso inválido.' });
    }

    res.setHeader('Allow', 'GET, POST, PUT');
    return res.status(405).json({ error: 'Método no soportado.' });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: err.message });
  }
};
