(() => {
  const fuente = document.querySelector('[data-voz-frase]');
  const botones = Array.from(document.querySelectorAll('[data-escuchar]'));
  if (!fuente || !botones.length || !fuente.dataset.voz || !fuente.dataset.vozUrl || !window.fetch) return;

  const raiz = document.documentElement;
  const esfera = document.querySelector('.i2c-esfera');
  const sol = document.querySelector('[data-sol]');
  const palabras = sol ? Array.from(sol.querySelectorAll('[data-sol-palabra]')) : [];
  const estadoSol = sol ? sol.querySelector('[data-sol-estado]') : null;
  const consulta = window.matchMedia ? window.matchMedia('(max-width: 720px)') : null;
  const TEXTOS = { quieto: 'Escuchar mi mes', cargando: 'Preparando la voz…', hablando: 'Detener' };
  const ICONOS = { quieto: 'fas fa-play', cargando: 'fas fa-spinner fa-spin', hablando: 'fas fa-stop' };
  let estado = 'quieto';
  let audio = null;
  let audioUrl = '';
  let pedido = null;
  let turno = 0;
  let abierto = false;
  let cierre = null;

  function enTelefono() {
    return !!(sol && esfera && consulta && consulta.matches);
  }

  function marcar(indice) {
    palabras.forEach((p, i) => {
      p.classList.toggle('dicha', i < indice);
      p.classList.toggle('ahora', i === indice);
    });
  }

  function poner(nuevo) {
    const antes = estado;
    estado = nuevo;
    raiz.classList.toggle('i2c-hablando', nuevo === 'hablando');
    raiz.classList.toggle('i2c-cargando', nuevo === 'cargando');
    botones.forEach((b) => {
      const txt = b.querySelector('[data-escuchar-txt]');
      const ico = b.querySelector('[data-escuchar-ico]');
      if (txt) txt.textContent = TEXTOS[nuevo];
      if (ico) ico.className = ICONOS[nuevo];
      if (txt) b.setAttribute('aria-pressed', nuevo === 'quieto' ? 'false' : 'true');
    });
    if (!sol) return;
    sol.classList.toggle('hablando', nuevo !== 'quieto');
    if (estadoSol) estadoSol.textContent = nuevo === 'quieto' ? 'Tu mes, en voz alta' : nuevo === 'cargando' ? 'Preparando la voz' : 'Hablando';
    if (nuevo === 'cargando') marcar(-1);
    if (nuevo === 'quieto' && antes === 'hablando') marcar(palabras.length);
  }

  function pedir() {
    if (audioUrl) return Promise.resolve(audioUrl);
    if (pedido) return pedido;
    const datos = new FormData();
    datos.append('frase', fuente.dataset.voz);
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    pedido = fetch(fuente.dataset.vozUrl, {
      method: 'POST', body: datos, credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': token ? token.value : '' },
    }).then((r) => (r.ok && (r.headers.get('Content-Type') || '').indexOf('audio') === 0 ? r.blob() : null))
      .then((b) => { pedido = null; if (b) audioUrl = URL.createObjectURL(b); return audioUrl; })
      .catch(() => { pedido = null; return ''; });
    return pedido;
  }

  function silencio() {
    const b = new ArrayBuffer(46);
    const v = new DataView(b);
    const t = (o, s) => { for (let i = 0; i < s.length; i += 1) v.setUint8(o + i, s.charCodeAt(i)); };
    t(0, 'RIFF'); v.setUint32(4, 38, true); t(8, 'WAVE'); t(12, 'fmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, 8000, true); v.setUint32(28, 16000, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    t(36, 'data'); v.setUint32(40, 2, true); v.setInt16(44, 0, true);
    return URL.createObjectURL(new Blob([b], { type: 'audio/wav' }));
  }

  function reproductor() {
    if (audio) return audio;
    audio = new Audio();
    const fin = () => { if (estado === 'hablando') poner('quieto'); };
    audio.addEventListener('ended', fin);
    audio.addEventListener('pause', fin);
    audio.addEventListener('error', fin);
    audio.addEventListener('timeupdate', () => {
      if (estado !== 'hablando' || !palabras.length || !audio.duration) return;
      marcar(Math.min(palabras.length - 1, Math.floor(audio.currentTime / audio.duration * palabras.length)));
    });
    return audio;
  }

  function detener() {
    turno += 1;
    if (audio && !audio.paused) audio.pause();
    poner('quieto');
  }

  function hablar() {
    const a = reproductor();
    if (!audioUrl) {
      a.src = silencio();
      const desbloqueo = a.play();
      if (desbloqueo && desbloqueo.catch) desbloqueo.catch(() => {});
    }
    poner('cargando');
    turno += 1;
    const mio = turno;
    pedir().then((url) => {
      if (mio !== turno || estado !== 'cargando') return;
      if (!url) { poner('quieto'); return; }
      a.src = url;
      a.currentTime = 0;
      poner('hablando');
      const intento = a.play();
      if (intento && intento.catch) intento.catch(() => { if (estado === 'hablando') poner('quieto'); });
    });
  }

  function centrar() {
    const r = esfera.getBoundingClientRect();
    const ancho = window.innerWidth || raiz.clientWidth;
    const alto = window.innerHeight || raiz.clientHeight;
    const medida = Math.min(200, ancho * .5);
    const cx = ancho / 2;
    const cy = Math.max(160, Math.min(alto * .3, 260));
    esfera.style.setProperty('--sol-x', (cx - (r.left + r.width / 2)) + 'px');
    esfera.style.setProperty('--sol-y', (cy - (r.top + r.height / 2)) + 'px');
    esfera.style.setProperty('--sol-s', String(medida / r.width));
    sol.style.setProperty('--sol-cy', cy + 'px');
    sol.style.setProperty('--sol-r', (medida / 2) + 'px');
  }

  function abrir() {
    if (abierto) return;
    abierto = true;
    clearTimeout(cierre);
    window.scrollTo(0, 0);
    centrar();
    raiz.classList.add('i2c-sol-abierto');
    raiz.classList.remove('i2c-sol-saliendo');
    sol.setAttribute('aria-hidden', 'false');
    hablar();
  }

  function cerrar() {
    if (!abierto) return;
    abierto = false;
    detener();
    raiz.classList.remove('i2c-sol-abierto');
    raiz.classList.add('i2c-sol-saliendo');
    sol.setAttribute('aria-hidden', 'true');
    cierre = setTimeout(() => raiz.classList.remove('i2c-sol-saliendo'), 900);
  }

  function tocar(e) {
    const desdeEsfera = e && e.currentTarget === esfera;
    if (desdeEsfera && enTelefono()) {
      if (!abierto) abrir();
      else if (estado === 'quieto') hablar();
      else cerrar();
      return;
    }
    if (estado !== 'quieto') { detener(); return; }
    hablar();
  }

  botones.forEach((b) => b.addEventListener('click', tocar));
  if (sol) {
    sol.querySelectorAll('[data-sol-cerrar]').forEach((b) => b.addEventListener('click', cerrar));
    sol.querySelectorAll('[data-sol-detener]').forEach((b) => b.addEventListener('click', detener));
    sol.querySelectorAll('[data-sol-otra]').forEach((b) => b.addEventListener('click', hablar));
    sol.querySelectorAll('[data-charla-abrir]').forEach((b) => b.addEventListener('click', cerrar));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && abierto) cerrar(); });
    if (consulta && consulta.addEventListener) consulta.addEventListener('change', () => { if (!consulta.matches) cerrar(); });
  }
  window.addEventListener('pagehide', () => { if (audio) audio.pause(); });
})();
