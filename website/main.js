/* ============================================================
   Unkle Funk — unklefunk.music — main.js  v2
   ============================================================ */

// ── Hero Canvas Equalizer ────────────────────────────────
;(function () {
  const canvas = document.getElementById('heroCanvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const BAR_COUNT = 80;
  const heights   = new Float32Array(BAR_COUNT).fill(0.05);
  const targets   = new Float32Array(BAR_COUNT).fill(0.05);
  let raf;

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width  = canvas.offsetWidth  * dpr;
    canvas.height = canvas.offsetHeight * dpr;
    ctx.scale(dpr, dpr);
  }

  function newTargets() {
    for (let i = 0; i < BAR_COUNT; i++) {
      const center = Math.abs(i / BAR_COUNT - 0.5);
      const peak   = Math.max(0.08, 0.65 * (1 - center * 1.6));
      targets[i]   = Math.random() * peak + 0.03;
    }
  }

  function draw() {
    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;

    ctx.clearRect(0, 0, w, h);

    const barW  = w / BAR_COUNT;
    const midY  = h * 0.5;
    const maxH  = h * 0.28;
    const gap   = barW * 0.35;

    for (let i = 0; i < BAR_COUNT; i++) {
      heights[i] += (targets[i] - heights[i]) * 0.04;

      const bh   = heights[i] * maxH;
      const x    = i * barW + gap / 2;
      const bw   = barW - gap;
      const r    = Math.min(bw / 2, 3);

      // Top bar
      const gTop = ctx.createLinearGradient(0, midY - bh, 0, midY);
      gTop.addColorStop(0, 'rgba(201,168,76,0.7)');
      gTop.addColorStop(1, 'rgba(201,168,76,0.15)');

      ctx.beginPath();
      ctx.roundRect(x, midY - bh, bw, bh, [r, r, 0, 0]);
      ctx.fillStyle = gTop;
      ctx.fill();

      // Mirror (reflected) bar
      const gBot = ctx.createLinearGradient(0, midY, 0, midY + bh * 0.5);
      gBot.addColorStop(0, 'rgba(201,168,76,0.12)');
      gBot.addColorStop(1, 'rgba(201,168,76,0)');

      ctx.beginPath();
      ctx.roundRect(x, midY, bw, bh * 0.5, [0, 0, r, r]);
      ctx.fillStyle = gBot;
      ctx.fill();
    }
  }

  let tick = 0;
  function loop() {
    tick++;
    if (tick % 12 === 0) newTargets();
    draw();
    raf = requestAnimationFrame(loop);
  }

  resize();
  newTargets();
  loop();

  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(resize, 120);
  });

  // Pause when tab hidden (perf)
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) cancelAnimationFrame(raf);
    else loop();
  });
})();


// ── Navigation ───────────────────────────────────────────
;(function () {
  const nav          = document.getElementById('nav');
  const navToggle    = document.getElementById('navToggle');
  const drawer       = document.getElementById('drawer');
  const drawerOverlay = document.getElementById('drawerOverlay');
  const drawerLinks  = document.querySelectorAll('.drawer__link');

  if (!nav) return;

  // Scrolled state
  let lastY = 0;
  function onScroll() {
    const y = window.scrollY;
    nav.classList.toggle('scrolled', y > 30);
    lastY = y;
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // Mobile drawer
  function openDrawer() {
    drawer.classList.add('open');
    drawerOverlay.classList.add('show');
    navToggle.classList.add('open');
    navToggle.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeDrawer() {
    drawer.classList.remove('open');
    drawerOverlay.classList.remove('show');
    navToggle.classList.remove('open');
    navToggle.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  navToggle.addEventListener('click', () => {
    if (drawer.classList.contains('open')) closeDrawer();
    else openDrawer();
  });

  drawerOverlay.addEventListener('click', closeDrawer);
  drawerLinks.forEach(link => link.addEventListener('click', closeDrawer));
})();


// ── Smooth scroll for anchor links ───────────────────────
;(function () {
  const NAV_H = 68;
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', e => {
      const target = document.querySelector(anchor.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      const top = target.getBoundingClientRect().top + window.scrollY - NAV_H;
      window.scrollTo({ top, behavior: 'smooth' });
    });
  });
})();


// ── Scroll reveal ────────────────────────────────────────
;(function () {
  const els = document.querySelectorAll(
    '.section-title, .about__body, .stats, .vinyl, .about__quote, ' +
    '.podcast__desc, .podcast__embed, .podcast__platforms, ' +
    '.music-embed, .chart-feature, .release, .connect-card, ' +
    '.releases__footer'
  );

  els.forEach(el => el.classList.add('reveal'));

  if (!('IntersectionObserver' in window)) {
    els.forEach(el => el.classList.add('visible'));
    return;
  }

  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -48px 0px' });

  els.forEach(el => io.observe(el));
})();
