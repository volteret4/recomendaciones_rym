import {
  USERS, userColor, userInitials,
  getStoredUser, clearStoredUser,
  selectUser, getApp,
} from '../app.js';

export function renderHome() {
  const stored = getStoredUser();
  const app = getApp();

  app.innerHTML = `
    <div class="home">
      <header class="home-header">
        <div class="home-logo">MusicCircle</div>
        <p class="home-sub">Recomendaciones musicales para el grupo — basadas en vuestros scrobbles de Last.fm</p>
      </header>

      ${stored ? renderWelcomeBack(stored) : ''}

      <p class="section-label">${stored ? 'O elige otro usuario' : '¿Quién eres?'}</p>
      <div class="user-grid">
        ${USERS.map(u => renderUserCard(u, u === stored)).join('')}
      </div>
    </div>`;

  // Botón "Continuar"
  app.querySelector('#btn-continue')?.addEventListener('click', () => {
    selectUser(stored);
  });

  // Botón "Cambiar usuario"
  app.querySelector('#btn-change')?.addEventListener('click', () => {
    clearStoredUser();
    renderHome();
  });

  // Cards de usuario
  app.querySelectorAll('.user-card').forEach(card => {
    card.addEventListener('click', () => selectUser(card.dataset.username));
  });
}

function renderWelcomeBack(username) {
  const color = userColor(username);
  return `
    <div class="home-welcome">
      <div class="avatar" style="background:${color}">${userInitials(username)}</div>
      <div class="welcome-text">
        <strong>${username}</strong>
        <span>Sesión guardada — ¿continuamos?</span>
      </div>
      <button class="btn btn-primary" id="btn-continue">Continuar</button>
      <button class="btn btn-ghost" id="btn-change">Cambiar</button>
    </div>`;
}

function renderUserCard(username, isActive) {
  const color = userColor(username);
  return `
    <button class="user-card${isActive ? ' active' : ''}" data-username="${username}">
      <div class="avatar" style="background:${color}">${userInitials(username)}</div>
      <span>${username}</span>
    </button>`;
}
