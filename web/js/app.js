// ── Constantes ────────────────────────────────────────────────
const STORAGE_KEY = 'musiccircle_user';

export const USERS = [
  'eliasj72', 'frikomid', 'gabredmared', 'lonsonxd', 'nubis84',
  'rocky_stereo', 'alberto_gu', 'paqueradejere', 'sdecandelario',
  'bipolarmuzik', 'verygooood',
];

// Colores deterministicos por usuario (HSL, evitando rojo puro)
const USER_COLORS = [
  '#3b82f6','#06b6d4','#10b981','#f59e0b','#ec4899',
  '#8b5cf6','#ef4444','#14b8a6','#f97316','#84cc16','#a78bfa',
];
export function userColor(username) {
  return USER_COLORS[USERS.indexOf(username) % USER_COLORS.length] ?? '#8b5cf6';
}
export function userInitials(username) {
  return username.slice(0, 2).toUpperCase();
}

// Bloques de motores
export const BLOCKS = [
  { id: 'todo',      label: 'Todos',      color: 'var(--c-todo)'      },
  { id: 'amigos',    label: 'Amigos',     color: 'var(--c-amigos)'    },
  { id: 'similitud', label: 'Similitud',  color: 'var(--c-similitud)' },
  { id: 'relaciones',label: 'Relaciones', color: 'var(--c-relaciones)'},
  { id: 'temporal',  label: 'Temporal',   color: 'var(--c-temporal)'  },
  { id: 'generos',   label: 'Géneros',    color: 'var(--c-generos)'   },
  { id: 'computado', label: 'Señales',    color: 'var(--c-computado)' },
];

export const ENGINE_BLOCK = {
  // Bloque A — Amigos
  collab_direct:     'amigos',
  genre_bridge:      'amigos',
  discovery_chain:   'amigos',
  trending_group:    'amigos',
  musical_twin:      'amigos',
  anti_bubble:       'amigos',
  sync_listen:       'amigos',
  deep_discography:  'amigos',
  taste_inheritance: 'amigos',
  group_consensus:   'amigos',
  // Bloque B — Similitud externa
  similar_cross_group: 'similitud',
  similar_transitive:  'similitud',
  tag_profile_match:   'similitud',
  tag_top_artists:     'similitud',
  track_similarity:    'similitud',
  // Bloque C — Grafos y relaciones
  collaboration_graph: 'relaciones',
  influence_tree:      'relaciones',
  label_curator:       'relaciones',
  shared_producers:    'relaciones',
  member_network:      'relaciones',
  // Bloque D — Temporal
  rabbit_hole:        'temporal',
  seasonal:           'temporal',
  adoption_pace:      'temporal',
  rediscovery_cycle:  'temporal',
  hook_speed:         'temporal',
  musical_lineage:    'temporal',
  // Bloque E — Géneros y ratings
  discogs_styles:       'generos',
  rating_curator:       'generos',
  critical_dissonance:  'generos',
  decade_explorer:      'generos',
  country_affinity:     'generos',
  // Bloque F — Señales computadas
  skip_aware:           'computado',
  loyalty_based:        'computado',
  diversity_calibrated: 'computado',
  colistening_cluster:  'computado',
  artist2vec:           'computado',
  markov_transition:    'computado',
  guilty_pleasure:      'computado',
  duration_energy:      'computado',
  complete_collection:  'computado',
  missing_link:         'computado',
  narrative:            'computado',
};

// ── Estado global ─────────────────────────────────────────────
export const state = {
  user: null,
  data: { recommendations: null, profile: null },
  tab: 'todo',
};

// ── Storage ───────────────────────────────────────────────────
export function getStoredUser() {
  return localStorage.getItem(STORAGE_KEY);
}
export function clearStoredUser() {
  localStorage.removeItem(STORAGE_KEY);
}

// ── Helpers ───────────────────────────────────────────────────
export function getApp() {
  return document.getElementById('app');
}

async function fetchJSON(url) {
  try {
    const res = await fetch(url);
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
}

// ── Navegación ────────────────────────────────────────────────
export async function selectUser(username) {
  state.user = username;
  state.tab  = 'todo';
  localStorage.setItem(STORAGE_KEY, username);

  getApp().innerHTML = `
    <div class="loading">
      <div class="spinner"></div>
      <p>Cargando recomendaciones para <strong>${username}</strong>…</p>
    </div>`;

  const [recommendations, profile] = await Promise.all([
    fetchJSON(`data/recommendations/${username}.json`),
    fetchJSON(`data/profiles/${username}.json`),
  ]);
  state.data = { recommendations, profile };

  const { renderRecommendations } = await import('./views/recommendations.js');
  renderRecommendations();
}

export async function goHome() {
  state.user = null;
  state.data = { recommendations: null, profile: null };
  const { renderHome } = await import('./views/home.js');
  renderHome();
}

export async function setTab(tab) {
  state.tab = tab;
  const { renderRecommendations } = await import('./views/recommendations.js');
  renderRecommendations();
}

// ── Init ──────────────────────────────────────────────────────
(async () => {
  const stored = getStoredUser();
  if (stored && USERS.includes(stored)) {
    await selectUser(stored);
  } else {
    const { renderHome } = await import('./views/home.js');
    renderHome();
  }
})();
