(() => {
  const panel = document.querySelector('[data-esfera-hoja]');
  const hero = document.querySelector('.ini-hero, .sec-hero');
  const esfera = document.querySelector('[data-esfera]');
  const asa = document.querySelector('[data-esfera-asa]');
  if (!panel || !hero || !esfera || !asa) return;

  const raiz = document.documentElement;
  const mq = window.matchMedia('(max-width: 720px)');
  const pestanas = panel.querySelector('[data-pestanas]');
  const accesos = hero.querySelector('.ini-accesos');
  const bola = esfera.querySelector('[data-esfera-hablar]');
  const ayuda = esfera.querySelector('[data-esfera-ayuda]');
  const ayudaTxt = ayuda ? ayuda.querySelector('span') : null;
  const ayudaIco = ayuda ? ayuda.querySelector('i') : null;
  const sintesis = window.speechSynthesis && window.SpeechSynthesisUtterance ? window.speechSynthesis : null;

  let p = 0;
  let d = 0;
  let arrastre = null;
  let suprimirHasta = 0;
  let hablando = false;

  function medir() {
    const r = panel.getBoundingClientRect();
    const topeArriba = r.top - p * d + window.scrollY;
    const nav = document.querySelector('.bottomnav');
    const navTop = nav ? nav.getBoundingClientRect().top : window.innerHeight - 100;
    const tope = pestanas || asa;
    const cab = tope.getBoundingClientRect().bottom - r.top + (pestanas ? 12 : 4);
    d = Math.max(0, Math.round(navTop - 12 - cab - topeArriba));
    if (accesos) {
      const ra = accesos.getBoundingClientRect();
      const rh = hero.getBoundingClientRect();
      esfera.style.setProperty('--esfera-top', Math.round(ra.top - rh.top - 6) + 'px');
    }
  }

  function aplicar() {
    raiz.style.setProperty('--esfera-p', p.toFixed(4));
    raiz.style.setProperty('--esfera-d', d + 'px');
  }

  function ponerHablando(on) {
    hablando = on;
    esfera.classList.toggle('hablando', on);
    if (ayudaTxt) ayudaTxt.textContent = on ? 'Hablando… toca para detener' : 'Toca la esfera para escucharlo';
    if (ayudaIco) ayudaIco.className = on ? 'fas fa-volume-high' : 'fas fa-hand-pointer';
  }

  function callar() {
    if (sintesis && hablando) sintesis.cancel();
    if (hablando) ponerHablando(false);
  }

  function fijar(nuevo) {
    p = nuevo;
    aplicar();
    const abierta = p > 0.5;
    raiz.classList.toggle('esfera-abierta', abierta);
    esfera.setAttribute('aria-hidden', abierta ? 'false' : 'true');
    if (bola) bola.tabIndex = abierta ? 0 : -1;
    asa.setAttribute('aria-expanded', abierta ? 'false' : 'true');
    asa.setAttribute('aria-label', abierta ? 'Subir la hoja' : 'Bajar la hoja para ver el resumen');
    if (!abierta) callar();
  }

  function abrir() {
    if (window.scrollY > 0) window.scrollTo(0, 0);
    medir();
    fijar(1);
  }

  function empezar(e) {
    if (!mq.matches) return;
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    if (p < 0.5 && window.scrollY > 4) return;
    medir();
    arrastre = { y: e.clientY, p0: p, movido: false };
  }

  function mover(e) {
    if (!arrastre) return;
    const dy = e.clientY - arrastre.y;
    if (!arrastre.movido) {
      if (Math.abs(dy) < 6) return;
      arrastre.movido = true;
      raiz.classList.add('esfera-arrastrando');
    }
    if (d <= 0) return;
    if (e.cancelable) e.preventDefault();
    p = Math.min(1, Math.max(0, arrastre.p0 + dy / d));
    aplicar();
  }

  function soltar() {
    if (!arrastre) return;
    const a = arrastre;
    arrastre = null;
    raiz.classList.remove('esfera-arrastrando');
    if (!a.movido) return;
    suprimirHasta = performance.now() + 400;
    const umbral = a.p0 > 0.5 ? 0.75 : 0.25;
    fijar(p > umbral ? 1 : 0);
  }

  asa.addEventListener('pointerdown', empezar);
  if (pestanas) pestanas.addEventListener('pointerdown', empezar);
  window.addEventListener('pointermove', mover, { passive: false });
  window.addEventListener('pointerup', soltar);
  window.addEventListener('pointercancel', soltar);

  asa.addEventListener('click', () => {
    if (!mq.matches || performance.now() < suprimirHasta) return;
    if (p > 0.5) fijar(0);
    else abrir();
  });

  if (pestanas) {
    pestanas.addEventListener('click', (e) => {
      if (performance.now() < suprimirHasta) {
        e.stopPropagation();
        e.preventDefault();
        return;
      }
      if (p > 0.5) fijar(0);
    }, true);
  }

  window.addEventListener('resize', () => {
    if (!mq.matches) {
      if (p) fijar(0);
      return;
    }
    medir();
    aplicar();
  });
  if (mq.addEventListener) mq.addEventListener('change', () => { if (p) fijar(0); });

  function vozEspanol() {
    const voces = sintesis.getVoices();
    return voces.find((v) => v.lang === 'es-CL')
      || voces.find((v) => v.lang === 'es-US')
      || voces.find((v) => v.lang && v.lang.toLowerCase().startsWith('es'))
      || null;
  }

  if (!sintesis) {
    if (ayuda) ayuda.hidden = true;
  } else {
    sintesis.getVoices();
    window.addEventListener('pagehide', () => sintesis.cancel());
  }

  if (bola) {
    bola.addEventListener('click', () => {
      if (!sintesis || p < 0.5) return;
      if (hablando) {
        callar();
        return;
      }
      const frase = esfera.dataset.frase;
      if (!frase) return;
      const u = new SpeechSynthesisUtterance(frase);
      const v = vozEspanol();
      u.lang = v ? v.lang : 'es-CL';
      if (v) u.voice = v;
      u.rate = 1;
      u.pitch = 1;
      u.onend = () => ponerHablando(false);
      u.onerror = () => ponerHablando(false);
      sintesis.cancel();
      ponerHablando(true);
      sintesis.speak(u);
    });
  }

  window.finappEsfera = {
    disponible: () => mq.matches,
    abierta: () => p > 0.5,
    abrir: () => { if (mq.matches) abrir(); },
    cerrar: () => fijar(0),
  };

  medir();
  fijar(0);
})();
