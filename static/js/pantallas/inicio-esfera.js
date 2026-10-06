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
  const bienvenida = esfera.hasAttribute('data-bienvenida');
  const hola = esfera.querySelector('[data-esfera-hola]');
  const cambio = esfera.querySelector('[data-esfera-cambio]');

  function saludoDeLaHora() {
    const h = new Date().getHours();
    if (h >= 7 && h < 12) return 'Buenos días';
    if (h >= 12 && h < 20) return 'Buenas tardes';
    return 'Buenas noches';
  }
  esfera.querySelectorAll('[data-saludo]').forEach((n) => { n.textContent = saludoDeLaHora(); });

  let p = 0;
  let d = 0;
  let arrastre = null;
  let suprimirHasta = 0;
  let estado = 'quieto';
  let turno = 0;
  let avisoHasta = 0;
  let silencioUrl = '';
  let audio = null;
  let audioUrl = '';
  let audioPara = '';
  let pedido = null;

  function claveAudio() {
    const conCambio = cambio && raiz.classList.contains('esfera-bienvenida');
    return (esfera.dataset.voz || '') + '|' + (conCambio ? (cambio.dataset.voz || '') + '|' + ((hola && hola.dataset.voz) || '') : '');
  }

  function pedirAudio() {
    if (!esfera.dataset.voz || !esfera.dataset.vozUrl || !window.fetch) return null;
    const clave = claveAudio();
    if (audioPara === clave && (audioUrl || pedido)) return pedido;
    audioPara = clave;
    audioUrl = '';
    const datos = new FormData();
    datos.append('frase', esfera.dataset.voz);
    if (cambio && raiz.classList.contains('esfera-bienvenida') && cambio.dataset.voz) {
      datos.append('cambio', cambio.dataset.voz);
      datos.append('saludo', saludoDeLaHora());
      if (hola && hola.dataset.voz) datos.append('nombre', hola.dataset.voz);
    }
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    pedido = fetch(esfera.dataset.vozUrl, {
      method: 'POST', body: datos, credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': token ? token.value : '' },
    }).then((r) => (r.ok && (r.headers.get('Content-Type') || '').indexOf('audio') === 0 ? r.blob() : null))
      .then((b) => {
        pedido = null;
        if (b && audioPara === clave) audioUrl = URL.createObjectURL(b);
        return audioUrl;
      })
      .catch(() => { pedido = null; return ''; });
    return pedido;
  }

  function medir() {
    const r = panel.getBoundingClientRect();
    const topeArriba = r.top - p * d + window.scrollY;
    const nav = document.querySelector('.bottomnav');
    const navTop = nav ? nav.getBoundingClientRect().top : window.innerHeight - 100;
    const tope = pestanas || asa;
    const cab = tope.getBoundingClientRect().bottom - r.top + (pestanas ? 12 : 4);
    d = Math.max(0, Math.round(navTop - 12 - cab - topeArriba));
    const rh = hero.getBoundingClientRect();
    if (raiz.classList.contains('esfera-bienvenida')) {
      const alto = esfera.offsetHeight;
      const zona = navTop - 12 - cab;
      const arriba = Math.max(16, Math.round((zona - alto) / 2));
      esfera.style.setProperty('--esfera-top', Math.round(arriba - rh.top) + 'px');
      return;
    }
    let top = accesos ? accesos.getBoundingClientRect().top - rh.top - 6 : 0;
    hero.querySelectorAll('.ini-vistas, .ini-chips, .ini-valor:not([hidden])').forEach((el) => {
      const re = el.getBoundingClientRect();
      if (re.height) top = Math.max(top, re.bottom - rh.top + 24);
    });
    if (top) esfera.style.setProperty('--esfera-top', Math.round(top) + 'px');
  }

  function aplicar() {
    raiz.style.setProperty('--esfera-p', p.toFixed(4));
    raiz.style.setProperty('--esfera-d', d + 'px');
  }

  const AYUDA = {
    quieto: ['Toca la esfera para escucharlo', 'fas fa-hand-pointer'],
    cargando: ['Preparando la voz…', 'fas fa-spinner fa-spin'],
    hablando: ['Hablando… toca para detener', 'fas fa-volume-high'],
  };

  function ponerEstado(nuevo) {
    estado = nuevo;
    avisoHasta = 0;
    esfera.classList.toggle('hablando', nuevo === 'hablando');
    esfera.classList.toggle('cargando', nuevo === 'cargando');
    if (ayudaTxt) ayudaTxt.textContent = AYUDA[nuevo][0];
    if (ayudaIco) ayudaIco.className = AYUDA[nuevo][1];
  }

  function avisar(texto) {
    ponerEstado('quieto');
    if (ayudaTxt) ayudaTxt.textContent = texto;
    if (ayudaIco) ayudaIco.className = 'fas fa-circle-exclamation';
    const hasta = performance.now() + 3500;
    avisoHasta = hasta;
    setTimeout(() => { if (avisoHasta === hasta && estado === 'quieto') ponerEstado('quieto'); }, 3600);
  }

  function callar() {
    turno += 1;
    if (audio && !audio.paused) audio.pause();
    if (estado !== 'quieto') ponerEstado('quieto');
  }

  function silencio() {
    if (silencioUrl) return silencioUrl;
    const b = new ArrayBuffer(46);
    const v = new DataView(b);
    const t = (o, s) => { for (let i = 0; i < s.length; i += 1) v.setUint8(o + i, s.charCodeAt(i)); };
    t(0, 'RIFF'); v.setUint32(4, 38, true); t(8, 'WAVE'); t(12, 'fmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, 8000, true); v.setUint32(28, 16000, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    t(36, 'data'); v.setUint32(40, 2, true); v.setInt16(44, 0, true);
    silencioUrl = URL.createObjectURL(new Blob([b], { type: 'audio/wav' }));
    return silencioUrl;
  }

  function reproductor() {
    if (audio) return audio;
    audio = new Audio();
    const fin = () => { if (estado === 'hablando') ponerEstado('quieto'); };
    audio.addEventListener('ended', fin);
    audio.addEventListener('pause', fin);
    audio.addEventListener('error', fin);
    return audio;
  }

  function sonar(url) {
    const a = reproductor();
    a.src = url;
    ponerEstado('hablando');
    const intento = a.play();
    if (intento && intento.catch) intento.catch(() => { if (estado === 'hablando') avisar('Toca de nuevo para escucharlo'); });
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
    if (abierta) pedirAudio();
    if (!abierta) {
      callar();
      if (raiz.classList.contains('esfera-bienvenida')) {
        raiz.classList.remove('esfera-bienvenida');
        medir();
      }
    }
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

  let pendiente = 0;
  function remedir() {
    if (pendiente || !mq.matches) return;
    pendiente = requestAnimationFrame(() => {
      pendiente = 0;
      medir();
      aplicar();
    });
  }
  new MutationObserver(remedir).observe(hero, { subtree: true, childList: true, attributes: true, attributeFilter: ['hidden'] });
  if (window.ResizeObserver) new ResizeObserver(remedir).observe(hero);

  if (!esfera.dataset.voz && ayuda) ayuda.hidden = true;
  window.addEventListener('pagehide', () => { if (audio) audio.pause(); });

  if (bola) {
    bola.addEventListener('click', () => {
      if (p < 0.5 || !esfera.dataset.voz) return;
      if (estado !== 'quieto') {
        callar();
        return;
      }
      const clave = claveAudio();
      if (audioUrl && audioPara === clave) {
        sonar(audioUrl);
        return;
      }
      const a = reproductor();
      a.src = silencio();
      const desbloqueo = a.play();
      if (desbloqueo && desbloqueo.catch) desbloqueo.catch(() => {});
      ponerEstado('cargando');
      turno += 1;
      const mio = turno;
      Promise.resolve(pedirAudio()).then((url) => {
        if (mio !== turno || estado !== 'cargando') return;
        if (url && audioPara === clave) sonar(url);
        else avisar('La voz no está disponible ahora');
      });
    });
  }

  window.finappEsfera = {
    disponible: () => mq.matches,
    abierta: () => p > 0.5,
    abrir: () => { if (mq.matches) abrir(); },
    cerrar: () => fijar(0),
  };

  if (bienvenida && mq.matches) {
    raiz.classList.add('esfera-bienvenida');
    requestAnimationFrame(() => abrir());
  } else {
    medir();
    fijar(0);
  }
})();
