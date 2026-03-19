import { ENGINE_BLOCK, BLOCKS, userColor, userInitials } from '../app.js';

// Mapa de engine_id → label corto legible
const ENGINE_LABELS = {
  collab_direct:       'Colaborativo',
  genre_bridge:        'Género puente',
  discovery_chain:     'Cadena descubrimiento',
  trending_group:      'Trending',
  musical_twin:        'Gemelo musical',
  anti_bubble:         'Anti-burbuja',
  sync_listen:         'Escucha sync',
  deep_discography:    'Discografía',
  taste_inheritance:   'Herencia gustos',
  group_consensus:     'Consenso grupo',
  similar_cross_group: 'Similar+grupo',
  similar_transitive:  'Similar transitivo',
  tag_profile_match:   'Perfil de tags',
  tag_top_artists:     'Top por tag',
  track_similarity:    'Similar por track',
  collaboration_graph: 'Colaboraciones',
  influence_tree:      'Influencias',
  label_curator:       'Sello',
  shared_producers:    'Productor',
  member_network:      'Red miembros',
  rabbit_hole:         'Rabbit hole',
  seasonal:            'Estacional',
  adoption_pace:       'Ritmo adopción',
  rediscovery_cycle:   'Re-descubrimiento',
  hook_speed:          'Enganche rápido',
  musical_lineage:     'Linaje musical',
  discogs_styles:      'Estilos Discogs',
  rating_curator:      'Ratings',
  critical_dissonance: 'Disonancia crítica',
  decade_explorer:     'Década',
  country_affinity:    'País',
  skip_aware:          'Skip-aware',
  loyalty_based:       'Fidelidad',
  diversity_calibrated:'Diversidad',
  colistening_cluster: 'Co-escucha',
  artist2vec:          'Artist2Vec',
  markov_transition:   'Markov',
  guilty_pleasure:     'Guilty pleasure',
  duration_energy:     'Energía',
  complete_collection: 'Completar colección',
  missing_link:        'Eslabón perdido',
  narrative:           'Narrativo',
};

function blockColor(blockId) {
  return BLOCKS.find(b => b.id === blockId)?.color ?? 'var(--c-todo)';
}

function confidenceClass(score) {
  if (score >= 0.7) return 'high';
  if (score >= 0.4) return 'medium';
  return 'low';
}

function confidenceLabel(score) {
  if (score >= 0.7) return 'Alta';
  if (score >= 0.4) return 'Media';
  return 'Exploratoria';
}

function countryFlag(countryCode) {
  if (!countryCode || countryCode.length !== 2) return '';
  return String.fromCodePoint(
    ...countryCode.toUpperCase().split('').map(c => 0x1F1E6 + c.charCodeAt(0) - 65)
  );
}

export function renderArtistCard(rec, index) {
  const { artist, final_score, engines = {}, explanation_short, explanation_full,
          friends_who_listen = [], recommended_album, category } = rec;

  const scorePercent = Math.round((final_score ?? 0) * 100);
  const confCls      = confidenceClass(final_score ?? 0);
  const enginesHTML  = renderEngineBadges(engines);
  const friendsHTML  = renderFriends(friends_who_listen);
  const linksHTML    = renderLinks(artist);
  const cardId       = `card-${artist?.id ?? index}`;

  const meta = [
    artist?.country ? `${countryFlag(artist.country)} ${artist.country}` : null,
    artist?.formed_year ? artist.formed_year : null,
  ].filter(Boolean).join(' · ');

  const genres = (artist?.genres ?? []).slice(0, 3)
    .map(g => `<span class="genre-pill">${g}</span>`).join('');

  return `
    <article class="artist-card" id="${cardId}">
      <div class="card-header">
        <div class="card-cover">
          ${artist?.cover_url
            ? `<img src="${artist.cover_url}" alt="${artist?.name}" loading="lazy">`
            : `<span class="card-cover-placeholder">🎵</span>`}
        </div>
        <div class="card-info">
          <div class="card-rank">#${rec.rank ?? index + 1}</div>
          <div class="card-name" title="${artist?.name ?? '—'}">${artist?.name ?? '—'}</div>
          ${meta ? `<div class="card-meta">${meta}</div>` : ''}
          ${genres ? `<div class="card-genres">${genres}</div>` : ''}
        </div>
      </div>

      <div class="card-score">
        <div class="score-bar-wrap">
          <div class="score-bar-bg">
            <div class="score-bar-fill" style="width:${scorePercent}%"></div>
          </div>
          <span class="score-value">${scorePercent}%</span>
          <span class="confidence-badge ${confCls}">${confidenceLabel(final_score ?? 0)}</span>
        </div>
      </div>

      ${enginesHTML ? `<div class="card-engines">${enginesHTML}</div>` : ''}

      ${explanation_short || explanation_full ? `
        <div class="card-explanation">
          <div class="card-explanation-short">${explanation_short ?? ''}</div>
          ${explanation_full ? `
            <div class="card-explanation-full" id="full-${cardId}">${explanation_full}</div>
            <button class="toggle-explanation" data-target="full-${cardId}" data-open="false">
              Ver más ▾
            </button>` : ''}
        </div>` : ''}

      ${friendsHTML ? `<div class="card-friends">${friendsHTML}</div>` : ''}

      ${recommended_album ? `
        <div class="card-explanation" style="border-top:1px solid var(--border)">
          <span style="color:var(--muted);font-size:0.74rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em">Empieza por · </span>
          ${recommended_album.name}
          ${recommended_album.year ? `<span style="color:var(--muted)"> (${recommended_album.year})</span>` : ''}
        </div>` : ''}

      ${linksHTML ? `<div class="card-links">${linksHTML}</div>` : ''}
    </article>`;
}

function renderEngineBadges(engines) {
  return Object.keys(engines).map(id => {
    const block = ENGINE_BLOCK[id] ?? 'computado';
    const color = blockColor(block);
    return `<span class="engine-badge"
      style="color:${color};border-color:color-mix(in srgb,${color} 30%,transparent);background:color-mix(in srgb,${color} 10%,transparent)"
      title="${engines[id]?.explanation ?? ''}">${ENGINE_LABELS[id] ?? id}</span>`;
  }).join('');
}

function renderFriends(friends) {
  if (!friends.length) return '';
  return friends.slice(0, 5).map(f => {
    const color = userColor(f.username);
    return `<span class="friend-chip">
      <span class="avatar" style="background:${color}">${userInitials(f.username)}</span>
      ${f.username}${f.scrobbles ? ` <span style="color:var(--muted)">(${f.scrobbles})</span>` : ''}
    </span>`;
  }).join('');
}

function renderLinks(artist) {
  if (!artist) return '';
  const links = [
    artist.spotify_url  && { href: artist.spotify_url,  label: 'Spotify'     },
    artist.youtube_url  && { href: artist.youtube_url,  label: 'YouTube'     },
    artist.lastfm_url   && { href: artist.lastfm_url,   label: 'Last.fm'     },
    artist.bandcamp_url && { href: artist.bandcamp_url, label: 'Bandcamp'    },
    artist.rym_url      && { href: artist.rym_url,      label: 'RYM'         },
  ].filter(Boolean);

  return links.map(l =>
    `<a class="link-btn" href="${l.href}" target="_blank" rel="noopener">${l.label}</a>`
  ).join('');
}

// Delegación de eventos para los toggles "Ver más"
export function initCardEventListeners(container) {
  container.addEventListener('click', e => {
    const toggle = e.target.closest('.toggle-explanation');
    if (!toggle) return;
    const targetId = toggle.dataset.target;
    const full = document.getElementById(targetId);
    if (!full) return;
    const open = toggle.dataset.open === 'true';
    full.classList.toggle('open', !open);
    toggle.dataset.open = String(!open);
    toggle.textContent  = open ? 'Ver más ▾' : 'Ver menos ▴';
  });
}
