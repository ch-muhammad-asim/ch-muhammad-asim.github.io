// ─── Scroll reveal ───────────────────────────────────────────────
const revealEls = document.querySelectorAll('.reveal');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Stagger children of .stagger containers: 90ms apart, capped so long
// grids don't leave the last card waiting.
document.querySelectorAll('.stagger').forEach(container => {
  [...container.children]
    .filter(child => !child.classList.contains('timeline-line'))
    .forEach((child, i) => child.style.setProperty('--d', Math.min(i * 90, 720)));
});

if ('IntersectionObserver' in window) {
  const io = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('active');
      obs.unobserve(entry.target);
    });
  }, { rootMargin: '0px 0px -100px 0px' });

  revealEls.forEach(el => io.observe(el));
} else {
  // No IntersectionObserver: show everything rather than hide it.
  revealEls.forEach(el => el.classList.add('active'));
}

// ─── Stat counters ───────────────────────────────────────────────
function countUp(el) {
  const target = Number(el.dataset.countTo);
  const suffix = el.dataset.countSuffix || '';
  if (!Number.isFinite(target)) return;

  if (reducedMotion) {
    el.textContent = target + suffix;
    return;
  }

  const duration = 1400;
  const start = performance.now();

  function step(now) {
    const p = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - p, 3);          // easeOutCubic
    el.textContent = Math.round(target * eased) + suffix;
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

const counters = document.querySelectorAll('[data-count-to]');

if (counters.length && 'IntersectionObserver' in window) {
  const counterIO = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      countUp(entry.target);
      obs.unobserve(entry.target);
    });
  }, { threshold: 0.5 });

  counters.forEach(el => counterIO.observe(el));
}

// ─── Navbar scroll style ─────────────────────────────────────────
const navbar = document.querySelector('nav');

window.addEventListener('scroll', () => {
  navbar.style.background = window.scrollY > 60
    ? 'rgba(5,5,8,0.97)'
    : 'rgba(5,5,8,0.85)';
}, { passive: true });

// ─── Mobile menu toggle ───────────────────────────────────────────
const menuBtn  = document.querySelector('.mobile-menu-btn');
const navLinks = document.querySelector('.nav-links');

if (menuBtn) {
  menuBtn.addEventListener('click', () => {
    const open = navLinks.classList.toggle('active');
    menuBtn.setAttribute('aria-expanded', open);
    menuBtn.querySelector('i').className = open ? 'fas fa-times' : 'fas fa-bars';
  });
}

// Close mobile menu on link click
navLinks?.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => {
    navLinks.classList.remove('active');
    menuBtn?.setAttribute('aria-expanded', false);
    if (menuBtn) menuBtn.querySelector('i').className = 'fas fa-bars';
  });
});

// ─── Smooth scroll ───────────────────────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function(e) {
    const target = document.querySelector(this.getAttribute('href'));
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});

// ─── Active nav link on scroll ───────────────────────────────────
const sections = document.querySelectorAll('section[id]');

window.addEventListener('scroll', () => {
  let current = '';
  sections.forEach(sec => {
    if (window.scrollY >= sec.offsetTop - 220) current = sec.id;
  });
  document.querySelectorAll('.nav-links a').forEach(link => {
    link.classList.toggle('active', link.getAttribute('href') === `#${current}`);
  });
}, { passive: true });

// ─── Copyright year ───────────────────────────────────────────────
const yearEl = document.getElementById('year');
if (yearEl) yearEl.textContent = new Date().getFullYear();
