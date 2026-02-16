const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const state = {
  selected: null,
  worldGroups: [],
};

const charactersEl = document.getElementById('characters');
const sendBtn = document.getElementById('sendBtn');

async function loadCharacters() {
  const res = await fetch('./characters.json', { cache: 'no-store' });
  const data = await res.json();

  // Nuevo formato agrupado por world type
  if (Array.isArray(data.worldTypes)) {
    state.worldGroups = data.worldTypes.map((group) => ({
      id: group.id,
      label: group.label || group.id,
      characters: (group.characters || []).map((c) => ({ ...c, world: group.id })),
    }));
    return;
  }

  // Compatibilidad con formato antiguo plano
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
      const card = document.createElement('article');
      card.className = `card ${state.selected?.id === c.id ? 'active' : ''}`;
      card.innerHTML = `
        <div class="icon">${c.icon || '👤'}</div>
        <div class="name">${c.name}</div>
        <div class="meta">${group.label}</div>
        <div class="meta">${c.short || ''}</div>
      `;
      card.onclick = () => {
        state.selected = { ...c, world: group.id };
        sendBtn.disabled = false;
        render();
      };
      grid.appendChild(card);
    }

    section.appendChild(grid);
    charactersEl.appendChild(section);
  }
}

sendBtn.onclick = () => {
  if (!state.selected || !tg) return;
  tg.sendData(
    JSON.stringify({
      type: 'select_character',
      character: state.selected.id,
      world: state.selected.world,
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
