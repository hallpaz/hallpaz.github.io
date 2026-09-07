/**
 * Theme toggle and interactive utilities
 */

(function () {
  const THEME_KEY = 'hallpaz-theme';

  function getPreferredTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === 'dark' || saved === 'light') {
      return saved;
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
    updateToggleIcons(theme);
  }

  function updateToggleIcons(theme) {
    const sunIcons = document.querySelectorAll('.theme-icon-sun');
    const moonIcons = document.querySelectorAll('.theme-icon-moon');

    if (theme === 'dark') {
      sunIcons.forEach(el => el.style.display = 'block');
      moonIcons.forEach(el => el.style.display = 'none');
    } else {
      sunIcons.forEach(el => el.style.display = 'none');
      moonIcons.forEach(el => el.style.display = 'block');
    }
  }

  // Initialize theme
  const initialTheme = getPreferredTheme();
  setTheme(initialTheme);

  document.addEventListener('DOMContentLoaded', () => {
    updateToggleIcons(initialTheme);

    // Theme toggle button click
    const toggleButtons = document.querySelectorAll('#theme-toggle-btn');
    toggleButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        setTheme(newTheme);
      });
    });

    // Mobile nav menu toggle
    const mobileBtn = document.getElementById('mobile-menu-btn');
    const navMenu = document.getElementById('nav-menu');
    if (mobileBtn && navMenu) {
      mobileBtn.addEventListener('click', () => {
        navMenu.classList.toggle('open');
      });
    }

    // BibTeX drawer toggles
    document.querySelectorAll('.bibtex-toggle-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const targetId = btn.getAttribute('data-target');
        const drawer = document.getElementById(targetId);
        if (drawer) {
          drawer.classList.toggle('open');
        }
      });
    });

    // BibTeX copy buttons
    document.querySelectorAll('.bibtex-copy-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-target');
        const drawer = document.getElementById(targetId);
        if (drawer) {
          const pre = drawer.querySelector('pre');
          if (pre) {
            navigator.clipboard.writeText(pre.innerText).then(() => {
              const originalText = btn.innerText;
              btn.innerText = 'Copied!';
              setTimeout(() => {
                btn.innerText = originalText;
              }, 2000);
            });
          }
        }
      });
    });
  });

  // Listen for system theme change if no explicit user preference is set
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem(THEME_KEY)) {
      setTheme(e.matches ? 'dark' : 'light');
    }
  });
})();
