const { getPool } = require('./_db');
const { requireAuth } = require('./_auth');

module.exports = async (req, res) => {
  if (!requireAuth(req, res)) return;
  const db = getPool();

  try {
    const usuarioId = req.query.usuario_id ? Number(req.query.usuario_id) : null;

    const [usuarios, categorias, cuentas, tarjetas] = await Promise.all([
      db.query('SELECT id, nombre FROM usuario ORDER BY id'),
      db.query('SELECT id, nombre, icono, tipo FROM categoria WHERE activa = 1 ORDER BY tipo, nombre'),
      usuarioId
        ? db.query('SELECT id, nombre, tipo FROM cuenta WHERE usuario_id = $1 AND activa = 1 ORDER BY nombre', [usuarioId])
        : db.query('SELECT id, nombre, tipo FROM cuenta WHERE activa = 1 ORDER BY nombre'),
      usuarioId
        ? db.query('SELECT id, nombre, banco FROM tarjeta_credito WHERE usuario_id = $1 AND activa = 1 ORDER BY nombre', [usuarioId])
        : db.query('SELECT id, nombre, banco FROM tarjeta_credito WHERE activa = 1 ORDER BY nombre'),
    ]);

    return res.status(200).json({
      usuarios: usuarios.rows,
      categorias: categorias.rows,
      cuentas: cuentas.rows,
      tarjetas: tarjetas.rows,
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: err.message });
  }
};
