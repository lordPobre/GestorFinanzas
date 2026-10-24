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

  function bloquear(si) {
    ocupado = si;
    campo.disabled = si || cerrada;
    enviar.disabled = si || cerrada;
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

  function reiniciar() {
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
    verVista('inicio');
    modo('quieto', 'Escribe tu pregunta');
    bloquear(false);
  }

  function abrirCharla() {
    ultimoFoco = document.activeElement;
    if (!conversacion && !cerrada) reiniciar();
    raiz.hidden = false;
    html.classList.add('charla-abierta');
    if (!cerrada && !form.hidden) campo.focus();
  }

  function cerrarCharla() {
    pararVoz();
    raiz.hidden = true;
    html.classList.remove('charla-abierta');
    if (!cerrada) reiniciar();
    if (ultimoFoco && ultimoFoco.focus) ultimoFoco.focus();
  }

  abrir.addEventListener('click', abrirCharla);
  raiz.querySelector('[data-charla-cerrar]').addEventListener('click', cerrarCharla);
  raiz.querySelector('[data-charla-otra]').addEventListener('click', () => { reiniciar(); campo.focus(); });
  form.addEventListener('submit', (e) => { e.preventDefault(); preguntar(campo.value); });
  raiz.querySelectorAll('[data-idea]').forEach((b) => {
    b.addEventListener('click', () => { campo.value = b.textContent.trim(); preguntar(campo.value); });
  });
  repetir.addEventListener('click', () => { olvidarAudio(); hablar(); });
  bola.addEventListener('click', () => {
    if (raiz.dataset.modo === 'habla') { pararVoz(); return; }
    if (raiz.dataset.modo !== 'piensa') hablar();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !raiz.hidden) cerrarCharla();
  });
  window.addEventListener('pagehide', pararVoz);
})();
