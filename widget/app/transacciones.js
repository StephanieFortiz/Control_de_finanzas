const $ = (id) => document.getElementById(id);
const MESES_ES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
  'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

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

// ══════════════════════════════════════════════════════════════════════
// NUEVA TRANSACCIÓN (mismo comportamiento que widget/captura.html)
// ══════════════════════════════════════════════════════════════════════

(function nuevaTransaccion() {
  const nMensajeEl = $('n-mensaje');
  const nBtnGuardar = $('n-btn-guardar');
  let usuariosCacheN = [];

  function mostrarMensajeN(texto, tipo) {
    nMensajeEl.textContent = texto;
    nMensajeEl.className = `mensaje ${tipo}`;
  }
  function ocultarMensajeN() {
    nMensajeEl.className = 'mensaje';
    nMensajeEl.textContent = '';
  }

  $('n-fecha').valueAsDate = new Date();

  document.querySelectorAll('#n-montos-rapidos .monto-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      $('n-monto').value = btn.dataset.monto;
      document.querySelectorAll('#n-montos-rapidos .monto-btn').forEach((b) => b.classList.remove('activo'));
      btn.classList.add('activo');
    });
  });
  $('n-monto').addEventListener('input', () => {
    document.querySelectorAll('#n-montos-rapidos .monto-btn').forEach((b) => b.classList.remove('activo'));
  });

  function mesesSinInteresesActualN() {
    const esTarjeta = $('n-medio').value.startsWith('tarjeta:');
    return (esTarjeta && $('n-usar-msi').checked) ? Number($('n-msi-meses').value) : 0;
  }

  function actualizarOpcionMsiPrestamoN() {
    const meses = mesesSinInteresesActualN();
    const opt = $('n-p-opcion-msi');
    if (meses > 0) {
      opt.textContent = `Conforme a MSI (${meses} meses)`;
      opt.hidden = false;
    } else {
      opt.hidden = true;
      if ($('n-p-forma-pago').value === 'msi') $('n-p-forma-pago').value = 'abonos';
    }
  }

  function actualizarVisibilidadMsiN() {
    const esTarjeta = $('n-medio').value.startsWith('tarjeta:');
    $('n-msi-box').classList.toggle('oculto', !esTarjeta);
    if (!esTarjeta) {
      $('n-usar-msi').checked = false;
      $('n-msi-meses').classList.add('oculto');
    }
    actualizarOpcionMsiPrestamoN();
  }

  $('n-medio').addEventListener('change', actualizarVisibilidadMsiN);
  $('n-usar-msi').addEventListener('change', () => {
    $('n-msi-meses').classList.toggle('oculto', !$('n-usar-msi').checked);
    actualizarOpcionMsiPrestamoN();
  });
  $('n-msi-meses').addEventListener('change', actualizarOpcionMsiPrestamoN);

  $('n-es-prestamo').addEventListener('change', () => {
    const activo = $('n-es-prestamo').checked;
    $('n-prestamo-box').classList.toggle('oculto', !activo);
    if (activo) actualizarOpcionMsiPrestamoN();
  });
  $('n-p-contraparte').addEventListener('change', () => {
    $('n-p-nombre-externo').classList.toggle('oculto', $('n-p-contraparte').value !== 'externa');
  });
  document.querySelectorAll('#n-p-montos-rapidos .n-p-monto-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const base = parseFloat($('n-monto').value) || 0;
      const valor = btn.dataset.modo === 'mitad' ? Math.round((base / 2) * 100) / 100 : base;
      $('n-p-monto').value = valor;
      document.querySelectorAll('#n-p-montos-rapidos .n-p-monto-btn').forEach((b) => b.classList.remove('activo'));
      btn.classList.add('activo');
    });
  });

  function resetearPrestamoN() {
    $('n-es-prestamo').checked = false;
    $('n-prestamo-box').classList.add('oculto');
    $('n-p-contraparte').value = 'pareja';
    $('n-p-nombre-externo').value = '';
    $('n-p-nombre-externo').classList.add('oculto');
    $('n-p-direccion').value = 'me_apoyan';
    $('n-p-monto').value = '';
    $('n-p-forma-pago').value = 'unico';
    document.querySelectorAll('#n-p-montos-rapidos .n-p-monto-btn').forEach((b) => b.classList.remove('activo'));
  }

  async function pedirDatosN(usuarioId, tipo) {
    const res = await fetch(`/api/data?usuario_id=${usuarioId}&tipo=${tipo}`);
    if (!res.ok) {
      const cuerpo = await res.json().catch(() => ({}));
      throw new Error(cuerpo.error || `HTTP ${res.status}`);
    }
    return res.json();
  }

  function poblarUsuariosN(usuarios) {
    usuariosCacheN = usuarios;
    $('n-usuario').innerHTML = usuarios.map((u) => `<option value="${u.id}">${u.nombre}</option>`).join('')
      || '<option value="">Sin usuarios</option>';
  }
  function poblarCategoriasN(categorias) {
    $('n-categoria').innerHTML = categorias.map((c) => `<option value="${c.id}">${c.icono || '📦'} ${c.nombre}</option>`).join('')
      || '<option value="">Sin categorías</option>';
  }
  function poblarMediosN(cuentas, tarjetas) {
    const oc = cuentas.map((c) => `<option value="cuenta:${c.id}">🏦 ${c.nombre}</option>`).join('');
    const ot = tarjetas.map((t) => `<option value="tarjeta:${t.id}">💳 ${t.nombre} (${t.banco})</option>`).join('');
    $('n-medio').innerHTML = oc + ot || '<option value="">Sin cuentas/tarjetas</option>';
    actualizarVisibilidadMsiN();
  }

  async function refrescarDependientesN() {
    try {
      const datos = await pedirDatosN($('n-usuario').value, $('n-tipo').value);
      poblarCategoriasN(datos.categorias);
      poblarMediosN(datos.cuentas, datos.tarjetas);
    } catch (err) {
      mostrarMensajeN('❌ Error al recargar datos: ' + err.message, 'error');
    }
  }

  async function cargarInicialN() {
    try {
      const primerUsuario = usuariosCacheGlobal.length ? usuariosCacheGlobal[0].id : 1;
      const datos = await pedirDatosN(primerUsuario, $('n-tipo').value);
      poblarUsuariosN(datos.usuarios);
      await refrescarDependientesN();
    } catch (err) {
      mostrarMensajeN('❌ Error al cargar datos: ' + err.message, 'error');
    }
  }

  $('n-usuario').addEventListener('change', refrescarDependientesN);
  $('n-tipo').addEventListener('change', refrescarDependientesN);

  window.cargarNuevaTransaccion = cargarInicialN;

  $('form-nueva').addEventListener('submit', async (e) => {
    e.preventDefault();
    ocultarMensajeN();

    const descripcion = $('n-descripcion').value.trim();
    const monto = parseFloat($('n-monto').value);
    const usuarioId = $('n-usuario').value;
    const tipo = $('n-tipo').value;
    const categoriaId = $('n-categoria').value;
    const fecha = $('n-fecha').value;
    const medio = $('n-medio').value;
    const notas = $('n-notas').value.trim();

    if (!descripcion || !monto || monto <= 0 || !usuarioId || !categoriaId || !fecha || !medio) {
      mostrarMensajeN('⚠️ Completa todos los campos requeridos.', 'error');
      return;
    }

    const [tipoMedio, medioId] = medio.split(':');
    const esTarjeta = tipoMedio === 'tarjeta';
    const mesesSinIntereses = (esTarjeta && $('n-usar-msi').checked) ? Number($('n-msi-meses').value) : 0;
    const montoPorMes = mesesSinIntereses > 0 ? Math.round((monto / mesesSinIntereses) * 100) / 100 : 0;

    let prestamoPayload = null;
    if ($('n-es-prestamo').checked) {
      const pMonto = parseFloat($('n-p-monto').value);
      const esParejaP = $('n-p-contraparte').value === 'pareja';
      const nombreExterno = esParejaP ? null : ($('n-p-nombre-externo').value.trim() || null);

      if (!pMonto || pMonto <= 0) { mostrarMensajeN('⚠️ Indica el monto del préstamo.', 'error'); return; }
      if (!esParejaP && !nombreExterno) { mostrarMensajeN('⚠️ Escribe el nombre de la persona externa.', 'error'); return; }

      const otro = usuariosCacheN.find((u) => u.id !== Number(usuarioId)) || null;
      if (esParejaP && !otro) { mostrarMensajeN('⚠️ No se encontró a tu pareja en el sistema.', 'error'); return; }

      let acreedorId, deudorId;
      if ($('n-p-direccion').value === 'me_apoyan') {
        acreedorId = esParejaP ? otro.id : null;
        deudorId = Number(usuarioId);
      } else {
        acreedorId = Number(usuarioId);
        deudorId = esParejaP ? otro.id : null;
      }

      const formaPago = $('n-p-forma-pago').value;
      let mesesMsiP = null, montoPorMesP = null;
      if (formaPago === 'msi') {
        mesesMsiP = mesesSinIntereses;
        montoPorMesP = Math.round((pMonto / mesesMsiP) * 100) / 100;
      }

      prestamoPayload = {
        monto: pMonto, fecha, notas: descripcion,
        acreedor_id: acreedorId, deudor_id: deudorId, nombre_externo: nombreExterno,
        tipo_pago: formaPago, meses_msi: mesesMsiP, monto_por_mes: montoPorMesP,
      };
    }

    const payload = {
      usuario_id: Number(usuarioId),
      cuenta_id: tipoMedio === 'cuenta' ? Number(medioId) : null,
      tarjeta_id: esTarjeta ? Number(medioId) : null,
      categoria_id: Number(categoriaId),
      monto, fecha, descripcion, tipo, notas,
      meses_sin_intereses: mesesSinIntereses,
      monto_por_mes: montoPorMes,
    };

    nBtnGuardar.disabled = true;
    nBtnGuardar.textContent = 'Guardando...';

    try {
      const res = await fetch('/api/data', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const cuerpo = await res.json().catch(() => ({}));
        throw new Error(cuerpo.error || `HTTP ${res.status}`);
      }
      const { id: txId } = await res.json();
      let mensajeFinal = '✅ ¡Transacción guardada con éxito!';
      let tipoFinal = 'exito';

      if (prestamoPayload) {
        const resP = await fetch('/api/prestamo', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...prestamoPayload, transaccion_id: txId }),
        });
        if (!resP.ok) {
          const cuerpoP = await resP.json().catch(() => ({}));
          mensajeFinal = '⚠️ La transacción se guardó, pero el préstamo falló: ' + (cuerpoP.error || `HTTP ${resP.status}`);
          tipoFinal = 'error';
        } else {
          mensajeFinal = '✅ ¡Transacción y préstamo guardados con éxito!';
        }
      }

      mostrarMensajeN(mensajeFinal, tipoFinal);
      const usuarioAntes = $('n-usuario').value;
      $('form-nueva').reset();
      $('n-fecha').valueAsDate = new Date();
      $('n-usuario').value = usuarioAntes;
      $('n-tipo').value = 'gasto';
      document.querySelectorAll('#n-montos-rapidos .monto-btn').forEach((b) => b.classList.remove('activo'));
      resetearPrestamoN();
      await refrescarDependientesN();
      cargarHistorial();
    } catch (err) {
      mostrarMensajeN('❌ Error al guardar: ' + err.message, 'error');
    } finally {
      nBtnGuardar.disabled = false;
      nBtnGuardar.textContent = 'Guardar transacción';
    }
  });
})();

// ══════════════════════════════════════════════════════════════════════
// HISTORIAL
// ══════════════════════════════════════════════════════════════════════

let usuariosCacheGlobal = [];
let txsActuales = [];
let expandActual = null; // { id, tipo: 'editar' | 'abonar' }

function ultimoDiaMes(anio, mes) {
  return new Date(Date.UTC(anio, mes, 0)).getUTCDate();
}
function rangoDelMes(anio, mes) {
  const ultimo = ultimoDiaMes(anio, mes);
  return {
    desde: `${anio}-${String(mes).padStart(2, '0')}-01`,
    hasta: `${anio}-${String(mes).padStart(2, '0')}-${String(ultimo).padStart(2, '0')}`,
  };
}
function ultimosMeses(n) {
  const hoy = new Date();
  let mes = hoy.getMonth() + 1;
  let anio = hoy.getFullYear();
  const meses = [];
  for (let i = 0; i < n; i++) {
    meses.push({ anio, mes });
    mes -= 1;
    if (mes <= 0) { mes += 12; anio -= 1; }
  }
  return meses;
}

function montoOrd(t) {
  return (t.meses_sin_intereses > 0) ? (t.monto_por_mes || t.monto) : t.monto;
}
function ordenarTxs(txs, orden) {
  const c = [...txs];
  if (orden === 'reciente_agregada') c.sort((a, b) => (b.id || 0) - (a.id || 0));
  else if (orden === 'fecha_reciente') c.sort((a, b) => (a.fecha !== b.fecha ? (a.fecha < b.fecha ? 1 : -1) : (b.id || 0) - (a.id || 0)));
  else if (orden === 'fecha_antigua') c.sort((a, b) => (a.fecha !== b.fecha ? (a.fecha < b.fecha ? -1 : 1) : (a.id || 0) - (b.id || 0)));
  else if (orden === 'monto_mayor') c.sort((a, b) => montoOrd(b) - montoOrd(a));
  else if (orden === 'monto_menor') c.sort((a, b) => montoOrd(a) - montoOrd(b));
  else if (orden === 'categoria_az') c.sort((a, b) => (a.categoria_nombre || '').localeCompare(b.categoria_nombre || ''));
  else if (orden === 'usuario_az') c.sort((a, b) => (a.usuario_nombre || '').localeCompare(b.usuario_nombre || ''));
  return c;
}

async function cargarCategoriasEnSelect(selectId, tipo) {
  const cats = window.__categoriasTodas.filter((c) => c.tipo === tipo);
  $(selectId).innerHTML = cats.map((c) => `<option value="${c.id}">${c.icono || '📦'} ${c.nombre}</option>`).join('');
}
async function cargarMediosEnSelect(selectId, usuarioId) {
  const res = await authFetch(`/api/catalogos?usuario_id=${usuarioId}`);
  const datos = await res.json();
  const oc = datos.cuentas.map((c) => `<option value="cuenta:${c.id}">🏦 ${c.nombre}</option>`).join('');
  const ot = datos.tarjetas.map((t) => `<option value="tarjeta:${t.id}">💳 ${t.nombre} (${t.banco})</option>`).join('');
  $(selectId).innerHTML = oc + ot;
}

async function inicializarFiltros() {
  const res = await authFetch('/api/catalogos');
  const datos = await res.json();
  usuariosCacheGlobal = datos.usuarios;
  window.__categoriasTodas = datos.categorias;

  $('f-usuario').innerHTML = '<option value="">Todos</option>' +
    datos.usuarios.map((u) => `<option value="${u.id}">${u.nombre}</option>`).join('');
  $('f-categoria').innerHTML = '<option value="">Todas las categorías</option>' +
    datos.categorias.map((c) => `<option value="${c.id}">${c.icono || '📦'} ${c.nombre}</option>`).join('');
  actualizarFiltrosMedio(datos.cuentas, datos.tarjetas);

  const meses = ultimosMeses(6);
  $('f-mes').innerHTML = meses.map((m) => `<option value="${m.anio}-${m.mes}">${MESES_ES[m.mes]} ${m.anio}</option>`).join('');

  await cargarNuevaTransaccion();
}

function actualizarFiltrosMedio(cuentas, tarjetas) {
  $('f-cuenta').innerHTML = '<option value="">Todas las cuentas</option>' +
    cuentas.map((c) => `<option value="${c.id}">${c.nombre} (${c.tipo})</option>`).join('');
  $('f-tarjeta').innerHTML = '<option value="">Todas las tarjetas</option>' +
    tarjetas.map((t) => `<option value="${t.id}">${t.nombre} — ${t.banco}</option>`).join('');
}

$('f-usuario').addEventListener('change', async () => {
  const uid = $('f-usuario').value;
  const res = await authFetch(`/api/catalogos${uid ? `?usuario_id=${uid}` : ''}`);
  const datos = await res.json();
  actualizarFiltrosMedio(datos.cuentas, datos.tarjetas);
  cargarHistorial();
});
['f-mes', 'f-categoria', 'f-cuenta', 'f-tarjeta'].forEach((id) => {
  $(id).addEventListener('change', () => cargarHistorial());
});
$('f-orden').addEventListener('change', () => renderHistorial());

async function cargarHistorial() {
  const usuarioId = $('f-usuario').value || null;
  const [anioStr, mesStr] = $('f-mes').value.split('-');
  const { desde, hasta } = rangoDelMes(Number(anioStr), Number(mesStr));
  const categoriaId = $('f-categoria').value || null;
  let cuentaId = $('f-cuenta').value || null;
  let tarjetaId = $('f-tarjeta').value || null;

  const historialMensaje = $('historial-mensaje');
  historialMensaje.className = 'mensaje';

  if (cuentaId && tarjetaId) tarjetaId = null;

  const params = new URLSearchParams({ desde, hasta });
  if (usuarioId) params.set('usuario_id', usuarioId);
  if (categoriaId) params.set('categoria_id', categoriaId);
  if (cuentaId) params.set('cuenta_id', cuentaId);
  if (tarjetaId) params.set('tarjeta_id', tarjetaId);

  try {
    const res = await authFetch(`/api/transacciones?${params.toString()}`);
    if (!res.ok) {
      const cuerpo = await res.json().catch(() => ({}));
      throw new Error(cuerpo.error || `HTTP ${res.status}`);
    }
    const { transacciones } = await res.json();
    txsActuales = transacciones;
    expandActual = null;
    await renderHistorial();
  } catch (err) {
    historialMensaje.textContent = '❌ ' + err.message;
    historialMensaje.className = 'mensaje error';
  }
}

async function renderHistorial() {
  const txs = ordenarTxs(txsActuales, $('f-orden').value);

  const gSum = txs.filter((t) => t.tipo === 'gasto').reduce((s, t) => s + montoOrd(t), 0);
  const iSum = txs.filter((t) => t.tipo === 'ingreso').reduce((s, t) => s + t.monto, 0);
  $('metricas').innerHTML = `
    <div class="metrica"><div class="valor" style="color:#E24B4A">${fmt(gSum)}</div><div class="etiqueta">Gastos</div></div>
    <div class="metrica"><div class="valor" style="color:#639922">${fmt(iSum)}</div><div class="etiqueta">Ingresos</div></div>
    <div class="metrica"><div class="valor">${fmt(iSum - gSum)}</div><div class="etiqueta">Balance</div></div>
  `;

  if (txs.length === 0) {
    $('lista-transacciones').innerHTML = '<div class="vacio">No hay transacciones con estos filtros.</div>';
    return;
  }

  const idsReales = [...new Set(txs.filter((t) => !t.es_proyeccion).map((t) => t.id))];
  let prestamosPorTx = {};
  if (idsReales.length > 0) {
    const res = await authFetch(`/api/prestamo-abono?tx_ids=${idsReales.join(',')}`);
    if (res.ok) prestamosPorTx = (await res.json()).porTransaccion;
  }

  $('lista-transacciones').innerHTML = txs.map((t) => renderFilaTx(t, prestamosPorTx[t.id])).join('');
  adjuntarListenersFilas();
}

function renderFilaTx(t, prestamo) {
  const claseColor = t.tipo === 'gasto' ? 'gasto' : 'ingreso';
  const signo = t.tipo === 'gasto' ? '-' : '+';
  const tagMsi = t.meses_sin_intereses > 0
    ? `<span class="tag-msi">${t.meses_sin_intereses}MSI · ${fmt(t.monto_por_mes)}/mes</span>` : '';
  const notaHtml = t.notas ? `<div class="tx-nota">📝 ${escapeHtml(t.notas)}</div>` : '';
  const medio = t.tarjeta_nombre || t.cuenta_nombre || '—';
  const montoHtml = (t.meses_sin_intereses > 0 && !t.es_proyeccion)
    ? `${signo}${fmt(t.monto_por_mes)}/mes<div style="font-size:11px;color:gray;font-weight:400">Total: ${fmt(t.monto)}</div>`
    : `${signo}${fmt(t.monto)}`;

  const prestamoHtml = (prestamo && !t.es_proyeccion)
    ? `<div class="tag-prestamo">💸 Préstamo · resta ${fmt(prestamo.monto_pendiente)}
         <button type="button" class="btn-abonar" data-abonar="${t.id}" data-prestamo="${prestamo.id}">Abonar</button>
       </div>`
    : '';

  const acciones = t.es_proyeccion
    ? `<button type="button" data-editar="${t.id}" title="Editar cargo original">✏️</button>`
    : `<button type="button" data-editar="${t.id}">✏️</button>
       <button type="button" data-borrar="${t.id}">🗑</button>`;

  return `
    <div class="tx-item">
      <div class="tx-row">
        <div class="tx-info">
          <div class="tx-desc">${escapeHtml(t.descripcion)}${tagMsi}</div>
          ${notaHtml}
          <div class="tx-sub">${t.categoria_icono || '📦'} ${t.categoria_nombre || '—'} · ${medio} · ${t.usuario_nombre}</div>
          ${prestamoHtml}
        </div>
        <div class="tx-monto ${claseColor}">${montoHtml}</div>
        <div class="tx-fecha">${t.fecha}</div>
        <div class="tx-acciones">${acciones}</div>
      </div>
      <div id="expand-${t.id}"></div>
    </div>
  `;
}

function cerrarExpandActual() {
  if (!expandActual) return;
  const slot = $(`expand-${expandActual.id}`);
  if (slot) { slot.innerHTML = ''; slot.classList.remove('caja-edicion', 'caja-abono'); }
  expandActual = null;
}

function adjuntarListenersFilas() {
  document.querySelectorAll('[data-editar]').forEach((btn) => {
    btn.addEventListener('click', () => abrirEdicion(Number(btn.dataset.editar)));
  });
  document.querySelectorAll('[data-borrar]').forEach((btn) => {
    btn.addEventListener('click', () => borrarTx(Number(btn.dataset.borrar)));
  });
  document.querySelectorAll('[data-abonar]').forEach((btn) => {
    btn.addEventListener('click', () => abrirAbono(Number(btn.dataset.abonar), Number(btn.dataset.prestamo)));
  });
}

async function borrarTx(id) {
  if (!confirm('¿Eliminar esta transacción?')) return;
  const res = await authFetch(`/api/transacciones?id=${id}`, { method: 'DELETE' });
  const cuerpo = await res.json().catch(() => ({}));
  if (!res.ok) {
    alert(cuerpo.error || 'No se pudo eliminar.');
    return;
  }
  cargarHistorial();
}

// ── Edición inline ──

function plantillaFormularioEdicion() {
  return `
    <form id="e-form">
      <div class="grid2">
        <div><label>Tipo</label>
          <select id="e-tipo"><option value="gasto">Gasto</option><option value="ingreso">Ingreso</option></select>
        </div>
        <div><label>Categoría</label><select id="e-categoria"></select></div>
      </div>
      <label>Descripción</label>
      <input type="text" id="e-descripcion" required>
      <div class="grid2">
        <div><label>Monto</label><input type="number" id="e-monto" step="0.01" min="0.01" required></div>
        <div><label>Fecha</label><input type="date" id="e-fecha" required></div>
      </div>
      <label>Medio</label>
      <select id="e-medio"></select>
      <div id="e-msi-box" class="msi-box oculto">
        <label class="msi-check"><input type="checkbox" id="e-usar-msi"> Meses sin intereses</label>
        <select id="e-msi-meses" class="oculto">
          <option value="3">3</option><option value="6">6</option><option value="9">9</option>
          <option value="12">12</option><option value="18">18</option><option value="20">20</option><option value="24">24</option>
        </select>
      </div>
      <label>Notas</label>
      <textarea id="e-notas"></textarea>
      <div style="display:flex; gap:10px">
        <button type="submit" class="btn-primario">Guardar cambios</button>
        <button type="button" class="btn-secundario" id="e-cancelar">Cancelar</button>
      </div>
      <div class="mensaje" id="e-mensaje"></div>
    </form>
  `;
}

async function abrirEdicion(id) {
  if (expandActual && expandActual.id === id && expandActual.tipo === 'editar') { cerrarExpandActual(); return; }
  cerrarExpandActual();

  // Se relee la transacción original de la BD (no la copia en memoria): si esta fila
  // es una proyección MSI, txsActuales trae el monto mensual sobreescrito, no el
  // monto total real — editar sobre eso corrompería el monto en la base de datos.
  const resOriginal = await authFetch(`/api/transacciones?id=${id}`);
  if (!resOriginal.ok) return;
  const t = (await resOriginal.json()).transaccion;
  if (!t) return;
  expandActual = { id, tipo: 'editar' };

  const slot = $(`expand-${id}`);
  slot.classList.add('caja-edicion');
  slot.innerHTML = plantillaFormularioEdicion();

  await Promise.all([
    cargarCategoriasEnSelect('e-categoria', t.tipo),
    cargarMediosEnSelect('e-medio', t.usuario_id),
  ]);

  $('e-tipo').value = t.tipo;
  $('e-categoria').value = t.categoria_id;
  $('e-descripcion').value = t.descripcion;
  $('e-monto').value = t.monto;
  $('e-fecha').value = t.fecha;
  $('e-medio').value = t.tarjeta_id ? `tarjeta:${t.tarjeta_id}` : `cuenta:${t.cuenta_id}`;
  $('e-notas').value = t.notas || '';

  const esTarjetaE = () => $('e-medio').value.startsWith('tarjeta:');
  function actualizarMsiE() {
    $('e-msi-box').classList.toggle('oculto', !esTarjetaE());
    if (!esTarjetaE()) { $('e-usar-msi').checked = false; $('e-msi-meses').classList.add('oculto'); }
  }
  actualizarMsiE();
  if (t.meses_sin_intereses > 0) {
    $('e-usar-msi').checked = true;
    $('e-msi-meses').value = t.meses_sin_intereses;
    $('e-msi-meses').classList.remove('oculto');
  }

  $('e-medio').addEventListener('change', actualizarMsiE);
  $('e-usar-msi').addEventListener('change', () => {
    $('e-msi-meses').classList.toggle('oculto', !$('e-usar-msi').checked);
  });
  $('e-tipo').addEventListener('change', () => cargarCategoriasEnSelect('e-categoria', $('e-tipo').value));
  $('e-cancelar').addEventListener('click', () => cerrarExpandActual());

  $('e-form').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const [tipoMedio, medioId] = $('e-medio').value.split(':');
    const monto = parseFloat($('e-monto').value);
    const meses = (tipoMedio === 'tarjeta' && $('e-usar-msi').checked) ? Number($('e-msi-meses').value) : 0;

    const payload = {
      id,
      descripcion: $('e-descripcion').value.trim(),
      monto,
      fecha: $('e-fecha').value,
      tipo: $('e-tipo').value,
      categoria_id: Number($('e-categoria').value),
      cuenta_id: tipoMedio === 'cuenta' ? Number(medioId) : null,
      tarjeta_id: tipoMedio === 'tarjeta' ? Number(medioId) : null,
      notas: $('e-notas').value.trim(),
      meses_sin_intereses: meses,
    };

    const btn = $('e-form').querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const res = await authFetch('/api/transacciones', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      const cuerpo = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(cuerpo.error || `HTTP ${res.status}`);
      cerrarExpandActual();
      cargarHistorial();
    } catch (err) {
      $('e-mensaje').textContent = '❌ ' + err.message;
      $('e-mensaje').className = 'mensaje error';
      btn.disabled = false;
    }
  });
}

// ── Abono inline ──

function plantillaFormularioAbono(prestamo) {
  return `
    <form id="a-form">
      <div class="grid2">
        <div><label>Monto</label><input type="number" id="a-monto" step="0.01" min="0.01" value="${prestamo.monto_pendiente}" required></div>
        <div><label>Fecha</label><input type="date" id="a-fecha" required></div>
      </div>
      <label>Tipo de pago</label>
      <select id="a-tipo">
        <option value="pago">Pago normal</option>
        <option value="adelantado">Pago adelantado</option>
        <option value="condonado">Pago condonado</option>
      </select>
      <label>Notas (opcional)</label>
      <input type="text" id="a-notas">
      <div style="display:flex; gap:10px">
        <button type="submit" class="btn-primario">Guardar abono</button>
        <button type="button" class="btn-secundario" id="a-cancelar">Cancelar</button>
      </div>
      <div class="mensaje" id="a-mensaje"></div>
    </form>
  `;
}

async function abrirAbono(txId, prestamoId) {
  if (expandActual && expandActual.id === txId && expandActual.tipo === 'abonar') { cerrarExpandActual(); return; }
  cerrarExpandActual();

  const res = await authFetch(`/api/prestamo-abono?tx_ids=${txId}`);
  const datos = await res.json();
  const prestamo = datos.porTransaccion[txId];
  if (!prestamo) return;

  expandActual = { id: txId, tipo: 'abonar' };
  const slot = $(`expand-${txId}`);
  slot.classList.add('caja-abono');
  slot.innerHTML = plantillaFormularioAbono(prestamo);
  $('a-fecha').valueAsDate = new Date();

  $('a-cancelar').addEventListener('click', () => cerrarExpandActual());
  $('a-form').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const btn = $('a-form').querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const res2 = await authFetch('/api/prestamo-abono', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prestamo_id: prestamoId,
          monto: parseFloat($('a-monto').value),
          fecha: $('a-fecha').value,
          notas: $('a-notas').value.trim(),
          tipo: $('a-tipo').value,
        }),
      });
      const cuerpo = await res2.json().catch(() => ({}));
      if (!res2.ok) throw new Error(cuerpo.error || `HTTP ${res2.status}`);
      cerrarExpandActual();
      cargarHistorial();
    } catch (err) {
      $('a-mensaje').textContent = '❌ ' + err.message;
      $('a-mensaje').className = 'mensaje error';
      btn.disabled = false;
    }
  });
}

// ══════════════════════════════════════════════════════════════════════
// Arranque
// ══════════════════════════════════════════════════════════════════════

(async function iniciar() {
  await inicializarFiltros();
  await cargarHistorial();
})();
