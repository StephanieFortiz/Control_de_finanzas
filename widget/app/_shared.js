const $ = (id) => document.getElementById(id);

function fmt(monto) {
  return `$${Number(monto || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s || '';
  return div.innerHTML;
}

async function authFetch(url, opts) {
  const res = await fetch(url, opts);
  if (res.status === 401) {
    location.href = '/login.html?destino=' + encodeURIComponent(location.pathname);
    throw new Error('Sesión expirada, redirigiendo...');
  }
  return res;
}

// Port de utils/calculos.py:_fecha_mas_n_meses — ver widget/api/_msi.js para la
// versión de servidor y las pruebas contra el original en Python.
function ultimoDiaDeMes(anio, mes) {
  return new Date(Date.UTC(anio, mes, 0)).getUTCDate();
}
function fechaMasNMeses(fechaIso, n) {
  const [anio, mes, dia] = fechaIso.split('-').map(Number);
  const mTotal = mes + n;
  const anioNuevo = anio + Math.floor((mTotal - 1) / 12);
  const mesNuevo = ((mTotal - 1) % 12) + 1;
  const diaNuevo = Math.min(dia, ultimoDiaDeMes(anioNuevo, mesNuevo));
  return `${String(anioNuevo).padStart(4, '0')}-${String(mesNuevo).padStart(2, '0')}-${String(diaNuevo).padStart(2, '0')}`;
}

// Port de utils/calculos.py:calcular_fecha_pago — ver widget/api/_calculos.js
// para la versión de servidor y las pruebas contra el original en Python.
function calcularFechaPago(fechaCorteIso, diaPago) {
  const [anio, mes, dia] = fechaCorteIso.split('-').map(Number);
  if (diaPago > dia) {
    return `${String(anio).padStart(4, '0')}-${String(mes).padStart(2, '0')}-${String(Math.min(diaPago, ultimoDiaDeMes(anio, mes))).padStart(2, '0')}`;
  }
  let anioPago = anio, mesPago = mes + 1;
  if (mesPago === 13) { anioPago += 1; mesPago = 1; }
  return `${String(anioPago).padStart(4, '0')}-${String(mesPago).padStart(2, '0')}-${String(Math.min(diaPago, ultimoDiaDeMes(anioPago, mesPago))).padStart(2, '0')}`;
}

// Port de utils/dashboard.py:_monto_efectivo — para recalcular en el cliente
// cuando los filtros de tarjeta/categoría cambian sin pedir datos de nuevo.
function montoEfectivo(t) {
  if ((t.meses_sin_intereses || 0) > 0 && !t.es_proyeccion) {
    return t.monto_por_mes || t.monto;
  }
  return t.monto;
}

// "Viendo como" — quién está usando la app, persistido entre visitas.
// Compartido entre páginas de widget/app/ vía localStorage.
const CLAVE_USUARIO_ACTIVO = 'finanzas_usuario_activo';
function obtenerUsuarioActivoGuardado() {
  return localStorage.getItem(CLAVE_USUARIO_ACTIVO);
}
function guardarUsuarioActivo(id) {
  localStorage.setItem(CLAVE_USUARIO_ACTIVO, String(id));
}
