// Port de utils/calculos.py: calcular_periodo_corte, calcular_fecha_pago,
// dias_para_pago/corte, proyectar_msi_en_periodo, estado_tarjeta,
// agrupar_por_periodo. Fechas siempre como strings ISO 'YYYY-MM-DD'.

const MESES_ES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
  'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

function ultimoDiaDeMes(anio, mes) {
  return new Date(Date.UTC(anio, mes, 0)).getUTCDate();
}

function pad(n, len = 2) { return String(n).padStart(len, '0'); }

function armarFecha(anio, mes, dia) {
  return `${pad(anio, 4)}-${pad(mes)}-${pad(dia)}`;
}

function sumarDias(fechaIso, dias) {
  const [anio, mes, dia] = fechaIso.split('-').map(Number);
  const d = new Date(Date.UTC(anio, mes - 1, dia));
  d.setUTCDate(d.getUTCDate() + dias);
  return armarFecha(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());
}

function diferenciaDias(fechaIsoA, fechaIsoB) {
  const [aA, mA, dA] = fechaIsoA.split('-').map(Number);
  const [aB, mB, dB] = fechaIsoB.split('-').map(Number);
  const utcA = Date.UTC(aA, mA - 1, dA);
  const utcB = Date.UTC(aB, mB - 1, dB);
  return Math.round((utcA - utcB) / 86400000);
}

function labelPeriodo(fechaIso) {
  const mes = Number(fechaIso.split('-')[1]);
  const anio = fechaIso.split('-')[0];
  return `${MESES_ES[mes]} ${anio}`;
}

function inicioDePeriodoDesdeCorte(fechaCorteIso, diaCorte) {
  const [acAnio, acMes] = fechaCorteIso.split('-').map(Number);
  let anioAnt, mesAnt;
  if (acMes > 1) { anioAnt = acAnio; mesAnt = acMes - 1; }
  else { anioAnt = acAnio - 1; mesAnt = 12; }
  const ultimoAnt = ultimoDiaDeMes(anioAnt, mesAnt);
  const diaInicioBase = Math.min(diaCorte, ultimoAnt);
  const fechaInicioBase = armarFecha(anioAnt, mesAnt, diaInicioBase);
  return sumarDias(fechaInicioBase, 1);
}

function calcularPeriodoCorte(fechaGastoIso, diaCorte) {
  const [anio, mes, dia] = fechaGastoIso.split('-').map(Number);
  const ultimoDia = ultimoDiaDeMes(anio, mes);
  const diaCorteReal = Math.min(diaCorte, ultimoDia);

  let fechaCorte;
  if (dia <= diaCorteReal) {
    fechaCorte = armarFecha(anio, mes, diaCorteReal);
  } else {
    let anioSig = anio, mesSig = mes + 1;
    if (mesSig === 13) { anioSig += 1; mesSig = 1; }
    const ultimoDiaSig = ultimoDiaDeMes(anioSig, mesSig);
    fechaCorte = armarFecha(anioSig, mesSig, Math.min(diaCorte, ultimoDiaSig));
  }

  const fechaInicio = inicioDePeriodoDesdeCorte(fechaCorte, diaCorte);
  return { fechaCorte, fechaInicio, periodoLabel: labelPeriodo(fechaCorte) };
}

// Fecha de corte N meses después de una fecha de corte, respetando el día de corte
// de la tarjeta (un corte de febrero recortado al 28 vuelve al 30 en marzo).
function fechaCorteN(fechaCorteIso, n, diaCorte) {
  const [anio, mes] = fechaCorteIso.split('-').map(Number);
  const mTotal = mes + n;
  const anioN = anio + Math.floor((mTotal - 1) / 12);
  const mesN = ((mTotal - 1) % 12) + 1;
  return armarFecha(anioN, mesN, Math.min(diaCorte, ultimoDiaDeMes(anioN, mesN)));
}

// Período en que cae la mensualidad N (0 = el cargo original) de una compra a MSI:
// el período de la compra más N cortes. La mensualidad se muestra con fecha del
// primer día de ese período, es decir, el primer cobro después del corte anterior.
function periodoMensualidadMsi(fechaCompraIso, n, diaCorte) {
  const inicial = calcularPeriodoCorte(fechaCompraIso, diaCorte);
  const fechaCorte = fechaCorteN(inicial.fechaCorte, n, diaCorte);
  return {
    fechaCorte,
    fechaInicio: inicioDePeriodoDesdeCorte(fechaCorte, diaCorte),
    periodoLabel: labelPeriodo(fechaCorte),
  };
}

function calcularFechaPago(fechaCorteIso, diaPago) {
  const [anio, mes, dia] = fechaCorteIso.split('-').map(Number);
  if (diaPago > dia) {
    const ultimoDia = ultimoDiaDeMes(anio, mes);
    return armarFecha(anio, mes, Math.min(diaPago, ultimoDia));
  }
  let anioPago = anio, mesPago = mes + 1;
  if (mesPago === 13) { anioPago += 1; mesPago = 1; }
  const ultimoDia = ultimoDiaDeMes(anioPago, mesPago);
  return armarFecha(anioPago, mesPago, Math.min(diaPago, ultimoDia));
}

function diasParaPago(fechaPagoIso, hoyIso) { return diferenciaDias(fechaPagoIso, hoyIso); }
function diasParaCorte(fechaCorteIso, hoyIso) { return diferenciaDias(fechaCorteIso, hoyIso); }

function montoMensualDe(t) {
  const meses = t.meses_sin_intereses;
  return (t.monto_por_mes != null && t.monto_por_mes !== 0)
    ? t.monto_por_mes
    : Math.round((t.monto / meses) * 100) / 100;
}

function proyectarMsiEnPeriodo(transaccionesMsi, diaCorte, fechaCorteObjetivoIso) {
  const proyecciones = [];
  for (const t of transaccionesMsi) {
    const meses = t.meses_sin_intereses || 0;
    if (meses <= 0) continue;
    const montoMensual = montoMensualDe(t);

    for (let n = 0; n < meses; n++) {
      const periodoN = periodoMensualidadMsi(t.fecha, n, diaCorte);
      if (periodoN.fechaCorte === fechaCorteObjetivoIso) {
        proyecciones.push({
          ...t,
          monto: montoMensual,
          monto_por_mes: montoMensual,
          monto_original: t.monto,
          es_proyeccion: n > 0,
          mensualidad_num: n + 1,
          fecha: n === 0 ? t.fecha : periodoN.fechaInicio,
          fecha_cargo_original: t.fecha,
          descripcion: n === 0 ? t.descripcion : `${t.descripcion} (${n + 1}/${meses})`,
        });
        break;
      }
    }
  }
  return proyecciones;
}

function estadoTarjeta(tarjeta, transacciones, hoyIso, fechaCorteObjetivoIso) {
  const diaCorte = tarjeta.dia_corte;
  const diaPago = tarjeta.dia_pago;
  const limite = tarjeta.limite || 0;

  const periodo = fechaCorteObjetivoIso
    ? {
        fechaCorte: fechaCorteObjetivoIso,
        fechaInicio: inicioDePeriodoDesdeCorte(fechaCorteObjetivoIso, diaCorte),
        periodoLabel: labelPeriodo(fechaCorteObjetivoIso),
      }
    : calcularPeriodoCorte(hoyIso, diaCorte);

  const fechaPago = calcularFechaPago(periodo.fechaCorte, diaPago);

  const txsDirectas = transacciones.filter((t) =>
    t.fecha >= periodo.fechaInicio && t.fecha <= periodo.fechaCorte && (t.meses_sin_intereses || 0) === 0
  );

  const todosMsi = transacciones.filter((t) => (t.meses_sin_intereses || 0) > 0);
  const mensualidadesPeriodo = proyectarMsiEnPeriodo(todosMsi, diaCorte, periodo.fechaCorte);

  const txsPeriodo = [...txsDirectas, ...mensualidadesPeriodo];

  let total = 0;
  for (const t of txsDirectas) if (t.tipo === 'gasto') total += t.monto;
  for (const m of mensualidadesPeriodo) if (m.tipo === 'gasto') total += m.monto;
  total = Math.round(total * 100) / 100;

  const dCorte = diasParaCorte(periodo.fechaCorte, hoyIso);
  const dPago = diasParaPago(fechaPago, hoyIso);
  const alerta = dPago <= 3 ? 'urgente' : dPago <= 7 ? 'proximo' : 'ok';
  const porcentajeLimite = limite > 0 ? Math.round((total / limite) * 1000) / 10 : 0.0;

  return {
    periodo_actual: periodo,
    fecha_pago: fechaPago,
    dias_para_corte: dCorte,
    dias_para_pago: dPago,
    total_periodo: total,
    transacciones: txsPeriodo,
    proyecciones: mensualidadesPeriodo.filter((m) => m.es_proyeccion),
    alerta,
    porcentaje_limite: porcentajeLimite,
    limite,
  };
}

function agruparPorPeriodo(transacciones, diaCorte) {
  const grupos = {};

  function agregar(t, fechaCorte, fechaInicio, label, esProyeccion) {
    if (!grupos[label]) {
      grupos[label] = { fecha_corte: fechaCorte, fecha_inicio: fechaInicio, total: 0, transacciones: [], tiene_proyecciones: false };
    }
    grupos[label].transacciones.push(t);
    if (esProyeccion) grupos[label].tiene_proyecciones = true;
    if (t.tipo === 'gasto') {
      const montoReal = (t.meses_sin_intereses || 0) > 0
        ? (t.monto_por_mes != null ? t.monto_por_mes : t.monto)
        : t.monto;
      grupos[label].total = Math.round((grupos[label].total + montoReal) * 100) / 100;
    }
  }

  for (const t of transacciones) {
    const periodo = calcularPeriodoCorte(t.fecha, diaCorte);
    agregar(t, periodo.fechaCorte, periodo.fechaInicio, periodo.periodoLabel, false);
  }

  const todosMsi = transacciones.filter((t) => (t.meses_sin_intereses || 0) > 0);
  for (const t of todosMsi) {
    const meses = t.meses_sin_intereses;
    const montoMensual = montoMensualDe(t);
    for (let n = 1; n < meses; n++) {
      const periodoN = periodoMensualidadMsi(t.fecha, n, diaCorte);
      const proyeccion = {
        ...t,
        monto: montoMensual,
        monto_por_mes: montoMensual,
        monto_original: t.monto,
        es_proyeccion: true,
        mensualidad_num: n + 1,
        fecha: periodoN.fechaInicio,
        fecha_cargo_original: t.fecha,
        descripcion: `${t.descripcion} (${n + 1}/${meses})`,
      };
      agregar(proyeccion, periodoN.fechaCorte, periodoN.fechaInicio, periodoN.periodoLabel, true);
    }
  }

  const entradas = Object.entries(grupos).sort((a, b) => (a[1].fecha_corte < b[1].fecha_corte ? 1 : -1));
  return Object.fromEntries(entradas);
}

module.exports = {
  calcularPeriodoCorte, calcularFechaPago, diasParaPago, diasParaCorte,
  periodoMensualidadMsi, proyectarMsiEnPeriodo, estadoTarjeta, agruparPorPeriodo,
};
