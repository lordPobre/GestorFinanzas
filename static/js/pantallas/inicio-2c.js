(() => {
  const fuente = document.querySelector('[data-voz-frase]');
  const botones = Array.from(document.querySelectorAll('[data-escuchar]'));
  if (!fuente || !botones.length || !fuente.dataset.voz || !fuente.dataset.vozUrl || !window.fetch) return;

  const raiz = document.documentElement;
  const TEXTOS = { quieto: 'Escuchar mi mes', cargando: 'Preparando la voz…', hablando: 'Detener' };
  const ICONOS = { quieto: 'fas fa-play', cargando: 'fas fa-spinner fa-spin', hablando: 'fas fa-stop' };
  let estado = 'quieto';
  let audio = null;
  let audioUrl = '';
  let pedido = null;
  let turno = 0;

  function poner(nuevo) {
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
    return audio;
  }

  function tocar() {
    if (estado !== 'quieto') {
      turno += 1;
      if (audio && !audio.paused) audio.pause();
      poner('quieto');
      return;
    }
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
      poner('hablando');
      const intento = a.play();
      if (intento && intento.catch) intento.catch(() => { if (estado === 'hablando') poner('quieto'); });
    });
  }

  botones.forEach((b) => b.addEventListener('click', tocar));
  window.addEventListener('pagehide', () => { if (audio) audio.pause(); });
})();
