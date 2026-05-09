// ─── Scroll reveal ───────────────────────────────────────────────
const revealEls = document.querySelectorAll('.reveal');

function reveal() {
  revealEls.forEach(el => {
    const top = el.getBoundingClientRect().top;
    if (top < window.innerHeight - 100) el.classList.add('active');
  });
}

window.addEventListener('scroll', reveal, { passive: true });
window.addEventListener('load', reveal);

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
