(function () {
  'use strict';

  document.documentElement.classList.add('lp-js');

  var reducir = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var timers = [];
  var cuadro = null;

  function formatear(n) { return '$' + n.toLocaleString('es-CL'); }

  function parar() {
    timers.forEach(clearTimeout);
    timers = [];
    if (cuadro) cancelAnimationFrame(cuadro);
  }

  function animarTelefono(pantalla) {
    var fases = pantalla.querySelectorAll('[data-lp-fase]');
    var cifra = pantalla.querySelector('[data-lp-cifra]');
    var barra = pantalla.querySelector('[data-lp-barra]');
    var pagada = pantalla.querySelector('[data-lp-pagada]');
    var meta = Number(cifra.dataset.meta) || 0;

    parar();
    if (reducir) {
      fases.forEach(function (el) { el.classList.add('lp-ok'); });
      if (pagada) pagada.classList.add('lp-ok');
      return;
    }

    fases.forEach(function (el) { el.classList.remove('lp-ok'); });
    if (pagada) pagada.classList.remove('lp-ok');
    cifra.textContent = formatear(0);
    barra.style.transition = 'none';
    barra.style.width = '0%';
    void barra.offsetWidth;
    barra.style.transition = '';

    var tiempos = { 1: 250, 2: 550, 3: 1350, 4: 1650, 5: 1850, 6: 2050 };
    fases.forEach(function (el) {
      timers.push(setTimeout(function () { el.classList.add('lp-ok'); }, tiempos[el.dataset.lpFase] || 0));
    });
    timers.push(setTimeout(function () { barra.style.width = barra.dataset.ancho; }, 650));
    timers.push(setTimeout(function () {
      var inicio = performance.now();
      var duracion = 1300;
      function paso(ahora) {
        var p = Math.min(1, (ahora - inicio) / duracion);
        cifra.textContent = formatear(Math.round(meta * (1 - Math.pow(1 - p, 3))));
        if (p < 1) cuadro = requestAnimationFrame(paso);
      }
      cuadro = requestAnimationFrame(paso);
    }, 650));
    if (pagada) timers.push(setTimeout(function () { pagada.classList.add('lp-ok'); }, 3100));
  }

  function prepararPestanas() {
    var botones = document.querySelectorAll('[data-lp-tab]');
    var texto = document.querySelector('[data-lp-texto]');
    botones.forEach(function (b) {
      b.addEventListener('click', function () {
        botones.forEach(function (x) { x.setAttribute('aria-selected', x === b ? 'true' : 'false'); });
        document.querySelectorAll('[data-lp-panel]').forEach(function (p) {
          p.hidden = p.dataset.lpPanel !== b.dataset.lpTab;
        });
        if (texto) texto.textContent = b.dataset.texto;
      });
    });
  }

  function prepararRevelado() {
    var items = [];
    document.querySelectorAll('[data-lp-revelar]').forEach(function (el) { items.push(el); });
    document.querySelectorAll('[data-lp-hijos]').forEach(function (padre) {
      Array.prototype.forEach.call(padre.children, function (el, i) {
        el.style.transitionDelay = (i * 90) + 'ms';
        items.push(el);
      });
    });

    function mostrar(el) {
      el.classList.add('lp-visible');
      setTimeout(function () { el.style.transitionDelay = ''; }, 1600);
    }

    if (reducir || !('IntersectionObserver' in window)) {
      items.forEach(mostrar);
      return;
    }
    var io = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) {
        if (!e.isIntersecting) return;
        mostrar(e.target);
        io.unobserve(e.target);
      });
    }, { threshold: 0, rootMargin: '0px 10000px -8% 10000px' });
    items.forEach(function (el) { io.observe(el); });
  }

  function prepararChat() {
    var raiz = document.querySelector('[data-lp-chat]');
    if (!raiz) return;
    var panel = raiz.querySelector('[data-lp-chat-panel]');
    var fondo = raiz.querySelector('[data-lp-chat-fondo]');
    var boton = raiz.querySelector('[data-lp-chat-abrir]');
    var cuerpo = raiz.querySelector('[data-lp-chat-cuerpo]');
    var entrada = raiz.querySelector('[data-lp-chat-form]');
    var campo = entrada.querySelector('input');
    var sugerencias = raiz.querySelector('[data-lp-sugerencias]');
    var plantilla = raiz.querySelector('[data-lp-plantilla-form]');
    var token = raiz.querySelector('input[name="csrfmiddlewaretoken"]');
    var historial = [];
    var ocupado = false;

    function bajar() { cuerpo.scrollTop = cuerpo.scrollHeight; }

    function abrir(si) {
      panel.hidden = !si;
      fondo.hidden = !si;
      boton.setAttribute('aria-expanded', si ? 'true' : 'false');
      document.documentElement.classList.toggle('lp-chat-abierto', si);
      if (si) {
        bajar();
        campo.focus();
      } else {
        boton.focus();
      }
    }

    function burbuja(texto, quien) {
      var el = document.createElement('div');
      el.className = 'lp-burbuja lp-burbuja-' + quien;
      el.textContent = texto;
      cuerpo.appendChild(el);
      bajar();
      return el;
    }

    function escribiendo() {
      var el = document.createElement('div');
      el.className = 'lp-escribiendo';
      el.setAttribute('aria-label', 'Escribiendo');
      for (var i = 0; i < 3; i++) el.appendChild(document.createElement('span'));
      cuerpo.appendChild(el);
      bajar();
      return el;
    }

    function cabeceras(extra) {
      var h = { 'X-CSRFToken': token ? token.value : '', 'X-Requested-With': 'XMLHttpRequest' };
      Object.keys(extra || {}).forEach(function (k) { h[k] = extra[k]; });
      return h;
    }

    function leer(r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        d.estado = r.status;
        return d;
      });
    }

    function pedirContacto(texto, pregunta) {
      burbuja(texto, 'bot');
      var previo = cuerpo.querySelector('.lp-chat-contacto');
      if (previo) previo.remove();
      var form = plantilla.content.firstElementChild.cloneNode(true);
      form.querySelector('textarea').value = pregunta || '';
      form.addEventListener('submit', enviarContacto);
      cuerpo.appendChild(form);
      bajar();
      form.querySelector('input[type="email"]').focus();
    }

    function enviarContacto(e) {
      e.preventDefault();
      var form = e.currentTarget;
      var error = form.querySelector('.lp-chat-error');
      var enviar = form.querySelector('button[type="submit"]');
      var correo = form.querySelector('input[type="email"]').value.trim();
      function fallar(texto) {
        error.textContent = texto;
        error.hidden = false;
        enviar.disabled = false;
      }
      if (!form.checkValidity()) {
        fallar('Revisa el correo y escribe tu pregunta.');
        return;
      }
      enviar.disabled = true;
      error.hidden = true;
      fetch(form.dataset.url, { method: 'POST', credentials: 'same-origin', headers: cabeceras(), body: new FormData(form) })
        .then(leer)
        .then(function (d) {
          if (d.ok) {
            form.remove();
            burbuja('Listo. Te respondemos a ' + correo + '.', 'bot');
            return;
          }
          fallar(d.msg || 'No se pudo enviar. Intenta de nuevo.');
        })
        .catch(function () { fallar('No se pudo enviar. Intenta de nuevo.'); });
    }

    function preguntar(texto) {
      texto = (texto || '').trim().slice(0, 600);
      if (!texto || ocupado) return;
      if (sugerencias) {
        sugerencias.remove();
        sugerencias = null;
      }
      burbuja(texto, 'yo');
      historial.push({ rol: 'user', texto: texto });
      campo.value = '';
      ocupado = true;
      var cargando = escribiendo();

      function sinRespuesta(mensaje) {
        historial.pop();
        pedirContacto(mensaje, texto);
      }

      fetch(entrada.dataset.url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: cabeceras({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ mensajes: historial.slice(-12) })
      })
        .then(leer)
        .then(function (d) {
          cargando.remove();
          if (d.estado === 429) {
            sinRespuesta('Llegaste al límite de preguntas por ahora. Déjame tu correo y te respondemos.');
          } else if (d.ok && d.texto) {
            burbuja(d.texto, 'bot');
            historial.push({ rol: 'assistant', texto: d.texto });
          } else if (d.ok) {
            sinRespuesta('No tengo esa respuesta. Déjame tu correo y alguien del equipo te escribe.');
          } else {
            sinRespuesta('No pude responder ahora. Déjame tu correo y te escribimos.');
          }
        })
        .catch(function () {
          cargando.remove();
          sinRespuesta('No pude responder ahora. Déjame tu correo y te escribimos.');
        })
        .then(function () { ocupado = false; });
    }

    boton.addEventListener('click', function () { abrir(panel.hidden); });
    raiz.querySelector('[data-lp-chat-cerrar]').addEventListener('click', function () { abrir(false); });
    fondo.addEventListener('click', function () { abrir(false); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !panel.hidden) abrir(false);
    });
    entrada.addEventListener('submit', function (e) {
      e.preventDefault();
      preguntar(campo.value);
    });
    if (sugerencias) {
      sugerencias.querySelectorAll('button').forEach(function (b) {
        b.addEventListener('click', function () { preguntar(b.textContent); });
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var pantalla = document.querySelector('[data-lp-telefono]');
    if (pantalla) {
      animarTelefono(pantalla);
      pantalla.addEventListener('click', function () { animarTelefono(pantalla); });
    }
    prepararPestanas();
    prepararRevelado();
    prepararChat();
  });
})();
