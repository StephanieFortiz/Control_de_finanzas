let uidActivo = null;
let tarjetasCache = [];
let tarjetaActivaId = null;

const COLOR_ALERTA = { urgente: '#E24B4A', proximo: '#EF9F27', ok: '#639922' };

function labelAlerta(dias) {
  if (dias < 0) return `Venció hace ${Math.abs(dias)} días`;
  if (dias === 0) return 'Vence hoy';
  return `Vence en ${dias} días`;
}
function fmtFechaCorta(iso) {
  const [a, m, d] = iso.split('-');
  return `${d}/${m}`;
}
function fmtFechaLarga(iso) {
  const [a, m, d] = iso.split('-');
  return `${d}/${m}/${a}`;
}

async function inicializar() {
  const res = await authFetch('/api/catalogos');
  const datos = await res.json();

  const guardado = obtenerUsuarioActivoGuardado();
  const valido = datos.usuarios.some((u) => String(u.id) === guardado);
  uidActivo = valido ? guardado : (datos.usuarios[0] && String(datos.usuarios[0].id));

  $('viendo-como').innerHTML = datos.usuarios.map((u) => `<option value="${u.id}">${u.nombre}</option>`).join('');
  $('viendo-como').value = uidActivo;

  $('viendo-como').addEventListener('change', () => {
    uidActivo = $('viendo-como').value;
    guardarUsuarioActivo(uidActivo);
    cargarTarjetas();
  });

  await cargarTarjetas();
}

async function cargarTarjetas() {
  const res = await authFetch(`/api/tarjetas?usuario_id=${uidActivo}`);
  const datos = await res.json();
  tarjetasCache = datos.tarjetas;

  if (tarjetasCache.length === 0) {
    $('tabs-tarjeta').innerHTML = '';
    $('contenido-tarjeta').innerHTML = '<div class="vacio">No tienes tarjetas registradas. Agrégalas en ⚙️ Configuración (app clásica).</div>';
    return;
  }

  tarjetaActivaId = tarjetasCache[0].id;
  $('tabs-tarjeta').innerHTML = tarjetasCache.map((t) =>
    `<button type="button" class="tab-tarjeta-btn ${t.id === tarjetaActivaId ? 'activo' : ''}" data-tarjeta="${t.id}">${escapeHtml(t.nombre)}</button>`
  ).join('');

  document.querySelectorAll('[data-tarjeta]').forEach((btn) => {
    btn.addEventListener('click', () => {
      tarjetaActivaId = Number(btn.dataset.tarjeta);
      document.querySelectorAll('[data-tarjeta]').forEach((b) => b.classList.remove('activo'));
      btn.classList.add('activo');
      cargarEstadoTarjeta();
    });
  });

  await cargarEstadoTarjeta();
}

let estadoActual = null;

async function cargarEstadoTarjeta() {
  $('contenido-tarjeta').innerHTML = '<div class="vacio">Cargando...</div>';
  const res = await authFetch(`/api/tarjetas?usuario_id=${uidActivo}&tarjeta_id=${tarjetaActivaId}`);
  if (!res.ok) {
    $('contenido-tarjeta').innerHTML = '<div class="vacio">No se pudo cargar la tarjeta.</div>';
    return;
  }
  estadoActual = await res.json();
  renderTarjeta();
}

function renderTarjeta() {
  const { tarjeta, estado, grupos, prestamosPorTx } = estadoActual;
  const periodo = estado.periodo_actual;
  const color = COLOR_ALERTA[estado.alerta];

  let html = `
    <div class="encabezado-flex">
      <div class="encabezado-info">
        <div class="banco">${escapeHtml(tarjeta.banco)} · Corte día <strong>${tarjeta.dia_corte}</strong> · Pago día <strong>${tarjeta.dia_pago}</strong></div>
        <div class="periodo">Período actual: ${periodo.periodoLabel} (${fmtFechaCorta(periodo.fechaInicio)} → ${fmtFechaLarga(periodo.fechaCorte)})</div>
      </div>
      <div class="encabezado-alerta" style="color:${color}">
        ${labelAlerta(estado.dias_para_pago)}
        <div class="fecha-pago">Pago: ${fmtFechaLarga(estado.fecha_pago)}</div>
      </div>
    </div>

    <div class="metricas">
      <div class="metrica"><div class="valor">${fmt(estado.total_periodo)}</div><div class="etiqueta">Cargos este período</div></div>
      <div class="metrica"><div class="valor">${fmt(Math.max(tarjeta.limite - estado.total_periodo, 0))}</div><div class="etiqueta">Límite disponible</div></div>
      <div class="metrica"><div class="valor">${estado.porcentaje_limite}%</div><div class="etiqueta">% del límite usado</div></div>
      <div class="metrica"><div class="valor">${estado.dias_para_corte}</div><div class="etiqueta">Días para corte</div></div>
    </div>
  `;

  if (tarjeta.limite > 0) {
    const pct = Math.min(estado.porcentaje_limite / 100, 1.0);
    const colorBarra = pct > 0.85 ? '#E24B4A' : pct > 0.60 ? '#EF9F27' : '#639922';
    html += `<div class="barra-limite"><div style="width:${pct * 100}%; background:${colorBarra}"></div></div>`;
  }

  html += `<h3 class="subtitulo">Cargos en ${periodo.periodoLabel}</h3>`;
  const txsActuales = [...estado.transacciones].sort((a, b) => (a.fecha < b.fecha ? 1 : -1));
  if (txsActuales.length === 0) {
    html += '<div class="vacio">Sin cargos en este período aún.</div>';
  } else {
    html += txsActuales.map((t) => renderCargoFila(t, prestamosPorTx, false, 'actual')).join('');
  }

  html += '<h3 class="subtitulo">Historial de estados de cuenta</h3>';
  const labels = Object.keys(grupos);
  if (labels.length === 0) {
    html += '<div class="vacio">Sin historial disponible.</div>';
  } else {
    html += labels.map((label) => {
      const g = grupos[label];
      const esActual = label === periodo.periodoLabel;
      const fechaPagoGrupo = calcularFechaPago(g.fecha_corte, tarjeta.dia_pago);
      const encabezado = `${label}${esActual ? ' · (período actual)' : ''} — Total: ${fmt(g.total)} · Corte: ${fmtFechaLarga(g.fecha_corte)} · Pago límite: ${fmtFechaLarga(fechaPagoGrupo)}`;
      const idGrupo = `grupo-${label.replace(/\s+/g, '-')}`;
      const cuerpo = g.transacciones.length === 0
        ? '<div class="vacio">Sin transacciones.</div>'
        : [...g.transacciones].sort((a, b) => (a.fecha < b.fecha ? 1 : -1))
            .map((t) => renderCargoFila(t, prestamosPorTx, true, `hist_${label}`)).join('');
      return `
        <button type="button" class="grupo-header" data-grupo="${idGrupo}">${escapeHtml(encabezado)}</button>
        <div class="grupo-cuerpo ${esActual ? '' : 'oculto'}" id="${idGrupo}">${cuerpo}</div>
      `;
    }).join('');
  }

  $('contenido-tarjeta').innerHTML = html;
  adjuntarListeners();
}

function renderCargoFila(t, prestamosPorTx, mostrarEditar, contexto) {
  const esProyeccion = !!t.es_proyeccion;
  let msiTag = '';
  if (t.meses_sin_intereses > 0) {
    msiTag = esProyeccion
      ? `<span class="tag-msi-proj">MSI ${t.mensualidad_num}/${t.meses_sin_intereses} · proyectado</span>`
      : `<span class="tag-msi">${t.meses_sin_intereses}MSI</span>`;
  }
  const notaHtml = t.notas ? `<div class="cargo-nota">📝 ${escapeHtml(t.notas)}</div>` : '';
  const icono = esProyeccion ? '🔄' : (t.categoria_icono || '📦');

  const montoHtml = t.meses_sin_intereses > 0
    ? `-${fmt(t.monto_por_mes)}/mes<div class="total">Total: ${fmt(t.monto_original != null ? t.monto_original : t.monto)}</div>`
    : `-${fmt(t.monto)}`;

  const claveAjuste = `aj_${contexto}_${t.id}_${t.mensualidad_num}`;
  const btnEditar = (esProyeccion && mostrarEditar)
    ? `<button type="button" data-ajustar="${claveAjuste}" data-tx="${t.id}" data-mes="${t.mensualidad_num}" data-monto="${t.monto_por_mes}">✏️</button>`
    : '';

  const prest = !esProyeccion ? prestamosPorTx[t.id] : null;
  const claveAbono = `abn_tar_${contexto}_${t.id}`;
  const prestamoHtml = prest
    ? `<div class="tag-prestamo">💸 Préstamo · resta ${fmt(prest.monto_pendiente)}
         <button type="button" class="btn-abonar-tar" data-abonar="${claveAbono}" data-prestamo="${prest.id}" data-sugerido="${prest.monto_por_mes || prest.monto_pendiente}">Abonar</button>
       </div>`
    : '';

  return `
    <div class="cargo-fila">
      <div class="cargo-info">
        <div class="cargo-desc">${icono} <strong>${escapeHtml(t.descripcion)}</strong>${msiTag}</div>
        ${notaHtml}
        ${prestamoHtml}
        <div id="expand-${claveAjuste}"></div>
        <div id="expand-${claveAbono}"></div>
      </div>
      <div class="cargo-monto">${montoHtml}</div>
      <div class="cargo-fecha">${t.fecha}</div>
      <div class="cargo-acciones">${btnEditar}</div>
    </div>
  `;
}

function adjuntarListeners() {
  document.querySelectorAll('[data-grupo]').forEach((btn) => {
    btn.addEventListener('click', () => {
      $(btn.dataset.grupo).classList.toggle('oculto');
    });
  });
  document.querySelectorAll('[data-ajustar]').forEach((btn) => {
    btn.addEventListener('click', () => toggleAjuste(btn.dataset.ajustar, Number(btn.dataset.tx), Number(btn.dataset.mes), parseFloat(btn.dataset.monto)));
  });
  document.querySelectorAll('[data-abonar]').forEach((btn) => {
    btn.addEventListener('click', () => toggleAbono(btn.dataset.abonar, Number(btn.dataset.prestamo), parseFloat(btn.dataset.sugerido)));
  });
}

function toggleAjuste(clave, txId, mensualidadNum, montoActual) {
  const slot = $(`expand-${clave}`);
  if (slot.innerHTML) { slot.innerHTML = ''; return; }

  slot.classList.add('caja-ajuste');
  slot.innerHTML = `
    <form id="form-${clave}">
      <label>Ajuste de monto — mensualidad ${mensualidadNum}</label>
      <input type="number" id="input-${clave}" step="0.01" min="0.01" value="${montoActual}" required>
      <div style="display:flex; gap:8px">
        <button type="submit" class="btn-primario">Guardar ajuste</button>
        <button type="button" class="btn-secundario" id="cancelar-${clave}">Cancelar</button>
      </div>
      <div class="mensaje" id="mensaje-${clave}"></div>
    </form>
  `;
  $(`cancelar-${clave}`).addEventListener('click', () => { slot.innerHTML = ''; });
  $(`form-${clave}`).addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const btn = ev.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const res = await authFetch(`/api/tarjetas?usuario_id=${uidActivo}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transaccion_id: txId, mensualidad_num: mensualidadNum, monto: parseFloat($(`input-${clave}`).value) }),
      });
      const cuerpo = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(cuerpo.error || `HTTP ${res.status}`);
      slot.innerHTML = '';
      cargarEstadoTarjeta();
    } catch (err) {
      const m = $(`mensaje-${clave}`);
      m.textContent = '❌ ' + err.message;
      m.className = 'mensaje error';
      btn.disabled = false;
    }
  });
}

function toggleAbono(clave, prestamoId, montoSugerido) {
  const slot = $(`expand-${clave}`);
  if (slot.innerHTML) { slot.innerHTML = ''; return; }

  slot.classList.add('caja-abono');
  slot.innerHTML = `
    <form id="form-${clave}">
      <div class="grid2">
        <div><label>Monto</label><input type="number" id="monto-${clave}" step="0.01" min="0.01" value="${montoSugerido}" required></div>
        <div><label>Fecha</label><input type="date" id="fecha-${clave}" required></div>
      </div>
      <label>Tipo</label>
      <select id="tipo-${clave}">
        <option value="pago">Pago normal</option>
        <option value="adelantado">Pago adelantado</option>
        <option value="condonado">Pago condonado</option>
      </select>
      <label>Notas (opcional)</label>
      <input type="text" id="notas-${clave}">
      <div style="display:flex; gap:8px">
        <button type="submit" class="btn-primario">Guardar abono</button>
        <button type="button" class="btn-secundario" id="cancelar-${clave}">Cancelar</button>
      </div>
      <div class="mensaje" id="mensaje-${clave}"></div>
    </form>
  `;
  $(`fecha-${clave}`).valueAsDate = new Date();
  $(`cancelar-${clave}`).addEventListener('click', () => { slot.innerHTML = ''; });
  $(`form-${clave}`).addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const btn = ev.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const res = await authFetch('/api/prestamo-abono', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prestamo_id: prestamoId,
          monto: parseFloat($(`monto-${clave}`).value),
          fecha: $(`fecha-${clave}`).value,
          notas: $(`notas-${clave}`).value.trim(),
          tipo: $(`tipo-${clave}`).value,
        }),
      });
      const cuerpo = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(cuerpo.error || `HTTP ${res.status}`);
      slot.innerHTML = '';
      cargarEstadoTarjeta();
    } catch (err) {
      const m = $(`mensaje-${clave}`);
      m.textContent = '❌ ' + err.message;
      m.className = 'mensaje error';
      btn.disabled = false;
    }
  });
}

inicializar();
