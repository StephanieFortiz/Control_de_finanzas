const MESES_ES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
  'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

let uidActivo = null;
let mesesOpts = [];
let datosActuales = null;
let chipsTarjetaSeleccionadas = new Set();
let chipsCategoriaSeleccionadas = new Set();
const chartInstances = {};

function fmtMoneda(v) { return '$' + Number(v || 0).toLocaleString('es-MX', { maximumFractionDigits: 0 }); }
function fmtFechaCorta(iso) { const [a, m, d] = iso.split('-'); return `${d}/${m}`; }

function renderChart(id, opciones) {
  const dom = $(id);
  if (!dom) return;
  if (chartInstances[id]) chartInstances[id].dispose();
  const chart = echarts.init(dom);
  chart.setOption(opciones);
  chartInstances[id] = chart;
}
window.addEventListener('resize', () => {
  Object.values(chartInstances).forEach((c) => c.resize());
});

function ultimoDiaDeMesLocal(anio, mes) {
  return new Date(Date.UTC(anio, mes, 0)).getUTCDate();
}

function opcionesMeses(n = 13) {
  const hoy = new Date();
  const out = [];
  for (let i = -1; i < n; i++) {
    let mes = hoy.getMonth() + 1 - i;
    let anio = hoy.getFullYear();
    while (mes <= 0) { mes += 12; anio -= 1; }
    while (mes > 12) { mes -= 12; anio += 1; }
    out.push({ label: `${MESES_ES[mes]} ${anio}`, anio, mes, esActual: i === 0 });
  }
  return out;
}

// ── Inicialización ──

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
    cargarDashboard();
  });

  mesesOpts = opcionesMeses();
  $('f-mes').innerHTML = mesesOpts.map((m, i) => `<option value="${i}">${m.label}</option>`).join('');
  $('f-mes').value = String(mesesOpts.findIndex((m) => m.esActual));
  $('f-mes').addEventListener('change', () => cargarDashboard());

  await cargarDashboard();
}

async function cargarDashboard() {
  const mesSel = mesesOpts[Number($('f-mes').value)];
  const res = await authFetch(`/api/dashboard?usuario_id=${uidActivo}&anio=${mesSel.anio}&mes=${mesSel.mes}`);
  if (!res.ok) {
    $('metricas').innerHTML = '<div class="vacio">No se pudo cargar el dashboard.</div>';
    return;
  }
  datosActuales = await res.json();
  datosActuales.mesLabel = mesSel.label;

  renderMetricas();
  renderGauges();

  if (datosActuales.gastosTx.length === 0) {
    ['seccion-analisis-tarjeta', 'seccion-categoria', 'seccion-promedio', 'seccion-anio'].forEach((id) => {
      $(id).classList.add('oculto');
    });
    return;
  }

  const tarjetasEnPeriodo = new Map();
  for (const t of datosActuales.gastosTx) {
    if (t.tarjeta_id) tarjetasEnPeriodo.set(t.tarjeta_id, t.tarjeta_nombre || String(t.tarjeta_id));
  }
  datosActuales.tarjetasEnPeriodo = tarjetasEnPeriodo;
  chipsTarjetaSeleccionadas = new Set(tarjetasEnPeriodo.values());

  if (tarjetasEnPeriodo.size > 0) {
    $('seccion-analisis-tarjeta').classList.remove('oculto');
    renderChipsTarjeta();
  } else {
    $('seccion-analisis-tarjeta').classList.add('oculto');
  }

  $('seccion-categoria').classList.remove('oculto');
  $('seccion-promedio').classList.remove('oculto');
  $('seccion-anio').classList.remove('oculto');

  renderAnalisisTarjeta();
  renderCategoria();

  chipsCategoriaSeleccionadas = new Set(datosActuales.ytdPorCategoria.map((c) => c.categoria));
  renderChipsCategoria();
  renderPromedio();

  renderAnio();
}

// ── 1. Métricas ──

function renderMetricas() {
  const m = datosActuales.metricas;
  $('titulo-mes').textContent = datosActuales.mesLabel;
  const colorAhorro = m.ahorro >= 0 ? '#639922' : '#E24B4A';
  $('metricas').innerHTML = `
    <div class="metrica"><div class="valor">${fmt(m.total_ingresos)}</div><div class="etiqueta">💰 Ingresos</div></div>
    <div class="metrica"><div class="valor">${fmt(m.total_gastos)}</div><div class="etiqueta">💸 Gastos</div></div>
    <div class="metrica">
      <div class="valor" style="color:${colorAhorro}">${fmt(m.ahorro)}</div>
      <div class="etiqueta">🏦 Ahorro</div>
      <div class="delta" style="color:${colorAhorro}">${m.tasa_ahorro.toFixed(1)}% del ingreso</div>
    </div>
    <div class="metrica"><div class="valor">${m.n_cargos_reales}</div><div class="etiqueta">🧾 Cargos</div></div>
  `;
}

// ── 2. Estado de tarjetas ──

function opcionesGauge(nombre, pct, color) {
  return {
    series: [{
      type: 'gauge',
      startAngle: 210, endAngle: -30,
      min: 0, max: 100,
      progress: { show: true, width: 14, itemStyle: { color } },
      axisLine: { lineStyle: { width: 14, color: [[0.60, '#EAF3DE'], [0.85, '#FAEEDA'], [1, '#FCEBEB']] } },
      pointer: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      title: { show: true, fontSize: 12, color: '#35606f', offsetCenter: [0, '75%'] },
      detail: { formatter: '{value}%', fontSize: 18, offsetCenter: [0, '25%'], color: '#133a4f', fontWeight: 700 },
      data: [{ value: Math.round(pct * 10) / 10, name: nombre }],
    }],
  };
}

function renderGauges() {
  const lista = datosActuales.tarjetasConEstado;

  Object.keys(chartInstances)
    .filter((id) => id.startsWith('gauge-'))
    .forEach((id) => { chartInstances[id].dispose(); delete chartInstances[id]; });

  if (lista.length === 0) {
    $('tarjetas-gauges').innerHTML = '<div class="vacio">Sin tarjetas registradas.</div>';
    return;
  }
  $('tarjetas-gauges').innerHTML = lista.map(({ tarjeta }) => `
    <div class="gauge-item">
      <div class="chart" id="gauge-${tarjeta.id}"></div>
      <div class="info" id="gauge-info-${tarjeta.id}"></div>
    </div>
  `).join('');

  for (const { tarjeta, estado } of lista) {
    const pct = Math.min(estado.porcentaje_limite, 100);
    const color = estado.porcentaje_limite > 85 ? '#E24B4A' : estado.porcentaje_limite > 60 ? '#EF9F27' : '#378ADD';
    renderChart(`gauge-${tarjeta.id}`, opcionesGauge(tarjeta.nombre, pct, color));

    const dias = estado.dias_para_pago;
    const colorDias = dias <= 3 ? '#E24B4A' : dias <= 7 ? '#EF9F27' : '#639922';
    $(`gauge-info-${tarjeta.id}`).innerHTML = `
      <span style="color:${colorDias}">Pago en ${dias}d · ${fmtFechaCorta(estado.fecha_pago)}</span><br>
      <span class="gris">${fmt(estado.total_periodo)} de ${fmt(tarjeta.limite)}</span>
    `;
  }
}

// ── Filtro por tarjeta (chips) — afecta secciones 3 y 4 ──

function renderChipsTarjeta() {
  const nombres = [...datosActuales.tarjetasEnPeriodo.values()].sort();
  $('chips-tarjeta').innerHTML = nombres.map((n) =>
    `<span class="chip ${chipsTarjetaSeleccionadas.has(n) ? 'activo' : ''}" data-chip-tarjeta="${escapeHtml(n)}">${escapeHtml(n)}</span>`
  ).join('');
  document.querySelectorAll('[data-chip-tarjeta]').forEach((chip) => {
    chip.addEventListener('click', () => {
      const n = chip.dataset.chipTarjeta;
      if (chipsTarjetaSeleccionadas.has(n)) chipsTarjetaSeleccionadas.delete(n);
      else chipsTarjetaSeleccionadas.add(n);
      chip.classList.toggle('activo');
      renderAnalisisTarjeta();
      renderCategoria();
    });
  });
}

function calcularGastosFiltradosPorTarjeta() {
  const todosNombres = new Set(datosActuales.tarjetasEnPeriodo.values());
  const ningunoOTodos = chipsTarjetaSeleccionadas.size === 0 ||
    (chipsTarjetaSeleccionadas.size === todosNombres.size && [...todosNombres].every((n) => chipsTarjetaSeleccionadas.has(n)));

  if (ningunoOTodos) {
    return { gastosFiltrados: datosActuales.gastosTx, idsFiltradas: new Set(datosActuales.tarjetasEnPeriodo.keys()) };
  }
  const gastosFiltrados = datosActuales.gastosTx.filter((t) =>
    chipsTarjetaSeleccionadas.has(t.tarjeta_nombre) || !t.tarjeta_id
  );
  const idsFiltradas = new Set(
    [...datosActuales.tarjetasEnPeriodo.entries()].filter(([, n]) => chipsTarjetaSeleccionadas.has(n)).map(([id]) => id)
  );
  return { gastosFiltrados, idsFiltradas };
}

const PALETA = ['#378ADD', '#EF9F27', '#639922', '#E24B4A', '#9B59B6', '#1ABC9C', '#E67E22', '#2ECC71'];

// ── 3. Análisis por tarjeta ──

function renderAnalisisTarjeta() {
  if (datosActuales.tarjetasEnPeriodo.size === 0) return;
  const { gastosFiltrados, idsFiltradas } = calcularGastosFiltradosPorTarjeta();

  // 3a. Pie: cargos por tarjeta
  const conteo = {};
  for (const t of gastosFiltrados) {
    if (!t.es_proyeccion && t.tarjeta_id) conteo[t.tarjeta_nombre] = (conteo[t.tarjeta_nombre] || 0) + 1;
  }
  const nombresT = Object.keys(conteo).sort((a, b) => conteo[b] - conteo[a]);
  renderChart('chart-pie-tarjeta', {
    color: PALETA,
    title: { text: 'Cargos por tarjeta', left: 'center', top: 0, textStyle: { fontSize: 13 } },
    tooltip: { formatter: (p) => `${p.name}<br>${p.value} cargos (${p.percent}%)` },
    series: [{ type: 'pie', radius: '60%', top: 20, data: nombresT.map((n) => ({ name: n, value: conteo[n] })), label: { formatter: '{b}: {c}' } }],
  });

  // 3b. Barras agrupadas: categoría en cada tarjeta
  const catTotales = {};
  for (const t of gastosFiltrados) {
    if (idsFiltradas.has(t.tarjeta_id)) {
      const cat = t.categoria_nombre || 'Sin categoría';
      catTotales[cat] = (catTotales[cat] || 0) + montoEfectivo(t);
    }
  }
  const catsAsc = Object.keys(catTotales).sort((a, b) => catTotales[a] - catTotales[b]);
  const series = [];
  let i = 0;
  for (const [tid, tnombre] of datosActuales.tarjetasEnPeriodo.entries()) {
    if (!idsFiltradas.has(tid)) continue;
    const porCat = {};
    for (const t of gastosFiltrados) {
      if (t.tarjeta_id === tid) {
        const cat = t.categoria_nombre || 'Sin categoría';
        porCat[cat] = (porCat[cat] || 0) + montoEfectivo(t);
      }
    }
    series.push({
      name: tnombre, type: 'bar',
      data: catsAsc.map((c) => porCat[c] || 0),
      itemStyle: { color: PALETA[i % PALETA.length] },
      label: { show: true, position: 'right', formatter: (p) => (p.value > 0 ? fmtMoneda(p.value) : '') },
    });
    i++;
  }
  renderChart('chart-barras-tarjeta', {
    title: { text: 'Categoría en cada tarjeta', left: 'center', top: 0, textStyle: { fontSize: 13 } },
    legend: { top: 20, type: 'scroll' },
    grid: { left: 10, right: 90, top: 55, bottom: 10, containLabel: true },
    xAxis: { type: 'value', axisLabel: { formatter: fmtMoneda } },
    yAxis: { type: 'category', data: catsAsc },
    series,
  });
}

// ── 4. Gastos por categoría ──

function renderCategoria() {
  const { gastosFiltrados } = calcularGastosFiltradosPorTarjeta();

  const catData = {};
  for (const t of gastosFiltrados) {
    const cat = t.categoria_nombre || 'Sin categoría';
    if (!catData[cat]) catData[cat] = { monto: 0, color: t.categoria_color || '#888780', txs: [] };
    catData[cat].monto += montoEfectivo(t);
    catData[cat].txs.push(t);
  }

  const totalFiltrado = Object.values(catData).reduce((s, d) => s + d.monto, 0);
  const catsAsc = Object.keys(catData).sort((a, b) => catData[a].monto - catData[b].monto);
  const catsDesc = [...catsAsc].reverse();

  renderChart('chart-categoria', {
    grid: { left: 10, right: 90, top: 10, bottom: 10, containLabel: true },
    xAxis: { type: 'value', axisLabel: { formatter: fmtMoneda } },
    yAxis: { type: 'category', data: catsAsc },
    series: [{
      type: 'bar',
      data: catsAsc.map((c) => ({ value: catData[c].monto, itemStyle: { color: catData[c].color } })),
      label: { show: true, position: 'right', formatter: (p) => fmtMoneda(p.value) },
    }],
  });

  $('detalle-categoria').innerHTML = catsDesc.map((nombre) => {
    const d = catData[nombre];
    const pct = totalFiltrado > 0 ? (d.monto / totalFiltrado) * 100 : 0;
    const txsOrdenados = [...d.txs].sort((a, b) => montoEfectivo(b) - montoEfectivo(a));
    const idSeguro = `catdet-${nombre.replace(/[^a-zA-Z0-9]/g, '_')}`;
    return `
      <button type="button" class="cat-resumen" data-toggle-cat="${idSeguro}">
        <strong>${escapeHtml(nombre)}</strong> · ${fmt(d.monto)} · ${pct.toFixed(1)}%
      </button>
      <div class="cat-cuerpo oculto" id="${idSeguro}">
        ${txsOrdenados.map((t) => `
          <div class="cat-tx-fila">
            <span>${escapeHtml(t.descripcion)}</span>
            <span><span class="cat-tx-monto">${fmt(montoEfectivo(t))}</span><span class="cat-tx-tarjeta">${escapeHtml(t.tarjeta_nombre || '—')}</span></span>
          </div>
        `).join('')}
      </div>
    `;
  }).join('') || '<div class="vacio">Sin categorías.</div>';

  document.querySelectorAll('[data-toggle-cat]').forEach((btn) => {
    btn.addEventListener('click', () => $(btn.dataset.toggleCat).classList.toggle('oculto'));
  });
}

// ── 5. Promedio mensual por categoría (YTD) ──

function renderChipsCategoria() {
  const nombres = datosActuales.ytdPorCategoria.map((c) => c.categoria).sort();
  $('chips-categoria').innerHTML = nombres.map((n) =>
    `<span class="chip ${chipsCategoriaSeleccionadas.has(n) ? 'activo' : ''}" data-chip-cat="${escapeHtml(n)}">${escapeHtml(n)}</span>`
  ).join('');
  document.querySelectorAll('[data-chip-cat]').forEach((chip) => {
    chip.addEventListener('click', () => {
      const n = chip.dataset.chipCat;
      if (chipsCategoriaSeleccionadas.has(n)) chipsCategoriaSeleccionadas.delete(n);
      else chipsCategoriaSeleccionadas.add(n);
      chip.classList.toggle('activo');
      renderPromedio();
    });
  });
  const hoy = new Date();
  $('titulo-promedio').textContent = `📐 Promedio mensual de gasto por categoría — ${hoy.getFullYear()}`;
  $('titulo-anio').textContent = `🗓️ Gastos por categoría y mes — ${hoy.getFullYear()}`;
}

function renderPromedio() {
  const activas = chipsCategoriaSeleccionadas.size > 0
    ? datosActuales.ytdPorCategoria.filter((c) => chipsCategoriaSeleccionadas.has(c.categoria))
    : datosActuales.ytdPorCategoria;

  const suma = activas.reduce((s, c) => s + c.promedio, 0);
  $('promedio-total').textContent = fmt(suma);

  const ordenAsc = [...activas].sort((a, b) => a.promedio - b.promedio);
  renderChart('chart-promedio', {
    grid: { left: 10, right: 100, top: 10, bottom: 10, containLabel: true },
    xAxis: { type: 'value', axisLabel: { formatter: fmtMoneda } },
    yAxis: { type: 'category', data: ordenAsc.map((c) => c.categoria) },
    series: [{
      type: 'bar',
      data: ordenAsc.map((c) => ({ value: c.promedio, itemStyle: { color: c.color } })),
      label: { show: true, position: 'right', formatter: (p) => fmtMoneda(p.value) + '/mes' },
    }],
  });
}

// ── 6. Gastos por categoría y mes (año completo) ──

function renderAnio() {
  const entradas = Object.entries(datosActuales.anioPorCategoriaMes);
  if (entradas.length === 0) {
    if (chartInstances['chart-anio']) { chartInstances['chart-anio'].dispose(); delete chartInstances['chart-anio']; }
    $('chart-anio').innerHTML = '<div class="vacio">Sin gastos registrados en el año.</div>';
    return;
  }
  const catsOrden = entradas
    .map(([nombre, d]) => ({ nombre, ...d, total: d.meses.reduce((s, v) => s + v, 0) }))
    .sort((a, b) => b.total - a.total);

  const mesesX = MESES_ES.slice(1).map((m) => m.slice(0, 3));
  renderChart('chart-anio', {
    color: catsOrden.map((c) => c.color),
    legend: { top: 0, type: 'scroll' },
    grid: { left: 10, right: 10, top: 40, bottom: 10, containLabel: true },
    xAxis: { type: 'category', data: mesesX },
    yAxis: { type: 'value', axisLabel: { formatter: fmtMoneda } },
    tooltip: { trigger: 'axis' },
    series: catsOrden.map((c) => ({ name: c.nombre, type: 'bar', stack: 'total', data: c.meses })),
  });
}

inicializar();
