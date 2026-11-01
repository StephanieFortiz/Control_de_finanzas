let usuariosCache = [];
let uidActivo = null;

const TIPO_PAGO_LABEL = { unico: 'Pago único', abonos: 'Abonos libres' };
function tipoPagoLabel(p) {
  if (p.tipo_pago === 'msi') return `MSI · ${p.meses_msi || '?'} meses`;
  return TIPO_PAGO_LABEL[p.tipo_pago] || 'Abonos libres';
}

function contraparte(p, uid) {
  if (p.acreedor_id === uid) return p.deudor_nombre || p.nombre_externo || 'Externo';
  return p.acreedor_nombre || p.nombre_externo || 'Externo';
}

// ── Inicialización de "Viendo como" ──

async function inicializar() {
  const res = await authFetch('/api/catalogos');
  const datos = await res.json();
  usuariosCache = datos.usuarios;

  const guardado = obtenerUsuarioActivoGuardado();
  const valido = usuariosCache.some((u) => String(u.id) === guardado);
  uidActivo = valido ? guardado : (usuariosCache[0] && String(usuariosCache[0].id));

  $('viendo-como').innerHTML = usuariosCache.map((u) => `<option value="${u.id}">${u.nombre}</option>`).join('');
  $('viendo-como').value = uidActivo;

  $('viendo-como').addEventListener('change', () => {
    uidActivo = $('viendo-como').value;
    guardarUsuarioActivo(uidActivo);
    cargarTodo();
  });

  document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('activo'));
      btn.classList.add('activo');
      $('tab-pendientes').classList.toggle('oculto', btn.dataset.tab !== 'pendientes');
      $('tab-archivados').classList.toggle('oculto', btn.dataset.tab !== 'archivados');
    });
  });

  document.querySelectorAll('#filtro-direccion input').forEach((r) => {
    r.addEventListener('change', () => renderPendientes());
  });

  await cargarTodo();
}

let prestamosPendientesCache = [];

async function cargarTodo() {
  await Promise.all([cargarPendientes(), cargarArchivados()]);
}

async function cargarPendientes() {
  const res = await authFetch(`/api/prestamos?usuario_id=${uidActivo}&estado=pendiente`);
  const datos = await res.json();
  prestamosPendientesCache = datos.prestamos;
  renderPendientes();
}

function renderPendientes() {
  const uid = Number(uidActivo);
  const yoDebo = prestamosPendientesCache.filter((p) => p.deudor_id === uid);
  const meDeben = prestamosPendientesCache.filter((p) => p.acreedor_id === uid);

  $('metricas-pendientes').innerHTML = `
    <div class="metrica"><div class="valor" style="color:#E24B4A">${fmt(yoDebo.reduce((s, p) => s + p.monto_pendiente, 0))}</div><div class="etiqueta">Yo debo · ${yoDebo.length} préstamo(s)</div></div>
    <div class="metrica"><div class="valor" style="color:#639922">${fmt(meDeben.reduce((s, p) => s + p.monto_pendiente, 0))}</div><div class="etiqueta">Me deben · ${meDeben.length} préstamo(s)</div></div>
  `;

  const filtro = document.querySelector('#filtro-direccion input:checked').value;
  let lista = [];
  if (filtro === 'todos') lista = [...yoDebo.map((p) => [p, 'debo']), ...meDeben.map((p) => [p, 'me_deben'])];
  else if (filtro === 'debo') lista = yoDebo.map((p) => [p, 'debo']);
  else lista = meDeben.map((p) => [p, 'me_deben']);

  if (lista.length === 0) {
    $('lista-pendientes').innerHTML = '<div class="vacio">No hay préstamos en esta categoría.</div>';
    return;
  }

  $('lista-pendientes').innerHTML = lista.map(([p, dir]) => renderFilaPrestamo(p, uid, dir, true)).join('');
  adjuntarListeners($('lista-pendientes'));
}

async function cargarArchivados() {
  const uid = Number(uidActivo);
  const res = await authFetch(`/api/prestamos?usuario_id=${uidActivo}`);
  const datos = await res.json();
  const archivados = datos.prestamos.filter((p) => p.estado === 'pagado' || p.estado === 'cancelado');

  if (archivados.length === 0) {
    $('lista-archivados').innerHTML = '<div class="vacio">No hay préstamos archivados aún.</div>';
    return;
  }

  $('lista-archivados').innerHTML = archivados
    .map((p) => renderFilaPrestamo(p, uid, p.deudor_id === uid ? 'debo' : 'me_deben', false))
    .join('');
  adjuntarListeners($('lista-archivados'));
}

function renderFilaPrestamo(p, uid, direccion, puedeAbonar) {
  const montoPagado = Math.round((p.monto_original - p.monto_pendiente) * 100) / 100;
  const progreso = p.monto_original > 0 ? montoPagado / p.monto_original : 0;
  const cargo = p.tx_descripcion || p.notas || '—';
  const tarjetaStr = p.tx_tarjeta_nombre ? `${p.tx_tarjeta_nombre} (${p.tx_tarjeta_banco || ''})` : (p.tx_cuenta_nombre || '');
  const dirLabel = direccion === 'me_deben' ? '⬆️ Me deben' : '⬇️ Yo debo';
  const claseCompleta = progreso >= 1 ? 'completa' : '';

  const btnAbonar = (puedeAbonar && p.estado === 'pendiente')
    ? `<button type="button" class="btn-abonar-prestamo" data-abonar="${p.id}">💸 Abonar</button>` : '';
  const btnEliminar = (montoPagado === 0)
    ? `<button type="button" data-eliminar="${p.id}" title="Eliminar préstamo">🗑</button>` : '';

  return `
    <div class="prestamo-item" data-item-prestamo="${p.id}">
      <div class="prestamo-fila">
        <div class="prestamo-info">
          <div class="prestamo-cargo">${escapeHtml(cargo)}</div>
          <div class="prestamo-sub">${dirLabel} · <strong>${escapeHtml(contraparte(p, uid))}</strong> · ${tipoPagoLabel(p)}</div>
          <div class="prestamo-sub">📅 ${p.fecha}${tarjetaStr ? ' · 💳 ' + escapeHtml(tarjetaStr) : ''}</div>
          <button type="button" class="detalle-toggle" data-detalle="${p.id}">Ver detalle</button>
          <div id="detalle-${p.id}"></div>
        </div>
        <div class="prestamo-montos">
          <div><div class="valor">${fmt(p.monto_original)}</div><div class="etiqueta">Total</div></div>
          <div><div class="valor">${fmt(montoPagado)}</div><div class="etiqueta">Pagado</div></div>
          <div><div class="valor resta ${progreso >= 1 ? 'pagado' : ''}">${fmt(p.monto_pendiente)}</div><div class="etiqueta">Resta</div></div>
          <div style="min-width:110px">
            <div class="barra-progreso ${claseCompleta}"><div style="width:${Math.min(progreso, 1) * 100}%"></div></div>
            <div class="progreso-texto">${Math.round(progreso * 100)}% pagado</div>
          </div>
        </div>
        <div class="prestamo-acciones">${btnAbonar}${btnEliminar}</div>
      </div>
      <div id="abono-${p.id}"></div>
    </div>
  `;
}

// Solo dentro del contenedor recién renderizado: si se buscara en todo el documento,
// los botones de la otra lista recibirían un segundo listener y el click abriría y
// cerraría el formulario al mismo tiempo.
function adjuntarListeners(contenedor) {
  contenedor.querySelectorAll('[data-detalle]').forEach((btn) => {
    btn.addEventListener('click', () => toggleDetalle(Number(btn.dataset.detalle), btn));
  });
  contenedor.querySelectorAll('[data-eliminar]').forEach((btn) => {
    btn.addEventListener('click', () => eliminarPrestamo(Number(btn.dataset.eliminar)));
  });
  contenedor.querySelectorAll('[data-abonar]').forEach((btn) => {
    btn.addEventListener('click', () => toggleAbono(Number(btn.dataset.abonar)));
  });
}

// ── Detalle: pagos registrados + calendario MSI ──

async function toggleDetalle(prestamoId, btn) {
  const slot = $(`detalle-${prestamoId}`);
  if (slot.innerHTML) {
    slot.innerHTML = '';
    btn.textContent = 'Ver detalle';
    return;
  }
  btn.textContent = 'Ocultar detalle';

  const todos = [...prestamosPendientesCache];
  let p = todos.find((x) => x.id === prestamoId);
  if (!p) {
    const res = await authFetch(`/api/prestamos?usuario_id=${uidActivo}`);
    p = (await res.json()).prestamos.find((x) => x.id === prestamoId);
  }

  const res = await authFetch(`/api/prestamo-abono?prestamo_id=${prestamoId}`);
  const pagos = (await res.json()).pagos;

  let html = '<div class="detalle-box">';
  if (p.tipo_pago === 'msi' && p.meses_msi && p.monto_por_mes) {
    html += renderCalendarioMsi(p, pagos);
  }
  if (pagos.length > 0) {
    html += '<div style="font-weight:600; font-size:0.82rem; margin-bottom:4px">Abonos registrados:</div>';
    html += pagos.map((pg) => {
      const icono = { pago: '', adelantado: ' 🔼', condonado: ' ✦' }[pg.tipo] || '';
      const mes = pg.numero_mes ? ` · mes ${pg.numero_mes}` : '';
      const notas = pg.notas ? ` · 📝 ${escapeHtml(pg.notas)}` : '';
      return `<div class="pago-fila"><span>${pg.fecha}${mes}${icono}${notas}</span><span class="monto">${fmt(pg.monto)}</span></div>`;
    }).join('');
  } else {
    html += '<div style="font-size:0.8rem; color:gray">Sin abonos registrados aún.</div>';
  }
  html += '</div>';

  slot.innerHTML = html;
}

function renderCalendarioMsi(p, pagos) {
  const mesesPagados = new Set(pagos.filter((pg) => pg.numero_mes).map((pg) => pg.numero_mes));
  const mesesCondonados = new Set(pagos.filter((pg) => pg.numero_mes && pg.tipo === 'condonado').map((pg) => pg.numero_mes));

  let html = '<div style="font-weight:600; font-size:0.82rem; margin-bottom:6px">Calendario de pagos MSI:</div><div class="calendario">';
  for (let n = 1; n <= p.meses_msi; n++) {
    const fechaN = fechaMasNMeses(p.fecha, n - 1);
    const [anio, mes] = fechaN.split('-');
    const clase = mesesCondonados.has(n) ? 'condonado' : (mesesPagados.has(n) ? 'pagado' : '');
    const estado = mesesCondonados.has(n) ? '✦ Condonado' : (mesesPagados.has(n) ? '✓ Pagado' : fmt(p.monto_por_mes));
    html += `
      <div class="mes-msi ${clase}">
        <div class="num">Mes ${n}</div>
        <div class="fecha">${mes}/${anio}</div>
        <div class="estado">${estado}</div>
      </div>
    `;
  }
  html += '</div>';
  return html;
}

// ── Eliminar ──

async function eliminarPrestamo(id) {
  if (!confirm('¿Eliminar este préstamo? Esta acción no se puede deshacer.')) return;
  const res = await authFetch(`/api/prestamos?id=${id}`, { method: 'DELETE' });
  const cuerpo = await res.json().catch(() => ({}));
  if (!res.ok) {
    alert(cuerpo.error || 'No se pudo eliminar.');
    return;
  }
  cargarTodo();
}

// ── Abonar ──

function toggleAbono(prestamoId) {
  const slot = $(`abono-${prestamoId}`);
  if (slot.innerHTML) { slot.innerHTML = ''; return; }

  const p = prestamosPendientesCache.find((x) => x.id === prestamoId);
  if (!p) return;

  slot.classList.add('caja-abono');
  slot.innerHTML = `
    <form id="a-form-${prestamoId}">
      <div class="grid2">
        <div><label>Monto</label><input type="number" id="a-monto-${prestamoId}" step="0.01" min="0.01" value="${p.monto_por_mes || p.monto_pendiente}" required></div>
        <div><label>Fecha</label><input type="date" id="a-fecha-${prestamoId}" required></div>
      </div>
      <label>Tipo de pago</label>
      <select id="a-tipo-${prestamoId}">
        <option value="pago">Pago normal</option>
        <option value="adelantado">Pago adelantado</option>
        <option value="condonado">Pago condonado</option>
      </select>
      <label>Notas (opcional)</label>
      <input type="text" id="a-notas-${prestamoId}" style="width:100%">
      <div style="display:flex; gap:10px">
        <button type="submit" class="btn-primario">Guardar abono</button>
        <button type="button" class="btn-secundario" id="a-cancelar-${prestamoId}">Cancelar</button>
      </div>
      <div class="mensaje" id="a-mensaje-${prestamoId}"></div>
    </form>
  `;
  $(`a-fecha-${prestamoId}`).valueAsDate = new Date();
  $(`a-cancelar-${prestamoId}`).addEventListener('click', () => { slot.innerHTML = ''; });

  $(`a-form-${prestamoId}`).addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const btn = ev.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const res = await authFetch('/api/prestamo-abono', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prestamo_id: prestamoId,
          monto: parseFloat($(`a-monto-${prestamoId}`).value),
          fecha: $(`a-fecha-${prestamoId}`).value,
          notas: $(`a-notas-${prestamoId}`).value.trim(),
          tipo: $(`a-tipo-${prestamoId}`).value,
        }),
      });
      const cuerpo = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(cuerpo.error || `HTTP ${res.status}`);
      slot.innerHTML = '';
      cargarTodo();
    } catch (err) {
      const m = $(`a-mensaje-${prestamoId}`);
      m.textContent = '❌ ' + err.message;
      m.className = 'mensaje error';
      btn.disabled = false;
    }
  });
}

inicializar();
