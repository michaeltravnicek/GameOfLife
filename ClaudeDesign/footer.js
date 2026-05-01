/* ── Game of Life — Shared Footer Component ──
   Usage: <div id="footer-root"></div><script src="footer.js"></script>
*/
(function(){
  const style = document.createElement('style');
  style.textContent = `
    footer{position:relative;z-index:2;background:var(--color-purple);background-image:url('assets/Grain_texture_purple.png');background-size:cover;padding:52px 56px 44px;border-top:1px solid rgba(255,255,255,.05)}
    .ft-inner{max-width:1040px;margin:0 auto;display:grid;grid-template-columns:180px 1fr;gap:80px}
    .ft-label{font-family:'Helvetica',Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:rgba(255,255,255,.45);margin-bottom:14px}
    .ft-link{display:block;font-family:'IBM Plex Serif',Georgia,serif;font-style:italic;font-size:15px;color:rgba(255,255,255,.7);margin-bottom:6px;transition:color .15s;text-decoration:none}
    .ft-link:hover{color:#e15463}
    .ft-right{display:flex;flex-direction:column;align-items:flex-end;text-align:right}
    .ft-logo{font-family:'Bebas Neue',sans-serif;font-size:22px;color:#fff;letter-spacing:.06em;display:inline-flex;align-items:center;gap:8px;margin-bottom:18px}
    .ft-logo .sp{color:#e15463;font-size:14px}
    .ft-desc{font-family:'IBM Plex Serif',Georgia,serif;font-size:13px;font-weight:300;font-style:italic;line-height:1.7;color:rgba(255,255,255,.65);max-width:440px;margin-bottom:16px}
    .ft-contact{font-family:'IBM Plex Serif',Georgia,serif;font-size:13px;color:rgba(255,255,255,.6);line-height:1.7}
    .ft-credit{font-family:'IBM Plex Serif',Georgia,serif;font-size:11px;font-style:italic;color:rgba(255,255,255,.35);margin-top:14px}
    @media(max-width:640px){footer{padding:40px 24px 36px}.ft-inner{grid-template-columns:1fr;gap:40px}.ft-right{align-items:flex-start;text-align:left}}
  `;
  document.head.appendChild(style);

  const html = `<footer>
  <div class="ft-inner">
    <div>
      <div class="ft-label">Menu</div>
      <a class="ft-link" href="index.html">Domů</a>
      <a class="ft-link" href="events.html">Kalendář</a>
      <a class="ft-link" href="gallery_page.html">Galerie</a>
      <a class="ft-link" href="leaderboard.html">Leaderboard</a>
      <a class="ft-link" style="margin-top:14px" href="#">Instagram</a>
      <a class="ft-link" href="#">Facebook</a>
      <a class="ft-link" href="#">TikTok</a>
    </div>
    <div class="ft-right">
      <div class="ft-logo"><span class="sp">✦</span> GAME OF LIFE</div>
      <p class="ft-desc">Game of Life sdružuje ty, co chtějí z každodenního stereotypu vytřískat maximum a nebojí se u toho jít do extrému i do hloubky. Jsme tvůj protijed na moderní izolaci.</p>
      <div class="ft-contact">Vojta Toman<br/>+420 731 005 976</div>
      <div class="ft-credit">Tyhle krásný stránky vytvořil Lukáš Müller.<br/>Game of Life © 2026</div>
    </div>
  </div>
</footer>`;

  const root = document.getElementById('footer-root');
  if (root) root.outerHTML = html;
})();
