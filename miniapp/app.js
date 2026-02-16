const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const state = {
  selected: null,
  characters: [],
};

const charactersEl = document.getElementById('characters');
const sendBtn = document.getElementById('sendBtn');

async function loadCharacters() {
  const res = await fetch('./characters.json', { cache: 'no-store' });
  const data = await res.json();
  state.characters = data.characters || [];
}

function render() {
  charactersEl.innerHTML = '';
  for (const c of state.characters) {
    const card = document.createElement('article');
    card.className = `card ${state.selected?.id === c.id ? 'active' : ''}`;
    card.innerHTML = `
      <div class="icon">${c.icon || '👤'}</div>
      <div class="name">${c.name}</div>
      <div class="meta">${c.worldLabel || c.world || '-'}</div>
      <div class="meta">${c.short || ''}</div>
    `;
    card.onclick = () => {
      state.selected = c;
      sendBtn.disabled = false;
      render();
    };
    charactersEl.appendChild(card);
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
