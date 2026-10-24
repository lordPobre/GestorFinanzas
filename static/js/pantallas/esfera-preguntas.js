(() => {
  const raiz = document.querySelector('[data-charla]');
  const abrir = document.querySelector('[data-charla-abrir]');
  if (!raiz || !abrir) return;

  const html = document.documentElement;
  const MAX = 4;
  const form = raiz.querySelector('[data-charla-form]');
  const campo = raiz.querySelector('[data-charla-campo]');
  const enviar = form.querySelector('button[type=submit]');
  const contador = raiz.querySelector('[data-charla-contador]');
  const estadoTxt = raiz.querySelector('[data-charla-estado]');
  const respuesta = raiz.querySelector('[data-charla-respuesta]');
  const antes = raiz.querySelector('[data-charla-antes]');
  const final = raiz.querySelector('[data-charla-final]');
  const repetir = raiz.querySelector('[data-charla-repetir]');
  const bola = raiz.querySelector('[data-charla-bola]');
  const avisoTitulo = raiz.querySelector('[data-charla-aviso-titulo]');
  const avisoNota = raiz.querySelector('[data-charla-aviso-nota]');
  const avisoEnlace = raiz.querySelector('[data-charla-aviso-enlace]');
  const esferaMes = document.querySelector('[data-esfera]');
  const estadoMes = raiz.dataset.estado;
  const mic = raiz.querySelector('[data-charla-mic]');
  const graba = raiz.querySelector('[data-charla-graba]');
  const parar = raiz.querySelector('[data-charla-parar]');
  const onda = raiz.querySelector('[data-charla-onda]');
  const tiempo = raiz.querySelector('[data-charla-tiempo]');
  const ayuda = raiz.querySelector('[data-charla-ayuda]');
  const ayudaTxt = raiz.querySelector('[data-charla-ayuda-txt]');
  const urlOir = raiz.dataset.urlOir || '';
  const MAX_SEG = 30;
  const MIN_MS = 700;
  const UMBRAL = 0.015;
  const BARRAS = 30;
  const vistas = {};
  raiz.querySelectorAll('[data-vista]').forEach((v) => { vistas[v.dataset.vista] = v; });

  let conversacion = '';
  let anterior = '';
  let turno = 0;
  let ocupado = false;
  let cerrada = false;
  let vozFirmada = '';
  let audio = null;
  let audioUrl = '';
  let silencioUrl = '';
  let ultimoFoco = null;
  let grab = null;
  let puedeGrabar = !!(urlOir && navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  const barras = [];
  for (let i = 0; i < BARRAS; i += 1) barras.push(onda.appendChild(document.createElement('i')));

  function verVista(nombre) {
    Object.keys(vistas).forEach((k) => { vistas[k].hidden = k !== nombre; });
  }

  function modo(m, texto, aviso) {
    raiz.dataset.modo = m;
    if (texto !== undefined) estadoTxt.textContent = texto;
    estadoTxt.classList.toggle('aviso', !!aviso);
  }

  function ponerContador(n) {
    contador.textContent = `Pregunta ${Math.min(MAX, Math.max(1, n))} de ${MAX}`;
  }

  function ponerBotones() {
    const hay = campo.value.trim() !== '';
    mic.hidden = !puedeGrabar || hay;
    enviar.hidden = puedeGrabar && !hay;
  }

  function bloquear(si) {
    ocupado = si;
    campo.disabled = si || cerrada;
    enviar.disabled = si || cerrada;
    mic.disabled = si || cerrada;
    ponerBotones();
  }

  function token() {
    const t = form.querySelector('[name=csrfmiddlewaretoken]');
    return t ? t.value : '';
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

  function marcar() {
    if (!audio || !audio.duration || !isFinite(audio.duration)) return;
    const palabras = respuesta.children;
    const actual = Math.floor((audio.currentTime / audio.duration) * palabras.length);
    for (let i = 0; i < palabras.length; i += 1) {
      palabras[i].className = i < actual ? 'dicha' : (i === actual ? 'ahora' : '');
    }
  }

  function terminoVoz() {
    respuesta.classList.remove('leyendo');
    Array.from(respuesta.children).forEach((s) => { s.className = ''; });
    if (raiz.dataset.modo !== 'habla') return;
    if (cerrada) modo('quieto', 'Toca la esfera para escuchar cómo vas');
    else if (turno >= MAX) modo('quieto', 'Toca la esfera para escucharlo de nuevo');
    else modo('quieto', 'Escribe otra pregunta o toca la esfera para repetir');
  }

  function reproductor() {
    if (audio) return audio;
    audio = new Audio();
    audio.addEventListener('ended', terminoVoz);
    audio.addEventListener('pause', terminoVoz);
    audio.addEventListener('error', terminoVoz);
    audio.addEventListener('timeupdate', marcar);
    return audio;
  }

  function desbloquearAudio() {
    const a = reproductor();
    a.src = silencio();
    const p = a.play();
    if (p && p.catch) p.catch(() => {});
  }

  function pararVoz() {
    if (audio && !audio.paused) audio.pause();
  }

  function olvidarAudio() {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    audioUrl = '';
  }

  function pedirVoz() {
    const datos = new FormData();
    datos.append('frase', vozFirmada);
    return fetch(raiz.dataset.vozUrl, {
      method: 'POST', body: datos, credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': token() },
    }).then((r) => (r.ok && (r.headers.get('Content-Type') || '').indexOf('audio') === 0 ? r.blob() : null))
      .then((b) => {
        olvidarAudio();
        audioUrl = b ? URL.createObjectURL(b) : '';
        return audioUrl;
      })
      .catch(() => '');
  }

  function fallaVoz(texto) {
    respuesta.classList.remove('leyendo');
    modo('quieto', texto || 'La voz no está disponible ahora', true);
    repetir.hidden = !!texto || !vistas.responde || vistas.responde.hidden;
  }

  function sonar(url) {
    if (!url) { fallaVoz(); return; }
    const a = reproductor();
    a.src = url;
    if (respuesta.children.length) respuesta.classList.add('leyendo');
    modo('habla', 'Hablando… toca la esfera para detener');
    const p = a.play();
    if (p && p.catch) p.catch(() => fallaVoz('Toca la esfera para escucharlo'));
  }

  function hablar() {
    if (!vozFirmada) return;
    repetir.hidden = true;
    if (audioUrl) { sonar(audioUrl); return; }
    modo('piensa', 'Preparando la voz…');
    pedirVoz().then(sonar);
  }

  function escribirRespuesta(texto) {
    respuesta.textContent = '';
    texto.split(/\s+/).filter(Boolean).forEach((p) => {
      const s = document.createElement('span');
      s.textContent = `${p} `;
      respuesta.appendChild(s);
    });
  }

  function aviso(titulo, nota, enlace, sinPreguntas) {
    ayuda.hidden = true;
    ayudaTxt.hidden = true;
    avisoTitulo.textContent = titulo;
    avisoNota.textContent = nota;
    avisoEnlace.hidden = !enlace;
    if (enlace) {
      avisoEnlace.href = enlace.href;
      avisoEnlace.textContent = enlace.texto;
    }
    verVista('aviso');
    if (sinPreguntas) {
      cerrada = true;
      raiz.dataset.estado = 'neutro';
      contador.textContent = 'Sin preguntas por hoy';
      vozFirmada = (esferaMes && esferaMes.dataset.voz) || '';
      olvidarAudio();
      modo('quieto', vozFirmada ? 'Toca la esfera para escuchar cómo vas' : '');
    } else {
      modo('quieto', '');
    }
  }

  function terminarConversacion() {
    form.hidden = true;
    final.hidden = false;
  }

  function esperar(firmado, intentos) {
    return new Promise((listo) => { setTimeout(listo, 1000); })
      .then(() => fetch(`${raiz.dataset.urlTarea}?t=${encodeURIComponent(firmado)}`, {
        credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' },
      }))
      .then((r) => r.json())
      .then((d) => (d.listo || intentos <= 0 ? d : esperar(firmado, intentos - 1)))
      .catch(() => ({ ok: false }));
  }

  function mostrar(d, texto) {
    if (d.ok && d.texto) {
      turno = d.turno || turno + 1;
      ponerContador(turno);
      antes.hidden = !anterior;
      if (anterior) antes.querySelector('span').textContent = `Antes: ${anterior}`;
      anterior = texto;
      escribirRespuesta(d.texto);
      verVista('responde');
      campo.value = '';
      vozFirmada = d.voz || '';
      olvidarAudio();
      if (turno >= MAX) terminarConversacion();
      if (vozFirmada) hablar();
      else modo('quieto', turno >= MAX ? '' : 'Escribe otra pregunta');
      return;
    }
    if (d.motivo === 'conversacion') {
      terminarConversacion();
      modo('quieto', '');
      return;
    }
    if (d.motivo === 'tope') {
      aviso(`Por hoy llegaste a las ${d.tope || 30} preguntas`,
        'Mañana puedes seguir preguntando. El resumen del mes sigue disponible.', null, true);
      return;
    }
    if (d.motivo === 'politica') {
      aviso('Falta aceptar la nueva política de privacidad',
        'Explica qué se envía cuando le preguntas a la esfera. Acéptala en Inicio para empezar.',
        { href: raiz.dataset.urlPrivacidad, texto: 'Leer la política' });
      return;
    }
    if (d.motivo === 'desactivado') {
      aviso('El análisis con IA está apagado', 'Actívalo en Perfil para preguntarle a la esfera.',
        { href: raiz.dataset.urlPerfil, texto: 'Ir a Perfil' });
      return;
    }
    aviso('No pude responder ahora', 'Intenta de nuevo en un momento.');
  }

  function preguntar(texto) {
    const limpio = (texto || '').trim();
    if (!limpio || ocupado || cerrada) return;
    desbloquearAudio();
    pararVoz();
    bloquear(true);
    raiz.querySelectorAll('[data-charla-pregunta]').forEach((n) => { n.textContent = limpio; });
    repetir.hidden = true;
    verVista('piensa');
    modo('piensa', 'Pensando…');
    const datos = new FormData();
    datos.append('pregunta', limpio);
    datos.append('conversacion', conversacion);
    fetch(raiz.dataset.url, {
      method: 'POST', body: datos, credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': token() },
    }).then((r) => r.json())
      .then((d) => {
        if (d.conversacion) conversacion = d.conversacion;
        return d.tarea ? esperar(d.tarea, 60) : d;
      })
      .catch(() => ({ ok: false }))
      .then((d) => mostrar(d, limpio))
      .finally(() => bloquear(false));
  }

  function noEntendi() {
    aviso('No alcancé a entenderte', 'Intenta de nuevo, más cerca del teléfono, o escribe tu pregunta.');
    modo('quieto', 'No se descontó ninguna pregunta');
  }

  function sinPermiso() {
    aviso('No tengo permiso para usar el micrófono', 'Actívalo en los ajustes del navegador para preguntar con la voz.');
    ayuda.hidden = false;
    form.classList.add('sin-mic');
    mic.querySelector('i').className = 'fas fa-microphone-slash';
    modo('quieto', 'Puedes escribir tu pregunta');
  }

  function conPermiso() {
    form.classList.remove('sin-mic');
    mic.querySelector('i').className = 'fas fa-microphone';
  }

  function quitarMic() {
    puedeGrabar = false;
    campo.placeholder = 'Escribe tu pregunta';
    ponerBotones();
  }

  function tipoGrabacion() {
    if (!MediaRecorder.isTypeSupported) return '';
    return ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus', 'audio/webm']
      .find((t) => MediaRecorder.isTypeSupported(t)) || '';
  }

  function soltar(g) {
    if (g.cuadro) cancelAnimationFrame(g.cuadro);
    clearInterval(g.reloj);
    g.flujo.getTracks().forEach((t) => t.stop());
    if (g.ctx && g.ctx.close) g.ctx.close().catch(() => {});
    barras.forEach((b) => { b.style.transform = ''; });
  }

  function dibujar() {
    const g = grab;
    if (!g) return;
    if (g.analizador) {
      g.analizador.getFloatTimeDomainData(g.muestras);
      let suma = 0;
      for (let i = 0; i < g.muestras.length; i += 1) suma += g.muestras[i] * g.muestras[i];
      const nivel = Math.sqrt(suma / g.muestras.length);
      if (nivel > g.maximo) g.maximo = nivel;
      g.niveles.push(Math.min(1, nivel * 6));
      g.niveles.shift();
      barras.forEach((b, i) => { b.style.transform = `scaleY(${Math.max(0.12, g.niveles[i])})`; });
    }
    g.cuadro = requestAnimationFrame(dibujar);
  }

  function enviarAudio(blob) {
    raiz.querySelectorAll('[data-charla-pregunta]').forEach((n) => { n.textContent = ''; });
    verVista('piensa');
    modo('piensa', 'Pasando tu voz a texto…');
    const datos = new FormData();
    datos.append('audio', blob, 'pregunta');
    fetch(urlOir, {
      method: 'POST', body: datos, credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': token() },
    }).then((r) => r.json())
      .catch(() => ({ ok: false }))
      .then((d) => {
        bloquear(false);
        if (d.ok && d.texto) { preguntar(d.texto); return; }
        if (d.motivo === 'no_entendi') { noEntendi(); return; }
        if (d.motivo === 'sin_oido') {
          quitarMic();
          aviso('La voz no está disponible ahora', 'Puedes escribir tu pregunta.');
          return;
        }
        if (['tope', 'politica', 'desactivado'].indexOf(d.motivo) >= 0) { mostrar(d, ''); return; }
        if (d.msg) { aviso('Espera un momento', d.msg); return; }
        aviso('No pude escuchar la grabación', 'Intenta de nuevo o escribe tu pregunta.');
      });
  }

  function terminoGrabacion(g) {
    if (g.listo) return;
    g.listo = true;
    soltar(g);
    if (grab === g) grab = null;
    graba.hidden = true;
    if (g.cancelada) { bloquear(false); return; }
    form.hidden = false;
    if (g.duracion < MIN_MS || g.maximo < UMBRAL || !g.partes.length) {
      bloquear(false);
      noEntendi();
      return;
    }
    enviarAudio(new Blob(g.partes, { type: g.rec.mimeType || 'audio/webm' }));
  }

  function pararGrabacion(cancelar) {
    const g = grab;
    if (!g) return;
    g.cancelada = !!cancelar;
    g.duracion = Date.now() - g.inicio;
    if (!cancelar) desbloquearAudio();
    if (g.rec.state !== 'inactive') g.rec.stop();
    else terminoGrabacion(g);
  }

  function empezarGrabacion() {
    if (!puedeGrabar || ocupado || cerrada || grab) return;
    desbloquearAudio();
    pararVoz();
    bloquear(true);
    navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
      .then((flujo) => {
        if (raiz.hidden) { flujo.getTracks().forEach((t) => t.stop()); bloquear(false); return; }
        const tipo = tipoGrabacion();
        const rec = new MediaRecorder(flujo, tipo ? { mimeType: tipo } : undefined);
        const g = { flujo, rec, partes: [], inicio: Date.now(), maximo: 0, niveles: new Array(BARRAS).fill(0) };
        try {
          const Ctx = window.AudioContext || window.webkitAudioContext;
          g.ctx = new Ctx();
          if (g.ctx.resume) g.ctx.resume().catch(() => {});
          g.analizador = g.ctx.createAnalyser();
          g.analizador.fftSize = 1024;
          g.muestras = new Float32Array(g.analizador.fftSize);
          g.ctx.createMediaStreamSource(flujo).connect(g.analizador);
          g.analizador.getFloatTimeDomainData(g.muestras);
        } catch (e) {
          g.analizador = null;
          g.maximo = 1;
        }
        rec.addEventListener('dataavailable', (e) => { if (e.data && e.data.size) g.partes.push(e.data); });
        rec.addEventListener('stop', () => terminoGrabacion(g));
        grab = g;
        rec.start();
        conPermiso();
        let ultimo = -1;
        tiempo.textContent = '0:00';
        g.reloj = setInterval(() => {
          const s = Math.floor((Date.now() - g.inicio) / 1000);
          if (s !== ultimo) { ultimo = s; tiempo.textContent = `0:${String(Math.min(s, MAX_SEG)).padStart(2, '0')}`; }
          if (s >= MAX_SEG) pararGrabacion();
        }, 250);
        repetir.hidden = true;
        verVista('escucha');
        form.hidden = true;
        graba.hidden = false;
        modo('escucha', 'Te escucho…');
        parar.focus();
        dibujar();
      })
      .catch((e) => {
        bloquear(false);
        if (e && (e.name === 'NotAllowedError' || e.name === 'SecurityError')) sinPermiso();
        else aviso('No encontré un micrófono', 'Puedes escribir tu pregunta.');
      });
  }

  function reiniciar() {
    pararGrabacion(true);
    pararVoz();
    olvidarAudio();
    conversacion = '';
    anterior = '';
    turno = 0;
    cerrada = false;
    vozFirmada = '';
    raiz.dataset.estado = estadoMes;
    form.hidden = false;
    final.hidden = true;
    repetir.hidden = true;
    campo.value = '';
    ponerContador(1);
    graba.hidden = true;
    verVista('inicio');
    modo('quieto', puedeGrabar ? 'Toca el micrófono o escribe' : 'Escribe tu pregunta');
    bloquear(false);
  }

  function abrirCharla() {
    ultimoFoco = document.activeElement;
    if (!conversacion && !cerrada) reiniciar();
    raiz.hidden = false;
    html.classList.add('charla-abierta');
    if (!puedeGrabar && !cerrada && !form.hidden) campo.focus();
  }

  function cerrarCharla() {
    pararGrabacion(true);
    pararVoz();
    raiz.hidden = true;
    html.classList.remove('charla-abierta');
    if (!cerrada) reiniciar();
    if (ultimoFoco && ultimoFoco.focus) ultimoFoco.focus();
  }

  if (puedeGrabar) campo.placeholder = 'Escribe o toca el micrófono';
  ponerBotones();
  campo.addEventListener('input', ponerBotones);
  mic.addEventListener('click', empezarGrabacion);
  parar.addEventListener('click', () => pararGrabacion());
  ayuda.addEventListener('click', () => { ayudaTxt.hidden = false; ayuda.hidden = true; });
  abrir.addEventListener('click', abrirCharla);
  raiz.querySelector('[data-charla-cerrar]').addEventListener('click', cerrarCharla);
  raiz.querySelector('[data-charla-otra]').addEventListener('click', () => { reiniciar(); campo.focus(); });
  form.addEventListener('submit', (e) => { e.preventDefault(); preguntar(campo.value); });
  raiz.querySelectorAll('[data-idea]').forEach((b) => {
    b.addEventListener('click', () => { campo.value = b.textContent.trim(); preguntar(campo.value); });
  });
  repetir.addEventListener('click', () => { olvidarAudio(); hablar(); });
  bola.addEventListener('click', () => {
    if (raiz.dataset.modo === 'escucha') { pararGrabacion(); return; }
    if (raiz.dataset.modo === 'habla') { pararVoz(); return; }
    if (raiz.dataset.modo !== 'piensa') hablar();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !raiz.hidden) cerrarCharla();
  });
  window.addEventListener('pagehide', () => { pararGrabacion(true); pararVoz(); });
})();
