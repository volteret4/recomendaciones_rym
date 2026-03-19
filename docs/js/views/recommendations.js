import {
  state, goHome, setTab,
  BLOCKS, ENGINE_BLOCK,
  userColor, userInitials,
  getApp,
} from '../app.js';
import { renderArtistCard, initCardEventListeners } from '../components/artist-card.js';

export function renderRecommendations() {
  const { user, data, tab } = state;
  const recs  = data.recommendations;
  const app   = getApp();

  app.innerHTML = `
    <div class="recs-page">
      ${renderTopbar(user)}
      ${renderTabbar(recs, tab)}
      <main class="recs-content" id="recs-content">
        ${renderContent(recs, tab)}
      </main>
    </div>`;

  // Eventos de tabs
  app.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => setTab(btn.dataset.tab));
  });

  // Evento del botón volver
  app.querySelector('#btn-back')?.addEventListener('click', () => goHome());

  // Toggle de explicaciones largas
  const content = document.getElementById('recs-content');
  if (content) initCardEventListeners(content);
}

// ── Topbar ────────────────────────────────────────────────────
function renderTopbar(username) {
  const color = userColor(username);
  return `
    <header class="topbar">
      <span class="topbar-logo">MusicCircle</span>
      <span class="topbar-sep">›</span>
      <div class="topbar-user">
        <span class="avatar" style="background:${color}">${userInitials(username)}</span>
        <span>${username}</span>
      </div>
      <div class="topbar-actions">
        <button class="btn btn-ghost" id="btn-back">← Cambiar usuario</button>
      </div>
    </header>`;
}

// ── Tab bar ───────────────────────────────────────────────────
function renderTabbar(recs, activeTab) {
  const allRecs = recs?.recommendations ?? [];

  const tabs = BLOCKS.map(block => {
    const count = block.id === 'todo'
      ? allRecs.length
      : allRecs.filter(r => recsInBlock(r, block.id)).length;

    const isActive = activeTab === block.id;
    return `
      <button class="tab-btn${isActive ? ' active' : ''}"
        data-tab="${block.id}"
        style="--tab-color:${block.color}">
        <span class="tab-dot"></span>
        ${block.label}
        ${count > 0 ? `<span class="tab-count">${count}</span>` : ''}
      </button>`;
  });

  return `<nav class="tabbar">${tabs.join('')}</nav>`;
}

// ── Contenido central ─────────────────────────────────────────
function renderContent(recs, tab) {
  if (!recs) return renderNoData();

  const all = recs.recommendations ?? [];
  const filtered = tab === 'todo'
    ? all
    : all.filter(r => recsInBlock(r, tab));

  if (!filtered.length) return renderEmptyBlock(tab);

  return `<div class="cards-grid">${filtered.map((r, i) => renderArtistCard(r, i)).join('')}</div>`;
}

function renderNoData() {
  return `
    <div class="no-data">
      <div class="no-data-icon">🎵</div>
      <h2>Las recomendaciones aún no se han generado</h2>
      <p>Ejecuta el script de Python para generar los datos:</p>
      <code>python scripts/generate_recommendations.py</code>
      <p style="color:var(--muted);font-size:0.82rem;margin-top:0.5rem">
        Los JSONs se guardarán en <code>output/recommendations/</code>
      </p>
    </div>`;
}

function renderEmptyBlock(tab) {
  const block = BLOCKS.find(b => b.id === tab);
  return `
    <div class="no-data">
      <div class="no-data-icon">—</div>
      <h2>Sin recomendaciones en este bloque</h2>
      <p style="color:var(--muted);font-size:0.85rem">
        Los motores de <strong>${block?.label ?? tab}</strong> no generaron candidatos,<br>
        o aún no están implementados.
      </p>
    </div>`;
}

// ── Helpers ───────────────────────────────────────────────────
/** Devuelve true si alguno de los motores de una recomendación pertenece al bloque dado. */
function recsInBlock(rec, blockId) {
  return Object.keys(rec.engines ?? {}).some(
    engineId => ENGINE_BLOCK[engineId] === blockId
  );
}
