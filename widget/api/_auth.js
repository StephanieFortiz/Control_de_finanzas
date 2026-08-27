const crypto = require('crypto');

const COOKIE_NAME = 'fin_session';
const MAX_AGE_SEG = 60 * 60 * 24 * 30; // 30 días

function firmar(expiraEn) {
  const secreto = process.env.SESSION_SECRET || '';
  return crypto.createHmac('sha256', secreto).update(String(expiraEn)).digest('hex');
}

function crearCookieSesion() {
  const expiraEn = Date.now() + MAX_AGE_SEG * 1000;
  const firma = firmar(expiraEn);
  const valor = `${expiraEn}.${firma}`;
  return `${COOKIE_NAME}=${valor}; HttpOnly; Secure; SameSite=Lax; Max-Age=${MAX_AGE_SEG}; Path=/`;
}

function cookieValida(cookieHeader) {
  if (!cookieHeader) return false;
  const partes = cookieHeader.split(';').map((p) => p.trim());
  const cookieSesion = partes.find((p) => p.startsWith(`${COOKIE_NAME}=`));
  if (!cookieSesion) return false;

  const valor = cookieSesion.slice(COOKIE_NAME.length + 1);
  const [expiraEnStr, firma] = valor.split('.');
  if (!expiraEnStr || !firma) return false;

  const expiraEn = Number(expiraEnStr);
  if (!expiraEn || Date.now() > expiraEn) return false;

  const firmaEsperada = firmar(expiraEn);
  const a = Buffer.from(firma, 'hex');
  const b = Buffer.from(firmaEsperada, 'hex');
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}

function requireAuth(req, res) {
  if (cookieValida(req.headers.cookie)) return true;
  res.status(401).json({ error: 'No autenticado.' });
  return false;
}

module.exports = { requireAuth, crearCookieSesion, COOKIE_NAME };
