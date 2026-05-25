/* ============================================================
   Unkle Funk — unklefunk.music — main.js v3
   Chicago house music artist hub
   ============================================================ */

const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ── Hero Canvas Equalizer ────────────────────────────────
;(function () {
  const canvas = document.getElementById('heroCanvas');
  if (!canvas || prefersReducedMotion) return;

  const ctx = canvas.getContext('2d');
  const BAR_COUNT = 96;
  const heights   = new Float32Array(BAR_COUNT).fill(0.05);
  const targets   = new Float32Array(BAR_COUNT).fill(0.05);
  let raf;

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width  = canvas.offsetWidth  * dpr;
    canvas.height = canvas.offsetHeight * dpr;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
  }

  function newTargets() {
    for (let i = 0; i < BAR_COUNT; i++) {
      const center = Math.abs(i / BAR_COUNT - 0.5);
      const peak   = Math.max(0.08, 0.7 * (1 - center * 1.5));
      targets[i]   = Math.random() * peak + 0.03;
    }
  }

  function draw() {
    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;
    ctx.clearRect(0, 0, w, h);

    const barW  = w / BAR_COUNT;
    const midY  = h * 0.55;
    const maxH  = h * 0.32;
    const gap   = barW * 0.4;

    for (let i = 0; i < BAR_COUNT; i++) {
      heights[i] += (targets[i] - heights[i]) * 0.05;

      const bh   = heights[i] * maxH;
      const x    = i * barW + gap / 2;
      const bw   = barW - gap;
      const r    = Math.min(bw / 2, 3);

      // Top bar — gradient gold
      const gTop = ctx.createLinearGradient(0, midY - bh, 0, midY);
      gTop.addColorStop(0, 'rgba(232, 201, 113, 0.7)');
      gTop.addColorStop(0.5, 'rgba(201,168,76,0.45)');
      gTop.addColorStop(1, 'rgba(201,168,76,0.1)');

      ctx.beginPath();
      ctx.roundRect(x, midY - bh, bw, bh, [r, r, 0, 0]);
      ctx.fillStyle = gTop;
      ctx.fill();

      // Mirror (reflected) bar
      const gBot = ctx.createLinearGradient(0, midY, 0, midY + bh * 0.45);
      gBot.addColorStop(0, 'rgba(201,168,76,0.18)');
      gBot.addColorStop(1, 'rgba(201,168,76,0)');

      ctx.beginPath();
      ctx.roundRect(x, midY, bw, bh * 0.45, [0, 0, r, r]);
      ctx.fillStyle = gBot;
      ctx.fill();
    }
  }

  let tick = 0;
  function loop() {
    tick++;
    if (tick % 10 === 0) newTargets();
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

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) cancelAnimationFrame(raf);
    else loop();
  });
})();


// ── Hero Canvas Sparks (drifting embers) ─────────────────
;(function () {
  const canvas = document.getElementById('sparkCanvas');
  if (!canvas || prefersReducedMotion) return;
  const ctx = canvas.getContext('2d');

  const SPARKS = [];
  const COUNT = window.innerWidth < 700 ? 22 : 38;

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width  = canvas.offsetWidth  * dpr;
    canvas.height = canvas.offsetHeight * dpr;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
  }

  function spawnSpark() {
    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;
    return {
      x: Math.random() * w,
      y: h + Math.random() * 60,
      vx: (Math.random() - 0.5) * 0.18,
      vy: -0.18 - Math.random() * 0.55,
      r: Math.random() * 1.6 + 0.4,
      a: Math.random() * 0.55 + 0.15,
      twinkle: Math.random() * Math.PI * 2,
    };
  }

  for (let i = 0; i < COUNT; i++) {
    const s = spawnSpark();
    s.y = Math.random() * canvas.offsetHeight;
    SPARKS.push(s);
  }

  function frame() {
    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;
    ctx.clearRect(0, 0, w, h);

    for (let i = 0; i < SPARKS.length; i++) {
      const s = SPARKS[i];
      s.x += s.vx;
      s.y += s.vy;
      s.twinkle += 0.04;

      if (s.y < -10 || s.x < -10 || s.x > w + 10) {
        SPARKS[i] = spawnSpark();
        continue;
      }
      const flick = 0.7 + Math.sin(s.twinkle) * 0.3;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(232, 201, 113, ${s.a * flick})`;
      ctx.shadowColor = 'rgba(201,168,76,0.6)';
      ctx.shadowBlur = 8;
      ctx.fill();
      ctx.shadowBlur = 0;
    }
    requestAnimationFrame(frame);
  }

  resize();
  frame();
  window.addEventListener('resize', () => { resize(); });
})();


// ── Cursor Spotlight ─────────────────────────────────────
;(function () {
  const spot = document.getElementById('spotlight');
  if (!spot || prefersReducedMotion) return;
  if (window.matchMedia('(hover: none)').matches) return;

  let tx = window.innerWidth / 2, ty = window.innerHeight / 2;
  let x = tx, y = ty;
  let active = false;

  document.addEventListener('pointermove', e => {
    tx = e.clientX;
    ty = e.clientY;
    if (!active) {
      active = true;
      document.body.classList.add('has-spot');
    }
  }, { passive: true });

  document.addEventListener('pointerleave', () => {
    document.body.classList.remove('has-spot');
    active = false;
  });

  function tick() {
    x += (tx - x) * 0.18;
    y += (ty - y) * 0.18;
    spot.style.transform = `translate(${x - 300}px, ${y - 300}px)`;
    requestAnimationFrame(tick);
  }
  tick();
})();


// ── Kinetic Typography (split letter reveal) ────────────
;(function () {
  const els = document.querySelectorAll('[data-split]');
  els.forEach(el => {
    const text = el.textContent;
    el.textContent = '';
    text.split('').forEach((char, i) => {
      const span = document.createElement('span');
      span.className = 'char';
      span.textContent = char === ' ' ? ' ' : char;
      span.style.animationDelay = (0.04 * i + 0.1) + 's';
      el.appendChild(span);
    });
  });
})();


// ── Magnetic Buttons ────────────────────────────────────
;(function () {
  if (prefersReducedMotion) return;
  if (window.matchMedia('(hover: none)').matches) return;

  const els = document.querySelectorAll('[data-magnetic]');
  els.forEach(el => {
    let raf = null;
    let tx = 0, ty = 0, x = 0, y = 0;

    function animate() {
      x += (tx - x) * 0.18;
      y += (ty - y) * 0.18;
      el.style.transform = `translate(${x}px, ${y}px)`;
      if (Math.abs(tx - x) > 0.1 || Math.abs(ty - y) > 0.1) {
        raf = requestAnimationFrame(animate);
      } else {
        raf = null;
      }
    }

    el.addEventListener('pointermove', e => {
      const rect = el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      tx = (e.clientX - cx) * 0.18;
      ty = (e.clientY - cy) * 0.18;
      if (!raf) raf = requestAnimationFrame(animate);
    });

    el.addEventListener('pointerleave', () => {
      tx = 0; ty = 0;
      if (!raf) raf = requestAnimationFrame(animate);
    });
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

  function onScroll() {
    nav.classList.toggle('scrolled', window.scrollY > 30);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  function openDrawer() {
    drawer.classList.add('open');
    drawerOverlay.classList.add('show');
    navToggle.classList.add('open');
    navToggle.setAttribute('aria-expanded', 'true');
    drawer.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }
  function closeDrawer() {
    drawer.classList.remove('open');
    drawerOverlay.classList.remove('show');
    navToggle.classList.remove('open');
    navToggle.setAttribute('aria-expanded', 'false');
    drawer.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  navToggle.addEventListener('click', () => {
    if (drawer.classList.contains('open')) closeDrawer();
    else openDrawer();
  });

  drawerOverlay.addEventListener('click', closeDrawer);
  drawerLinks.forEach(link => link.addEventListener('click', closeDrawer));

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && drawer.classList.contains('open')) closeDrawer();
  });
})();


// ── Smooth scroll for anchor links ───────────────────────
;(function () {
  const NAV_H = 72;
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', e => {
      const href = anchor.getAttribute('href');
      if (href === '#' || href === '#top') {
        e.preventDefault();
        window.scrollTo({ top: 0, behavior: 'smooth' });
        return;
      }
      const target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      const top = target.getBoundingClientRect().top + window.scrollY - NAV_H + 4;
      window.scrollTo({ top, behavior: 'smooth' });
    });
  });
})();


// ── Scroll-spy: highlight active nav link ───────────────
;(function () {
  const sections = ['about', 'podcast', 'music', 'mixes', 'discography', 'booking', 'connect']
    .map(id => document.getElementById(id))
    .filter(Boolean);
  const links = document.querySelectorAll('.nav__link');

  if (!('IntersectionObserver' in window) || sections.length === 0) return;

  const map = new Map();
  links.forEach(link => {
    const href = link.getAttribute('href');
    if (href && href.startsWith('#')) map.set(href.slice(1), link);
  });

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      const id = entry.target.id;
      const link = map.get(id);
      if (!link) return;
      if (entry.isIntersecting) {
        links.forEach(l => l.classList.remove('active'));
        link.classList.add('active');
      }
    });
  }, { rootMargin: '-40% 0px -55% 0px', threshold: 0 });

  sections.forEach(s => observer.observe(s));
})();


// ── Scroll reveal ────────────────────────────────────────
;(function () {
  const selectors = [
    '.section-title', '.about__body', '.stats', '.vinyl', '.about__quote',
    '.now__card',
    '.podcast__desc', '.podcast__embed', '.podcast__platforms',
    '.music-embed', '.dj-chart', '.release', '.connect-card',
    '.mix', '.mixes__footer',
    '.releases__footer',
    '.booking__col', '.booking__list',
    '.newsletter__inner',
    '.section__head'
  ];
  const els = document.querySelectorAll(selectors.join(', '));
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


// ── Counter animation for stats ─────────────────────────
;(function () {
  const counters = document.querySelectorAll('[data-counter]');
  if (counters.length === 0) return;

  const animate = (el) => {
    const end = parseInt(el.dataset.counter, 10);
    const suffix = el.dataset.suffix || '';
    if (Number.isNaN(end)) return;
    const duration = 1200;
    const start = performance.now();
    function step(now) {
      const t = Math.min(1, (now - start) / duration);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      const val = Math.floor(end * eased);
      el.textContent = val + suffix;
      if (t < 1) requestAnimationFrame(step);
      else el.textContent = end + suffix;
    }
    requestAnimationFrame(step);
  };

  if (!('IntersectionObserver' in window)) {
    counters.forEach(animate);
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        animate(entry.target);
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.5 });
  counters.forEach(c => io.observe(c));
})();


// ── Live ticker (rotate hero "Now Spinning" text) ───────
;(function () {
  const el = document.getElementById('liveTicker');
  if (!el) return;
  const messages = [
    "Sunday Slackin' Season 9 · Now Spinning",
    'Deep House from Chicago',
    'New mix Sunday · 9am CST',
    '16+ Years on the Decks',
    'Catalog on Beatport · Traxsource',
  ];
  let i = 0;
  setInterval(() => {
    i = (i + 1) % messages.length;
    el.style.opacity = '0';
    setTimeout(() => {
      el.textContent = messages[i];
      el.style.opacity = '1';
    }, 220);
  }, 4200);
  el.style.transition = 'opacity 0.22s ease';
})();


// ── Newsletter form ─────────────────────────────────────
;(function () {
  const form = document.getElementById('newsletterForm');
  if (!form) return;
  const note = document.getElementById('newsletterNote');
  const input = document.getElementById('newsletterEmail');

  form.addEventListener('submit', e => {
    e.preventDefault();
    const email = (input.value || '').trim();
    const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    if (!valid) {
      note.textContent = '⚠ Please enter a valid email.';
      note.style.color = '#d92b6c';
      input.focus();
      return;
    }
    // Fallback: open mailto so the artist receives the request without server.
    const subject = encodeURIComponent('Newsletter Signup — unklefunk.music');
    const body = encodeURIComponent(`Please add me to the Unkle Funk mailing list:\n\n${email}\n\nThanks!`);
    window.location.href = `mailto:hi@unklefunk.music?subject=${subject}&body=${body}`;

    note.textContent = '✓ Thanks — opening your email client to confirm.';
    note.style.color = '#c9a84c';
    input.value = '';
  });
})();


// ── Back to top ─────────────────────────────────────────
;(function () {
  const btn = document.getElementById('backToTop');
  if (!btn) return;
  function onScroll() {
    btn.classList.toggle('show', window.scrollY > window.innerHeight * 0.8);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
})();


// ── Copyright year ──────────────────────────────────────
;(function () {
  const el = document.getElementById('copyrightYear');
  if (el) el.textContent = new Date().getFullYear();
})();
