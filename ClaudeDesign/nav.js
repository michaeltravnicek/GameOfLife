/* ── Game of Life — Shared Nav Component ──
   Reads localStorage('gol_user') to decide guest vs. logged-in nav.
   Usage: <div id="nav-root"></div><script src="nav.js"></script>
   Mark current page: <script>window.GOL_PAGE = 'events'</script> before nav.js
*/
(function(){
  const PAGE = window.GOL_PAGE || '';
  const user = localStorage.getItem('gol_user'); // null = guest

  const style = document.createElement('style');
  style.textContent = `
    nav.top{position:fixed;top:24px;left:60px;right:60px;z-index:100;display:flex;align-items:center;justify-content:space-between;padding:0 8px 0 36px;border-radius:9999px;background:rgba(80,74,118,.82);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border:1px solid rgba(255,255,255,.10);box-shadow:0 8px 32px rgba(0,0,0,.3);transition:transform .3s ease}
    nav.top.hidden{transform:translateY(-120px)}
    .nav-left,.nav-right{display:flex;align-items:center;gap:36px;flex:1}
    .nav-right{justify-content:flex-end}
    .nav-item{font-family:'Helvetica',Arial,sans-serif;font-size:16px;font-weight:700;letter-spacing:.03em;color:rgba(255,255,255,.88);background:none;border:0;cursor:pointer;transition:color .2s;padding:18px 0;text-decoration:none;display:inline-block}
    .nav-item:hover,.nav-item.active{color:#e15463}
    .nav-logo{height:64px;display:flex;align-items:center;background:transparent;border:0;cursor:pointer;padding:6px 0;text-decoration:none}
    .nav-logo img{height:100%;width:auto;display:block}
    .nav-avatar{width:50px;height:50px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;border:1.5px solid rgba(255,255,255,.5);font-family:'Courier Prime','Courier New',monospace;font-style:italic;font-size:13px;font-weight:700;color:#fff;cursor:pointer;transition:border-color .2s;margin:9px 0;text-decoration:none}
    .nav-avatar:hover,.nav-avatar.active{border-color:#e15463}
    .nav-btn-start{display:inline-flex;align-items:center;gap:8px;background:#e15463;color:#fff;border:0;cursor:pointer;font-family:'Helvetica',Arial,sans-serif;font-size:14px;font-weight:700;letter-spacing:.04em;padding:10px 24px;border-radius:9999px;box-shadow:0 4px 16px rgba(225,84,99,.38);transition:transform .18s,background .18s;text-decoration:none;margin:10px 0}
    .nav-btn-start:hover{background:#cf4453;transform:translateY(-1px)}
    @media(max-width:820px){nav.top{left:14px;right:14px;padding:0 6px 0 20px}.nav-left,.nav-right{gap:18px}.nav-item{font-size:14px}.nav-logo{height:52px}}
    @media(max-width:560px){.nav-left .nav-item:nth-child(3){display:none}}
  `;
  document.head.appendChild(style);

  function li(href, label, key) {
    const active = PAGE === key ? ' active' : '';
    return `<a class="nav-item${active}" href="${href}">${label}</a>`;
  }

  const initials = (s) => s.split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase();
  const ava = user ? initials(user) : '';

  const rightHtml = user
    ? `${li('leaderboard.html','Leaderboard','leaderboard')}${li('eshop.html','Eshop','eshop')}<a class="nav-avatar${PAGE==='profile'?' active':''}" href="profile.html" title="${user}">${ava}</a>`
    : `${li('leaderboard.html','Leaderboard','leaderboard')}<a class="nav-btn-start" href="register.html">Start Playing ➤</a>`;

  const html = `<nav class="top" id="gol-nav">
    <div class="nav-left">
      ${li('index.html','Domů','home')}
      ${li('events.html','Akce','events')}
      ${li('gallery_page.html','Galerie','gallery')}
    </div>
    <a class="nav-logo" href="index.html" aria-label="Game of Life">
      <img src="logos/GOL_main_logo_pink.png" alt="Game of Life" />
    </a>
    <div class="nav-right">${rightHtml}</div>
  </nav>`;

  const root = document.getElementById('nav-root');
  if (root) root.innerHTML = html;

  // Hide on scroll
  let lastY = 0, up = 0;
  window.addEventListener('scroll', () => {
    const nav = document.getElementById('gol-nav');
    if (!nav) return;
    const y = window.pageYOffset;
    if (y > lastY) { up = 0; nav.classList.add('hidden'); }
    else { up++; if (up >= 3) { nav.classList.remove('hidden'); up = 0; } }
    lastY = y <= 0 ? 0 : y;
  }, { passive: true });
})();
