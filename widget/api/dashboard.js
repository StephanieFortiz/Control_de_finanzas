const { getPool } = require('./_db');
const { requireAuth } = require('./_auth');
const { calcularPeriodoCorte, estadoTarjeta } = require('./_calculos');
const { inyectarProyeccionesMsi } = require('./_msi');

function ultimoDiaDeMes(anio, mes) {
  return new Date(Date.UTC(anio, mes, 0)).getUTCDate();
}
function pad(n, len = 2) { return String(n).padStart(len, '0'); }

function montoEfectivo(t) {
  if ((t.meses_sin_intereses || 0) > 0 && !t.es_proyeccion) {
    return t.monto_por_mes || t.monto;
  }
  return t.monto;
}

const QUERY_TX = `
  SELECT t.*, cat.nombre AS categoria_nombre, cat.color AS categoria_color, cat.icono AS categoria_icono,
         tc.nombre AS tarjeta_nombre, tc.dia_corte AS tarjeta_dia_corte
  FROM transaccion t
  LEFT JOIN categoria cat      ON t.categoria_id = cat.id
  LEFT JOIN tarjeta_credito tc ON t.tarjeta_id   = tc.id
  WHERE t.usuario_id = $1 AND t.fecha >= $2 AND t.fecha <= $3
`;

async function consultarTx(db, usuarioId, desde, hasta, soloGasto) {
  const query = soloGasto ? `${QUERY_TX} AND t.tipo = 'gasto'` : QUERY_TX;
  const result = await db.query(query, [usuarioId, desde, hasta]);
  return result.rows;
}

module.exports = async (req, res) => {
  if (!requireAuth(req, res)) return;
  const db = getPool();

  try {
    const usuarioId = req.query.usuario_id ? Number(req.query.usuario_id) : null;
    if (!usuarioId) return res.status(400).json({ error: 'Falta usuario_id.' });

    const hoyDate = new Date();
    const hoy = hoyDate.toISOString().slice(0, 10);
    const anio = req.query.anio ? Number(req.query.anio) : hoyDate.getUTCFullYear();
    const mes = req.query.mes ? Number(req.query.mes) : hoyDate.getUTCMonth() + 1;

    const desde = `${pad(anio, 4)}-${pad(mes)}-01`;
    const hasta = `${pad(anio, 4)}-${pad(mes)}-${pad(ultimoDiaDeMes(anio, mes))}`;
    const desdeAmplio = `${hoyDate.getUTCFullYear() - 3}-01-01`;

    // ── Transacciones del mes + inyección MSI ──
    let txs = await consultarTx(db, usuarioId, desde, hasta, false);
    const txsMsiBase = (await consultarTx(db, usuarioId, desdeAmplio, hasta, true))
      .filter((t) => (t.meses_sin_intereses || 0) > 0);
    if (txsMsiBase.length > 0) {
      txs = inyectarProyeccionesMsi(txs, desde, hasta, txsMsiBase);
    }
    const gastosTx = txs.filter((t) => t.tipo === 'gasto');
    const ingresosTx = txs.filter((t) => t.tipo === 'ingreso');

    // ── Estado de tarjetas ──
    const tarjetasRes = await db.query(
      'SELECT * FROM tarjeta_credito WHERE usuario_id = $1 AND activa = 1 ORDER BY nombre', [usuarioId]
    );
    const tarjetasUsuario = tarjetasRes.rows;
    const txsCardBase = await consultarTx(db, usuarioId, desdeAmplio, hasta, false);
    const fechaRefMes = `${pad(anio, 4)}-${pad(mes)}-01`;

    const tarjetasConEstado = tarjetasUsuario.map((tarjeta) => {
      const txsT = txsCardBase.filter((t) => t.tarjeta_id === tarjeta.id);
      const periodoCard = calcularPeriodoCorte(fechaRefMes, tarjeta.dia_corte);
      const estado = estadoTarjeta(tarjeta, txsT, hoy, periodoCard.fechaCorte);
      return { tarjeta, estado };
    });

    // ── Métricas ──
    const totalTarjetas = Math.round(tarjetasConEstado.reduce((s, x) => s + x.estado.total_periodo, 0) * 100) / 100;
    const gastosEfectivo = Math.round(
      gastosTx.filter((t) => !t.tarjeta_id).reduce((s, t) => s + montoEfectivo(t), 0) * 100
    ) / 100;
    const totalGastos = Math.round((totalTarjetas + gastosEfectivo) * 100) / 100;
    const totalIngresos = Math.round(ingresosTx.reduce((s, t) => s + t.monto, 0) * 100) / 100;
    const ahorro = Math.round((totalIngresos - totalGastos) * 100) / 100;
    const tasaAhorro = totalIngresos > 0 ? (ahorro / totalIngresos) * 100 : 0;
    const nCargosReales = gastosTx.filter((t) => !t.es_proyeccion).length;

    // ── Promedio mensual por categoría (año a la fecha) ──
    const desdeYtd = `${hoyDate.getUTCFullYear()}-01-01`;
    let txsYtd = await consultarTx(db, usuarioId, desdeYtd, hoy, false);
    const txsMsiYtd = (await consultarTx(db, usuarioId, desdeAmplio, hoy, true))
      .filter((t) => (t.meses_sin_intereses || 0) > 0);
    if (txsMsiYtd.length > 0) txsYtd = inyectarProyeccionesMsi(txsYtd, desdeYtd, hoy, txsMsiYtd);
    const gastosYtd = txsYtd.filter((t) => t.tipo === 'gasto');

    const catTotalYtd = {};
    const catColorYtd = {};
    for (const t of gastosYtd) {
      const cat = t.categoria_nombre || 'Sin categoría';
      catTotalYtd[cat] = (catTotalYtd[cat] || 0) + montoEfectivo(t);
      if (!(cat in catColorYtd)) catColorYtd[cat] = t.categoria_color || '#888780';
    }
    const mesesTranscurridosYtd = hoyDate.getUTCMonth() + 1;
    const ytdPorCategoria = Object.entries(catTotalYtd).map(([categoria, total]) => ({
      categoria, promedio: total / mesesTranscurridosYtd, color: catColorYtd[categoria],
    }));

    // ── Gastos por categoría y mes (año completo) ──
    const desdeAnio = `${hoyDate.getUTCFullYear()}-01-01`;
    const hastaAnio = `${hoyDate.getUTCFullYear()}-12-31`;
    let txsAnio = await consultarTx(db, usuarioId, desdeAnio, hastaAnio, false);
    const txsMsiAnio = (await consultarTx(db, usuarioId, desdeAmplio, hastaAnio, true))
      .filter((t) => (t.meses_sin_intereses || 0) > 0);
    if (txsMsiAnio.length > 0) txsAnio = inyectarProyeccionesMsi(txsAnio, desdeAnio, hastaAnio, txsMsiAnio);
    const gastosAnio = txsAnio.filter((t) => t.tipo === 'gasto');

    const catMes = {};
    const catColores = {};
    for (const t of gastosAnio) {
      const cat = t.categoria_nombre || 'Sin categoría';
      const mesI = Number(t.fecha.slice(5, 7));
      if (!catMes[cat]) catMes[cat] = new Array(12).fill(0);
      catMes[cat][mesI - 1] = Math.round((catMes[cat][mesI - 1] + montoEfectivo(t)) * 100) / 100;
      if (!(cat in catColores)) catColores[cat] = t.categoria_color || '#888780';
    }
    const anioPorCategoriaMes = {};
    for (const cat of Object.keys(catMes)) {
      anioPorCategoriaMes[cat] = { color: catColores[cat], meses: catMes[cat] };
    }

    return res.status(200).json({
      metricas: {
        total_ingresos: totalIngresos, total_gastos: totalGastos, ahorro, tasa_ahorro: tasaAhorro,
        n_cargos_reales: nCargosReales,
      },
      tarjetasConEstado,
      gastosTx,
      ytdPorCategoria,
      anioPorCategoriaMes,
      mesesTranscurridosYtd,
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: err.message });
  }
};
