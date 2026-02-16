const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const state = {
  selectedCharacter: null,
  selectedScenario: null,
  worldGroups: [],
};

const charactersEl = document.getElementById('characters');
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
}

function getSelectedCharacterFull() {
  for (const group of state.worldGroups) {
    for (const c of group.characters) {
      if (state.selectedCharacter && c.id === state.selectedCharacter.id) {
        return { ...c, world: group.id, worldLabel: group.label };
      }
    }
  }
  return null;
}

function renderScenarioSelector(container, character) {
  const scenarios = character.scenarios || [];

  const label = document.createElement('div');
  label.className = 'scenario-title';
  label.textContent = 'Escenario inicial';
  container.appendChild(label);

  if (!scenarios.length) {
    const empty = document.createElement('p');
    empty.className = 'empty';
    empty.textContent = 'Sin escenarios configurados para este personaje';
    container.appendChild(empty);
    return;
  }

  const wrap = document.createElement('div');
  wrap.className = 'scenario-grid';

  for (const s of scenarios) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `scenario-chip ${state.selectedScenario?.id === s.id ? 'active' : ''}`;
    btn.textContent = `${s.icon || '📍'} ${s.title || s.id}`;
    btn.onclick = () => {
      state.selectedScenario = s;
      syncSendButton();
      render();
    };
    wrap.appendChild(btn);
  }

  container.appendChild(wrap);
}

function syncSendButton() {
  sendBtn.disabled = !(state.selectedCharacter && state.selectedScenario);
}

function render() {
  charactersEl.innerHTML = '';

  for (const group of state.worldGroups) {
    const section = document.createElement('section');
    section.className = 'group';

    const title = document.createElement('h2');
    title.className = 'group-title';
    title.textContent = group.label;
    section.appendChild(title);

    const grid = document.createElement('div');
    grid.className = 'group-grid';

    if (!group.characters.length) {
      const empty = document.createElement('p');
      empty.className = 'empty';
      empty.textContent = 'Sin personajes por ahora';
      section.appendChild(empty);
      charactersEl.appendChild(section);
      continue;
    }

    for (const c of group.characters) {
      const isActiveChar = state.selectedCharacter?.id === c.id;
      const card = document.createElement('article');
      card.className = `card ${isActiveChar ? 'active' : ''}`;
      card.innerHTML = `
        <div class="icon">${c.icon || '👤'}</div>
        <div class="name">${c.name}</div>
        <div class="meta">${group.label}</div>
        <div class="meta">${c.short || ''}</div>
      `;

      card.onclick = () => {
        state.selectedCharacter = { ...c, world: group.id, worldLabel: group.label };
        state.selectedScenario = null;
        syncSendButton();
        render();
      };

      if (isActiveChar) {
        renderScenarioSelector(card, c);
      }

      grid.appendChild(card);
    }

    section.appendChild(grid);
    charactersEl.appendChild(section);
  }
}

sendBtn.onclick = () => {
  if (!state.selectedCharacter || !state.selectedScenario || !tg) return;

  tg.sendData(
    JSON.stringify({
      type: 'select_character_scenario',
      character: state.selectedCharacter.id,
      world: state.selectedCharacter.world,
      scenario: state.selectedScenario.id,
      ts: Date.now(),
    })
  );
  tg.close();
};

(async () => {
  try {
    await loadCharacters();
    render();
  } catch (err) {
    charactersEl.innerHTML = '<p>No se pudo cargar la lista de personajes.</p>';
    console.error(err);
  }
})();
