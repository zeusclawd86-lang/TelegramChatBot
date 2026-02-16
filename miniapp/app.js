const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const state = {
  selectedCharacter: null,
  selectedScenario: null,
  worldGroups: [],
  activeWorldId: null,
};

const worldTabsEl = document.getElementById('worldTabs');
const charactersEl = document.getElementById('characters');
const scenariosEl = document.getElementById('scenarios');
const sendBtn = document.getElementById('sendBtn');

async function loadCharacters() {
  const res = await fetch('./characters.json', { cache: 'no-store' });
  const data = await res.json();

  if (Array.isArray(data.worldTypes)) {
    state.worldGroups = data.worldTypes.map((group) => ({
      id: group.id,
      label: group.label || group.id,
      characters: (group.characters || []).map((c) => ({ ...c, world: group.id })),
    }));
    state.activeWorldId = state.worldGroups.find((g) => g.characters.length)?.id || state.worldGroups[0]?.id || null;
    return;
  }

  const flat = data.characters || [];
  const byWorld = new Map();
  for (const c of flat) {
    const w = c.world || 'unknown';
    if (!byWorld.has(w)) byWorld.set(w, []);
    byWorld.get(w).push(c);
  }
  state.worldGroups = Array.from(byWorld.entries()).map(([id, chars]) => ({
    id,
    label: id,
    characters: chars,
  }));
  state.activeWorldId = state.worldGroups.find((g) => g.characters.length)?.id || state.worldGroups[0]?.id || null;
}

function renderWorldTabs() {
  worldTabsEl.innerHTML = '';
  for (const group of state.worldGroups) {
    const tab = document.createElement('button');
    tab.type = 'button';
    tab.className = `tab ${state.activeWorldId === group.id ? 'active' : ''}`;
    tab.textContent = group.label;
    tab.onclick = () => {
      state.activeWorldId = group.id;
      state.selectedCharacter = null;
      state.selectedScenario = null;
      syncSendButton();
      render();
    };
    worldTabsEl.appendChild(tab);
  }
}

function syncSendButton() {
  sendBtn.disabled = !(state.selectedCharacter && state.selectedScenario);
}

function renderCharacters() {
  charactersEl.innerHTML = '';

  const group = state.worldGroups.find((g) => g.id === state.activeWorldId) || state.worldGroups[0];
  if (!group) {
    charactersEl.innerHTML = '<p class="empty">Sin datos de mundos.</p>';
    return;
  }

  const section = document.createElement('section');
  section.className = 'group';

  const title = document.createElement('h2');
  title.className = 'group-title';
  title.textContent = `${group.label} · Personajes`;
  section.appendChild(title);

  const grid = document.createElement('div');
  grid.className = 'group-grid';

  if (!group.characters.length) {
    const empty = document.createElement('p');
    empty.className = 'empty';
    empty.textContent = 'Sin personajes por ahora';
    section.appendChild(empty);
    charactersEl.appendChild(section);
    return;
  }

  for (const c of group.characters) {
    const isActiveChar = state.selectedCharacter?.id === c.id;
    const imageHtml = c.image
      ? `<img class="char-image" src="${c.image}" alt="${c.name}" />`
      : `<div class="char-image char-image-fallback">${c.icon || '👤'}</div>`;

    const card = document.createElement('article');
    card.className = `card ${isActiveChar ? 'active' : ''}`;
    card.innerHTML = `
      ${imageHtml}
      <div class="name">${c.name}</div>
      <div class="meta">${group.label}</div>
      <div class="desc">${c.description || c.short || ''}</div>
    `;

    card.onclick = () => {
      state.selectedCharacter = { ...c, world: group.id, worldLabel: group.label };
      state.selectedScenario = null;
      syncSendButton();
      renderScenarios();
      renderCharacters();
    };

    grid.appendChild(card);
  }

  section.appendChild(grid);
  charactersEl.appendChild(section);
}

function renderScenarios() {
  scenariosEl.innerHTML = '';

  if (!state.selectedCharacter) {
    scenariosEl.classList.add('hidden');
    return;
  }

  scenariosEl.classList.remove('hidden');

  const header = document.createElement('h2');
  header.className = 'group-title';
  header.textContent = `Escenarios de ${state.selectedCharacter.name}`;
  scenariosEl.appendChild(header);

  const sub = document.createElement('p');
  sub.className = 'subtitle';
  sub.textContent = 'Selecciona un escenario para empezar el chat.';
  scenariosEl.appendChild(sub);

  const scenarios = state.selectedCharacter.scenarios || [];
  if (!scenarios.length) {
    const empty = document.createElement('p');
    empty.className = 'empty';
    empty.textContent = 'Este personaje no tiene escenarios configurados.';
    scenariosEl.appendChild(empty);
    return;
  }

  const grid = document.createElement('div');
  grid.className = 'scenario-cards';

  for (const s of scenarios) {
    const active = state.selectedScenario?.id === s.id;
    const card = document.createElement('article');
    card.className = `scenario-card ${active ? 'active' : ''}`;

    const mediaHtml = s.previewMp4
      ? `<video class="scenario-media" src="${s.previewMp4}" autoplay muted loop playsinline></video>`
      : s.previewImage
      ? `<img class="scenario-media" src="${s.previewImage}" alt="${s.title || s.id}" />`
      : `<div class="scenario-media scenario-fallback">${s.icon || '📍'}</div>`;

    card.innerHTML = `
      ${mediaHtml}
      <div class="scenario-name">${s.icon || '📍'} ${s.title || s.id}</div>
      <div class="scenario-desc">${s.description || ''}</div>
    `;

    card.onclick = () => {
      state.selectedScenario = s;
      syncSendButton();
      renderScenarios();
    };

    grid.appendChild(card);
  }

  scenariosEl.appendChild(grid);
}

function render() {
  renderWorldTabs();
  renderCharacters();
  renderScenarios();
}

sendBtn.onclick = () => {
  if (!state.selectedCharacter || !state.selectedScenario) return;

  const payload = JSON.stringify({
    type: 'select_character_scenario',
    character: state.selectedCharacter.id,
    world: state.selectedCharacter.world,
    scenario: state.selectedScenario.id,
    ts: Date.now(),
  });

  if (!tg || typeof tg.sendData !== 'function') {
    alert('MiniApp abierta fuera de Telegram o cliente no compatible. Usa el botón /miniapp desde el chat del bot.');
    return;
  }

  try {
    sendBtn.disabled = true;
    sendBtn.textContent = 'Enviando...';
    tg.HapticFeedback?.impactOccurred?.('medium');
    tg.sendData(payload);
    setTimeout(() => tg.close(), 180);
  } catch (err) {
    console.error(err);
    sendBtn.disabled = false;
    sendBtn.textContent = 'Empezar chat';
    tg.showAlert?.('No pude enviar la selección. Prueba de nuevo.');
  }
};

(async () => {
  try {
    await loadCharacters();
    render();
    syncSendButton();
  } catch (err) {
    charactersEl.innerHTML = '<p>No se pudo cargar la lista de personajes.</p>';
    console.error(err);
  }
})();
