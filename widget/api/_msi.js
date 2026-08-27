// Port de utils/calculos.py: _fecha_mas_n_meses e inyectar_proyecciones_msi.
// Las fechas se manejan como strings ISO 'YYYY-MM-DD' en todo momento.

function ultimoDiaDeMes(anio, mes) {
  return new Date(Date.UTC(anio, mes, 0)).getUTCDate();
}

function fechaISOaObj(iso) {
  const [anio, mes, dia] = iso.split('-').map(Number);
  return { anio, mes, dia };
}

function objAFechaISO({ anio, mes, dia }) {
  return `${String(anio).padStart(4, '0')}-${String(mes).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
}

function fechaMasNMeses(fechaIso, n) {
  const { anio, mes, dia } = fechaISOaObj(fechaIso);
  const mTotal = mes + n;
  const anioNuevo = anio + Math.floor((mTotal - 1) / 12);
  const mesNuevo = ((mTotal - 1) % 12) + 1;
  const diaNuevo = Math.min(dia, ultimoDiaDeMes(anioNuevo, mesNuevo));
  return objAFechaISO({ anio: anioNuevo, mes: mesNuevo, dia: diaNuevo });
}

function inyectarProyeccionesMsi(transacciones, desde, hasta, txsMsiOrigen) {
  const fuente = txsMsiOrigen != null ? txsMsiOrigen : transacciones;
  const todosMsi = fuente.filter((t) => (t.meses_sin_intereses || 0) > 0);
  const proyecciones = [];

  for (const t of todosMsi) {
    const meses = t.meses_sin_intereses;
    const montoMens = t.monto_por_mes != null && t.monto_por_mes !== 0
      ? t.monto_por_mes
      : Math.round((t.monto / meses) * 100) / 100;

    for (let n = 1; n < meses; n++) {
      const fechaN = fechaMasNMeses(t.fecha, n);
      if (fechaN < desde || fechaN > hasta) continue;

      proyecciones.push({
        ...t,
        monto: montoMens,
        monto_por_mes: montoMens,
        es_proyeccion: true,
        mensualidad_num: n + 1,
        fecha_cargo_original: t.fecha,
        fecha: fechaN,
        descripcion: `${t.descripcion} (${n + 1}/${meses})`,
      });
    }
  }

  if (proyecciones.length === 0) return transacciones;

  const combinadas = transacciones.concat(proyecciones);
  combinadas.sort((a, b) => {
    if (a.fecha !== b.fecha) return a.fecha < b.fecha ? 1 : -1;
    return (b.id || 0) - (a.id || 0);
  });
  return combinadas;
}

module.exports = { fechaMasNMeses, inyectarProyeccionesMsi };
