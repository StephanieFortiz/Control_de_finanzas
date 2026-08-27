const COLORES_PERFIL = {
  Azul: '#378ADD', Coral: '#D85A30', Verde: '#639922',
  Morado: '#7F77DD', Rosa: '#D4537E', Teal: '#1D9E75',
};
const TIPOS_CUENTA = ['debito', 'efectivo', 'ahorro', 'inversion'];
const COLORES_CAT = {
  Naranja: '#D85A30', Verde: '#639922', Azul: '#378ADD',
  Morado: '#7F77DD', Rosa: '#D4537E', Teal: '#1D9E75',
  Amarillo: '#EF9F27', Rojo: '#E24B4A', Gris: '#888780', 'Verde osc': '#085041',
};

let usuariosCache = [];

function badge(activo) {
  return activo ? '<span class="badge activa">Activa</span>' : '<span class="badge inactiva">Inactiva</span>';
}

function opcionesColor(mapa, seleccionado) {
  return Object.entries(mapa).map(([label, hex]) =>
    `<option value="${hex}" ${hex === seleccionado ? 'selected' : ''}>${label}</option>`
  ).join('');
}

// ── Tabs ──

document.querySelectorAll('.tab-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('activo'));
    btn.classList.add('activo');
    ['perfiles', 'cuentas', 'tarjetas', 'categorias'].forEach((t) => {
      $(`tab-${t}`).classList.toggle('oculto', t !== btn.dataset.tab);
    });
  });
});

// ── Perfiles ──

async function cargarPerfiles() {
  const res = await authFetch('/api/configuracion?recurso=usuarios');
  const datos = await res.json();
  usuariosCache = datos.usuarios;

  $('perfiles-grid').innerHTML = usuariosCache.map((u) => `
    <div class="perfil-badge" style="background:${u.color_perfil}22; border-color:${u.color_perfil}; color:${u.color_perfil}">
      ${escapeHtml(u.nombre)}
    </div>
  `).join('');

  const zona = $('perfiles-form-zona');
  if (usuariosCache.length >= 2) {
    zona.innerHTML = '';
    return;
  }

  const mensajeInfo = usuariosCache.length === 0
    ? 'Crea los dos perfiles para comenzar.'
    : `Perfil <strong>${escapeHtml(usuariosCache[0].nombre)}</strong> creado. Falta el segundo.`;

  zona.innerHTML = `
    <div class="mensaje" style="display:block; background:#e6f1fb; color:#0C447C; border:2px solid #b8d9f5">${mensajeInfo}</div>
    <form id="form-perfil">
      <label>Nombre</label>
      <input type="text" id="perfil-nombre" placeholder="Ej: Carlos" required>
      <label>Color</label>
      <select id="perfil-color">${opcionesColor(COLORES_PERFIL)}</select>
      <button type="submit" class="btn-primario">Crear perfil</button>
      <div class="mensaje" id="perfil-mensaje"></div>
    </form>
  `;

  $('form-perfil').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const nombre = $('perfil-nombre').value.trim();
    const m = $('perfil-mensaje');
    if (!nombre) { m.textContent = 'El nombre no puede estar vacío.'; m.className = 'mensaje error'; return; }
    if (usuariosCache.some((u) => u.nombre === nombre)) { m.textContent = 'Ya existe un perfil con ese nombre.'; m.className = 'mensaje error'; return; }

    try {
      const res = await authFetch('/api/configuracion', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recurso: 'usuario', nombre, color_perfil: $('perfil-color').value }),
      });
      const cuerpo = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(cuerpo.error || `HTTP ${res.status}`);
      await cargarPerfiles();
    } catch (err) {
      m.textContent = '❌ ' + err.message;
      m.className = 'mensaje error';
    }
  });
}

// ── Cuentas ──

async function cargarCuentas() {
  const res = await authFetch('/api/configuracion?recurso=cuentas');
  const cuentas = (await res.json()).cuentas;

  $('lista-cuentas').innerHTML = cuentas.map((c) => `
    <div class="fila-item">
      <div class="fila-info">
        <strong>${escapeHtml(c.nombre)}</strong> · ${c.tipo.charAt(0).toUpperCase() + c.tipo.slice(1)} ·
        Saldo inicial: ${fmt(c.saldo_inicial)}
        <span class="sub">(${escapeHtml(c.usuario_nombre)})</span> ${badge(!!c.activa)}
      </div>
      <button type="button" class="btn-editar" data-editar-cuenta="${c.id}">✏️ Editar</button>
    </div>
    <div id="edit-cuenta-${c.id}"></div>
  `).join('') || '<div class="fila-info sub">No hay cuentas registradas.</div>';

  document.querySelectorAll('[data-editar-cuenta]').forEach((btn) => {
    btn.addEventListener('click', () => toggleEditarCuenta(cuentas.find((c) => c.id === Number(btn.dataset.editarCuenta))));
  });

  $('toggle-agregar-cuenta').onclick = () => {
    const zona = $('form-agregar-cuenta');
    zona.innerHTML = zona.innerHTML ? '' : plantillaNuevaCuenta();
    if (zona.innerHTML) adjuntarFormNuevaCuenta();
  };
}

function toggleEditarCuenta(c) {
  const slot = $(`edit-cuenta-${c.id}`);
  if (slot.innerHTML) { slot.innerHTML = ''; return; }

  slot.classList.add('caja-form');
  slot.innerHTML = `
    <form id="form-edit-cuenta-${c.id}">
      <strong>Editar cuenta</strong>
      <div class="grid2">
        <div>
          <label>Nombre</label><input type="text" id="ec-nombre-${c.id}" value="${escapeHtml(c.nombre)}" required>
          <label>Saldo inicial ($)</label><input type="number" id="ec-saldo-${c.id}" step="0.01" min="0" value="${c.saldo_inicial}">
        </div>
        <div>
          <label>Tipo</label>
          <select id="ec-tipo-${c.id}">${TIPOS_CUENTA.map((t) => `<option value="${t}" ${t === c.tipo ? 'selected' : ''}>${t}</option>`).join('')}</select>
          <label class="checkbox-linea"><input type="checkbox" id="ec-activa-${c.id}" ${c.activa ? 'checked' : ''}> Cuenta activa</label>
        </div>
      </div>
      <div style="display:flex; gap:8px">
        <button type="submit" class="btn-primario">Guardar</button>
        <button type="button" class="btn-secundario" id="ec-cancelar-${c.id}">Cancelar</button>
      </div>
      <div class="mensaje" id="ec-mensaje-${c.id}"></div>
    </form>
  `;
  $(`ec-cancelar-${c.id}`).addEventListener('click', () => { slot.innerHTML = ''; });
  $(`form-edit-cuenta-${c.id}`).addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const m = $(`ec-mensaje-${c.id}`);
    const nombre = $(`ec-nombre-${c.id}`).value.trim();
    if (!nombre) { m.textContent = 'El nombre no puede estar vacío.'; m.className = 'mensaje error'; return; }
    try {
      const res = await authFetch('/api/configuracion', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recurso: 'cuenta', id: c.id, nombre,
          tipo: $(`ec-tipo-${c.id}`).value,
          saldo_inicial: parseFloat($(`ec-saldo-${c.id}`).value) || 0,
          activa: $(`ec-activa-${c.id}`).checked,
        }),
      });
      const cuerpo = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(cuerpo.error || `HTTP ${res.status}`);
      await cargarCuentas();
    } catch (err) {
      m.textContent = '❌ ' + err.message;
      m.className = 'mensaje error';
    }
  });
}

function plantillaNuevaCuenta() {
  return `
    <form id="form-nueva-cuenta" style="margin-top:10px">
      <label>Pertenece a</label>
      <select id="nc-usuario">${usuariosCache.map((u) => `<option value="${u.id}">${escapeHtml(u.nombre)}</option>`).join('')}</select>
      <div class="grid2">
        <div>
          <label>Nombre</label><input type="text" id="nc-nombre" placeholder="Ej: BBVA débito" required>
          <label>Saldo inicial ($)</label><input type="number" id="nc-saldo" step="0.01" min="0" value="0">
        </div>
        <div>
          <label>Tipo</label>
          <select id="nc-tipo">${TIPOS_CUENTA.map((t) => `<option value="${t}">${t}</option>`).join('')}</select>
        </div>
      </div>
      <button type="submit" class="btn-primario">Guardar cuenta</button>
      <div class="mensaje" id="nc-mensaje"></div>
    </form>
  `;
}

function adjuntarFormNuevaCuenta() {
  $('form-nueva-cuenta').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const m = $('nc-mensaje');
    const nombre = $('nc-nombre').value.trim();
    if (!nombre) { m.textContent = 'El nombre no puede estar vacío.'; m.className = 'mensaje error'; return; }
    try {
      const res = await authFetch('/api/configuracion', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recurso: 'cuenta', usuario_id: Number($('nc-usuario').value), nombre,
          tipo: $('nc-tipo').value, saldo_inicial: parseFloat($('nc-saldo').value) || 0,
        }),
      });
      const cuerpo = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(cuerpo.error || `HTTP ${res.status}`);
      $('form-agregar-cuenta').innerHTML = '';
      await cargarCuentas();
    } catch (err) {
      m.textContent = '❌ ' + err.message;
      m.className = 'mensaje error';
    }
  });
}

// ── Tarjetas ──

async function cargarTarjetasConfig() {
  const res = await authFetch('/api/configuracion?recurso=tarjetas');
  const tarjetas = (await res.json()).tarjetas;

  $('lista-tarjetas').innerHTML = tarjetas.map((t) => `
    <div class="fila-item">
      <div class="fila-info">
        <strong>${escapeHtml(t.nombre)}</strong> · ${escapeHtml(t.banco)} ·
        Corte: día ${t.dia_corte} · Pago: día ${t.dia_pago} · Límite: ${fmt(t.limite)}
        <span class="sub">(${escapeHtml(t.usuario_nombre)})</span> ${badge(!!t.activa)}
      </div>
      <button type="button" class="btn-editar" data-editar-tarjeta="${t.id}">✏️ Editar</button>
    </div>
    <div id="edit-tarjeta-${t.id}"></div>
  `).join('') || '<div class="fila-info sub">No hay tarjetas registradas.</div>';

  document.querySelectorAll('[data-editar-tarjeta]').forEach((btn) => {
    btn.addEventListener('click', () => toggleEditarTarjeta(tarjetas.find((t) => t.id === Number(btn.dataset.editarTarjeta))));
  });

  $('toggle-agregar-tarjeta').onclick = () => {
    const zona = $('form-agregar-tarjeta');
    zona.innerHTML = zona.innerHTML ? '' : plantillaNuevaTarjeta();
    if (zona.innerHTML) adjuntarFormNuevaTarjeta();
  };
}

function toggleEditarTarjeta(t) {
  const slot = $(`edit-tarjeta-${t.id}`);
  if (slot.innerHTML) { slot.innerHTML = ''; return; }

  slot.classList.add('caja-form');
  slot.innerHTML = `
    <form id="form-edit-tarjeta-${t.id}">
      <strong>Editar tarjeta</strong>
      <div class="grid2">
        <div>
          <label>Nombre</label><input type="text" id="et-nombre-${t.id}" value="${escapeHtml(t.nombre)}" required>
          <label>Día de corte</label><input type="number" id="et-corte-${t.id}" min="1" max="31" value="${t.dia_corte}">
          <label>Límite ($)</label><input type="number" id="et-limite-${t.id}" step="1" min="0" value="${t.limite}">
        </div>
        <div>
          <label>Banco</label><input type="text" id="et-banco-${t.id}" value="${escapeHtml(t.banco)}" required>
          <label>Día límite de pago</label><input type="number" id="et-pago-${t.id}" min="1" max="31" value="${t.dia_pago}">
          <label class="checkbox-linea"><input type="checkbox" id="et-activa-${t.id}" ${t.activa ? 'checked' : ''}> Tarjeta activa</label>
        </div>
      </div>
      <div style="display:flex; gap:8px">
        <button type="submit" class="btn-primario">Guardar</button>
        <button type="button" class="btn-secundario" id="et-cancelar-${t.id}">Cancelar</button>
      </div>
      <div class="mensaje" id="et-mensaje-${t.id}"></div>
    </form>
  `;
  $(`et-cancelar-${t.id}`).addEventListener('click', () => { slot.innerHTML = ''; });
  $(`form-edit-tarjeta-${t.id}`).addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const m = $(`et-mensaje-${t.id}`);
    const nombre = $(`et-nombre-${t.id}`).value.trim();
    const banco = $(`et-banco-${t.id}`).value.trim();
    if (!nombre || !banco) { m.textContent = 'Nombre y banco son obligatorios.'; m.className = 'mensaje error'; return; }
    try {
      const res = await authFetch('/api/configuracion', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recurso: 'tarjeta', id: t.id, nombre, banco,
          dia_corte: Number($(`et-corte-${t.id}`).value),
          dia_pago: Number($(`et-pago-${t.id}`).value),
          limite: parseFloat($(`et-limite-${t.id}`).value) || 0,
          activa: $(`et-activa-${t.id}`).checked,
        }),
      });
      const cuerpo = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(cuerpo.error || `HTTP ${res.status}`);
      await cargarTarjetasConfig();
    } catch (err) {
      m.textContent = '❌ ' + err.message;
      m.className = 'mensaje error';
    }
  });
}

function plantillaNuevaTarjeta() {
  return `
    <form id="form-nueva-tarjeta" style="margin-top:10px">
      <label>Pertenece a</label>
      <select id="nt-usuario">${usuariosCache.map((u) => `<option value="${u.id}">${escapeHtml(u.nombre)}</option>`).join('')}</select>
      <div class="grid2">
        <div>
          <label>Nombre</label><input type="text" id="nt-nombre" placeholder="Ej: BBVA Azul" required>
          <label>Día de corte</label><input type="number" id="nt-corte" min="1" max="31" value="1">
          <label>Límite ($)</label><input type="number" id="nt-limite" step="1" min="0" value="0">
        </div>
        <div>
          <label>Banco</label><input type="text" id="nt-banco" placeholder="Ej: BBVA" required>
          <label>Día límite de pago</label><input type="number" id="nt-pago" min="1" max="31" value="20">
        </div>
      </div>
      <p class="fila-info sub">💡 El día de corte es cuando cierra tu estado de cuenta.</p>
      <button type="submit" class="btn-primario">Guardar tarjeta</button>
      <div class="mensaje" id="nt-mensaje"></div>
    </form>
  `;
}

function adjuntarFormNuevaTarjeta() {
  $('form-nueva-tarjeta').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const m = $('nt-mensaje');
    const nombre = $('nt-nombre').value.trim();
    const banco = $('nt-banco').value.trim();
    if (!nombre || !banco) { m.textContent = 'Nombre y banco son obligatorios.'; m.className = 'mensaje error'; return; }
    try {
      const res = await authFetch('/api/configuracion', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recurso: 'tarjeta', usuario_id: Number($('nt-usuario').value), nombre, banco,
          dia_corte: Number($('nt-corte').value), dia_pago: Number($('nt-pago').value),
          limite: parseFloat($('nt-limite').value) || 0,
        }),
      });
      const cuerpo = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(cuerpo.error || `HTTP ${res.status}`);
      $('form-agregar-tarjeta').innerHTML = '';
      await cargarTarjetasConfig();
    } catch (err) {
      m.textContent = '❌ ' + err.message;
      m.className = 'mensaje error';
    }
  });
}

// ── Categorías ──

function nombreColor(hex) {
  return Object.keys(COLORES_CAT).find((k) => COLORES_CAT[k] === hex) || Object.keys(COLORES_CAT)[0];
}

async function cargarCategorias() {
  const incluirInactivas = $('mostrar-inactivas').checked ? '1' : '0';
  const res = await authFetch(`/api/configuracion?recurso=categorias&incluir_inactivas=${incluirInactivas}`);
  const categorias = (await res.json()).categorias;

  $('lista-categorias').innerHTML = categorias.map((c) => `
    <div class="fila-item">
      <div class="fila-info">
        ${c.icono} <strong>${escapeHtml(c.nombre)}</strong> · ${c.tipo.charAt(0).toUpperCase() + c.tipo.slice(1)} ${badge(!!c.activa)}
      </div>
      <button type="button" class="btn-editar" data-editar-cat="${c.id}">✏️ Editar</button>
    </div>
    <div id="edit-cat-${c.id}"></div>
  `).join('') || '<div class="fila-info sub">No hay categorías.</div>';

  document.querySelectorAll('[data-editar-cat]').forEach((btn) => {
    btn.addEventListener('click', () => toggleEditarCategoria(categorias.find((c) => c.id === Number(btn.dataset.editarCat))));
  });

  $('toggle-agregar-categoria').onclick = () => {
    const zona = $('form-agregar-categoria');
    zona.innerHTML = zona.innerHTML ? '' : plantillaNuevaCategoria();
    if (zona.innerHTML) adjuntarFormNuevaCategoria();
  };
}
$('mostrar-inactivas').addEventListener('change', cargarCategorias);

function toggleEditarCategoria(c) {
  const slot = $(`edit-cat-${c.id}`);
  if (slot.innerHTML) { slot.innerHTML = ''; return; }

  slot.classList.add('caja-form');
  slot.innerHTML = `
    <form id="form-edit-cat-${c.id}">
      <div class="grid3">
        <div>
          <label>Nombre</label><input type="text" id="ecat-nombre-${c.id}" value="${escapeHtml(c.nombre)}" required>
          <label>Ícono (emoji)</label><input type="text" id="ecat-icono-${c.id}" value="${c.icono}">
        </div>
        <div>
          <label>Tipo</label>
          <select id="ecat-tipo-${c.id}">
            <option value="gasto" ${c.tipo === 'gasto' ? 'selected' : ''}>gasto</option>
            <option value="ingreso" ${c.tipo === 'ingreso' ? 'selected' : ''}>ingreso</option>
          </select>
          <label>Color</label>
          <select id="ecat-color-${c.id}">${opcionesColor(COLORES_CAT, c.color)}</select>
        </div>
        <div>
          <label class="checkbox-linea"><input type="checkbox" id="ecat-activa-${c.id}" ${c.activa ? 'checked' : ''}> Categoría activa</label>
          <div class="vista-previa" id="ecat-preview-${c.id}" style="background:${c.color}22; border-color:${c.color}">${c.icono} ${escapeHtml(c.nombre)}</div>
        </div>
      </div>
      <div style="display:flex; gap:8px">
        <button type="submit" class="btn-primario">Guardar</button>
        <button type="button" class="btn-secundario" id="ecat-cancelar-${c.id}">Cancelar</button>
      </div>
      <div class="mensaje" id="ecat-mensaje-${c.id}"></div>
    </form>
  `;

  const actualizarPreview = () => {
    const color = $(`ecat-color-${c.id}`).value;
    const nombre = $(`ecat-nombre-${c.id}`).value || 'Vista previa';
    const icono = $(`ecat-icono-${c.id}`).value;
    const prev = $(`ecat-preview-${c.id}`);
    prev.style.background = color + '22';
    prev.style.borderColor = color;
    prev.textContent = `${icono} ${nombre}`;
  };
  $(`ecat-color-${c.id}`).addEventListener('change', actualizarPreview);
  $(`ecat-nombre-${c.id}`).addEventListener('input', actualizarPreview);
  $(`ecat-icono-${c.id}`).addEventListener('input', actualizarPreview);

  $(`ecat-cancelar-${c.id}`).addEventListener('click', () => { slot.innerHTML = ''; });
  $(`form-edit-cat-${c.id}`).addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const m = $(`ecat-mensaje-${c.id}`);
    const nombre = $(`ecat-nombre-${c.id}`).value.trim();
    if (!nombre) { m.textContent = 'El nombre no puede estar vacío.'; m.className = 'mensaje error'; return; }
    try {
      const res = await authFetch('/api/configuracion', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recurso: 'categoria', id: c.id, nombre,
          icono: $(`ecat-icono-${c.id}`).value.trim(),
          color: $(`ecat-color-${c.id}`).value,
          tipo: $(`ecat-tipo-${c.id}`).value,
          activa: $(`ecat-activa-${c.id}`).checked,
        }),
      });
      const cuerpo = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(cuerpo.error || `HTTP ${res.status}`);
      await cargarCategorias();
    } catch (err) {
      m.textContent = '❌ ' + err.message;
      m.className = 'mensaje error';
    }
  });
}

function plantillaNuevaCategoria() {
  return `
    <form id="form-nueva-cat" style="margin-top:10px">
      <div class="grid2">
        <div>
          <label>Nombre</label><input type="text" id="ncat-nombre" placeholder="Ej: Mascotas" required>
          <label>Ícono (emoji)</label><input type="text" id="ncat-icono" value="📦">
        </div>
        <div>
          <label>Tipo</label>
          <select id="ncat-tipo"><option value="gasto">gasto</option><option value="ingreso">ingreso</option></select>
          <label>Color</label>
          <select id="ncat-color">${opcionesColor(COLORES_CAT)}</select>
        </div>
      </div>
      <button type="submit" class="btn-primario">Crear categoría</button>
      <div class="mensaje" id="ncat-mensaje"></div>
    </form>
  `;
}

function adjuntarFormNuevaCategoria() {
  $('form-nueva-cat').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const m = $('ncat-mensaje');
    const nombre = $('ncat-nombre').value.trim();
    if (!nombre) { m.textContent = 'El nombre no puede estar vacío.'; m.className = 'mensaje error'; return; }
    try {
      const res = await authFetch('/api/configuracion', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recurso: 'categoria', nombre,
          icono: $('ncat-icono').value.trim() || '📦',
          color: $('ncat-color').value, tipo: $('ncat-tipo').value,
        }),
      });
      const cuerpo = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(cuerpo.error || `HTTP ${res.status}`);
      $('form-agregar-categoria').innerHTML = '';
      await cargarCategorias();
    } catch (err) {
      m.textContent = '❌ ' + err.message;
      m.className = 'mensaje error';
    }
  });
}

// ── Arranque ──

(async function iniciar() {
  await cargarPerfiles();
  await cargarCuentas();
  await cargarTarjetasConfig();
  await cargarCategorias();
})();
