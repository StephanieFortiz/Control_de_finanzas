const crypto = require('crypto');
const { crearCookieSesion } = require('./_auth');

function iguales(a, b) {
  const bufA = Buffer.from(String(a));
  const bufB = Buffer.from(String(b));
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

module.exports = async (req, res) => {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'Método no soportado.' });
  }

  const { password } = req.body || {};
  const esperado = process.env.APP_PASSWORD || '';

  if (!esperado || !password || !iguales(password, esperado)) {
    return res.status(401).json({ error: 'Contraseña incorrecta.' });
  }

  res.setHeader('Set-Cookie', crearCookieSesion());
  return res.status(200).json({ ok: true });
};
