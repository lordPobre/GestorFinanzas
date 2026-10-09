(function () {
  var esfera = document.querySelector('[data-esfera]');
  var orbe = document.querySelector('.sidebar-foot.health');
  if (!esfera || !orbe || !esfera.dataset.voz || !esfera.dataset.vozUrl || !window.fetch) return;
  var mq = window.matchMedia('(min-width: 721px)');
  var audio = null;
  var url = '';
  var estado = 'quieto';
  var titulo = orbe.getAttribute('title') || '';

  orbe.classList.add('habla');
  orbe.setAttribute('role', 'button');
  orbe.setAttribute('tabindex', '0');
  orbe.setAttribute('aria-label', 'Escuchar el resumen de esta pantalla');
  orbe.setAttribute('title', 'Toca para escuchar el resumen' + (titulo ? ' · ' + titulo : ''));

  function poner(nuevo) {
    estado = nuevo;
    orbe.classList.toggle('hablando', nuevo === 'hablando');
    orbe.classList.toggle('cargando', nuevo === 'cargando');
  }

  function reproductor() {
    if (audio) return audio;
    audio = new Audio();
    var fin = function () { if (estado === 'hablando') poner('quieto'); };
    audio.addEventListener('ended', fin);
    audio.addEventListener('pause', fin);
    audio.addEventListener('error', fin);
    return audio;
  }

  function pedir() {
    var datos = new FormData();
    datos.append('frase', esfera.dataset.voz);
    var token = document.querySelector('[name=csrfmiddlewaretoken]');
    return fetch(esfera.dataset.vozUrl, {
      method: 'POST', body: datos, credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': token ? token.value : '' },
    }).then(function (r) {
      return r.ok && (r.headers.get('Content-Type') || '').indexOf('audio') === 0 ? r.blob() : null;
    }).then(function (b) {
      if (b) url = URL.createObjectURL(b);
      return url;
    }).catch(function () { return ''; });
  }

  function sonar() {
    var a = reproductor();
    a.src = url;
    poner('hablando');
    var intento = a.play();
    if (intento && intento.catch) intento.catch(function () { poner('quieto'); });
  }

  function tocar() {
    if (!mq.matches) return;
    if (estado !== 'quieto') {
      if (audio) audio.pause();
      poner('quieto');
      return;
    }
    if (url) { sonar(); return; }
    poner('cargando');
    pedir().then(function (u) {
      if (estado !== 'cargando') return;
      if (u) sonar(); else poner('quieto');
    });
  }

  orbe.addEventListener('click', tocar);
  orbe.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); tocar(); }
  });
  window.addEventListener('pagehide', function () { if (audio) audio.pause(); });
})();
