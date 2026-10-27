(() => {
  if (!/Android/i.test(navigator.userAgent)) return;
  const raiz = document.documentElement;
  raiz.classList.add('android');
  if (matchMedia('(display-mode: standalone)').matches || matchMedia('(display-mode: minimal-ui)').matches) raiz.classList.add('android-app');
})();
