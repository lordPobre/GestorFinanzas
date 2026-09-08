/* Tour guiado de FinApp.
 *
 * Recorre las pantallas de la app con un foco sobre el elemento real y un
 * globo que lo explica. El recorrido cruza páginas: el paso actual se guarda
 * en el navegador (no hay migración ni campo nuevo en el perfil), así que al
 * pasar de Inicio a Cuotas el tour sigue donde iba.
 *
 * Se activa con ?tour=1 (lo hace el final del onboarding y el botón del
 * perfil) y se puede retomar con la píldora de abajo si el usuario se fue a
 * otra pantalla por su cuenta.
 *
 * Los destinos de cada paso NO están escritos acá: los pasa base.html con
 * {% url %}, para que un cambio de rutas no rompa el tour.
 */
(function () {
  'use strict';

  var LS_PASO = 'finapp.tour.paso';
  var LS_LISTO = 'finapp.tour.listo';
  var LS_PASOS_OCULTO = 'finapp.pasos.oculto';

  var PASOS = [
    {
      ruta: 'inicio', icono: 'fa-wallet',
      sel: '[data-tour="saldo"]',
      titulo: 'Cuánto puedes gastar',
      texto: 'Este número es lo que te queda para el resto del mes: lo que entró, menos tus gastos, las cuotas y lo que todavía tienes por pagar. Al lado están lo que debes y lo que te deben.'
    },
    {
      ruta: 'inicio', icono: 'fa-plus',
      sel: '[data-tour="registrar"]',
      titulo: 'Anotar un gasto o un ingreso',
      texto: 'Desde acá se anota todo, en cualquier pantalla. Se abre un panel con teclado de montos: eliges categoría, dices si ya lo pagaste y se guarda al toque.'
    },
    {
      ruta: 'cuotas', icono: 'fa-credit-card',
      sel: '[data-tour="cuotas"]',
      titulo: 'Tus compras en cuotas',
      texto: 'Pones el valor de la cuota y cuántas son; la app suma el total y deja una cuota en cada mes. Cada mes marcas la cuota como pagada desde su fila.'
    },
    {
      ruta: 'suscripciones', icono: 'fa-rotate',
      sel: '[data-tour="suscripciones"]',
      titulo: 'Suscripciones',
      texto: 'El streaming, el gimnasio, el plan del celular. Se anotan una vez y cada mes se cobran solas en tus gastos, sin que tengas que acordarte.'
    },
    {
      ruta: 'prestamos', icono: 'fa-hand-holding-dollar',
      sel: '[data-tour="prestamos"]',
      titulo: 'Lo que te deben',
      texto: 'Si prestaste plata, anótala con el nombre de la persona. Puedes registrar abonos parciales y ver cuánto falta para que te devuelvan todo.'
    },
    {
      ruta: 'metas', icono: 'fa-bullseye',
      sel: '[data-tour="metas"]',
      titulo: 'Metas de ahorro',
      texto: 'Pones cuánto quieres juntar y para cuándo. La app calcula cuánto aportar cada mes y te muestra el avance a medida que abonas.'
    },
    {
      ruta: 'estadisticas', icono: 'fa-chart-pie',
      sel: '[data-tour="graficos"]',
      titulo: 'Cómo cambian tus gastos',
      texto: 'Mes a mes y por categoría, con el presupuesto de fondo para ver en qué te pasaste. Es la pantalla para mirar una vez al mes, no todos los días.'
    },
    {
      ruta: 'perfil', icono: 'fa-file-arrow-down',
      sel: '[data-tour="exportar"]',
      titulo: 'Tus datos son tuyos',
      texto: 'Desde tu perfil descargas todo en Excel o CSV, con una hoja por mes. Acá también se cambia el presupuesto y se vuelve a ver este tour.'
    }
  ];

  var rutas = {};
  var indice = -1;
  var capa = null, hueco = null, globo = null, pildora = null, objetivo = null;

  /* ---------- estado ---------- */

  function guardar(n) { try { localStorage.setItem(LS_PASO, String(n)); } catch (e) {} }
  function leerPaso() {
    try {
      var v = localStorage.getItem(LS_PASO);
      return v === null ? -1 : Math.max(0, Math.min(PASOS.length - 1, Number(v) || 0));
    } catch (e) { return -1; }
  }
  function terminado() { try { return localStorage.getItem(LS_LISTO) === '1'; } catch (e) { return false; } }
  function marcarTerminado() {
    try { localStorage.setItem(LS_LISTO, '1'); localStorage.removeItem(LS_PASO); } catch (e) {}
  }
  function reiniciar() {
    try { localStorage.removeItem(LS_LISTO); localStorage.setItem(LS_PASO, '0'); } catch (e) {}
  }

  /* ---------- utilidades ---------- */

  function normalizar(u) {
    if (!u) return '';
    return u.replace(/[?#].*$/, '').replace(/\/+$/, '') || '/';
  }
  function rutaDe(paso) { return rutas[paso.ruta] || '/'; }
  function aqui(paso) { return normalizar(rutaDe(paso)) === normalizar(location.pathname); }

  /* El primer elemento del selector que de verdad se ve: en escritorio el
     botón de registrar vive en el topbar y en el teléfono en el botón
     flotante, y los dos llevan el mismo data-tour. */
  function elementoDe(paso) {
    var lista = document.querySelectorAll(paso.sel);
    for (var k = 0; k < lista.length; k++) {
      var el = lista[k];
      var r = el.getBoundingClientRect();
      if (el.offsetParent !== null && r.width > 4 && r.height > 4) return el;
    }
    return null;
  }

  function crear(tag, clase, padre) {
    var el = document.createElement(tag);
    if (clase) el.className = clase;
    (padre || document.body).appendChild(el);
    return el;
  }

  /* ---------- pintado ---------- */

  function armarCapa() {
    if (capa) return;
    capa = crear('div', 'tour-capa');
    hueco = crear('div', 'tour-hueco', capa);
    globo = crear('div', 'tour-globo', capa);
    globo.setAttribute('role', 'dialog');
    globo.setAttribute('aria-live', 'polite');

    globo.addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) return;
      if (b.dataset.tourAccion === 'siguiente') avanzar(1);
      if (b.dataset.tourAccion === 'atras') avanzar(-1);
      if (b.dataset.tourAccion === 'omitir') cerrar(true);
    });
    capa.addEventListener('click', function (e) {
      if (e.target === capa) cerrar(false);
    });
    window.addEventListener('resize', colocar);
    window.addEventListener('scroll', colocar, true);
    document.addEventListener('keydown', teclas);
  }

  function teclas(e) {
    if (!capa || !capa.classList.contains('on')) return;
    if (e.key === 'Escape') { e.preventDefault(); cerrar(false); }
    if (e.key === 'ArrowRight' || e.key === 'Enter') { e.preventDefault(); avanzar(1); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); avanzar(-1); }
  }

  function contenido(n) {
    var p = PASOS[n];
    var ultimo = n === PASOS.length - 1;
    var puntos = '';
    for (var k = 0; k < PASOS.length; k++) {
      puntos += '<span class="tour-punto' + (k === n ? ' on' : (k < n ? ' hecho' : '')) + '"></span>';
    }
    globo.innerHTML =
      '<div class="tour-cab">' +
        '<span class="tour-ficha"><i class="fas ' + p.icono + '"></i></span>' +
        '<div class="tour-cab-txt">' +
          '<div class="tour-eyebrow">Paso ' + (n + 1) + ' de ' + PASOS.length + '</div>' +
          '<div class="tour-titulo">' + p.titulo + '</div>' +
        '</div>' +
      '</div>' +
      '<p class="tour-texto">' + p.texto + '</p>' +
      '<div class="tour-puntos">' + puntos + '</div>' +
      '<div class="tour-pie">' +
        '<button type="button" class="tour-omitir" data-tour-accion="omitir">Saltar el tour</button>' +
        '<div class="tour-botones">' +
          (n > 0 ? '<button type="button" class="btn btn-glass btn-sm" data-tour-accion="atras">Atrás</button>' : '') +
          '<button type="button" class="btn btn-purple btn-sm" data-tour-accion="siguiente">' +
            (ultimo ? 'Terminar' : 'Siguiente') +
          '</button>' +
        '</div>' +
      '</div>';
  }

  function colocar() {
    if (!objetivo || !capa || !capa.classList.contains('on')) return;
    var r = objetivo.getBoundingClientRect();
    var pad = 8;

    hueco.style.top = (r.top - pad) + 'px';
    hueco.style.left = (r.left - pad) + 'px';
    hueco.style.width = (r.width + pad * 2) + 'px';
    hueco.style.height = (r.height + pad * 2) + 'px';

    var gr = globo.getBoundingClientRect();
    var margen = 14;
    var abajo = r.bottom + margen + gr.height <= window.innerHeight - 10;
    var top = abajo ? r.bottom + margen : r.top - margen - gr.height;
    if (top < 10) top = Math.min(window.innerHeight - gr.height - 10, r.bottom + margen);
    if (top < 10) top = 10;

    var left = r.left + r.width / 2 - gr.width / 2;
    left = Math.max(margen, Math.min(left, window.innerWidth - gr.width - margen));

    globo.style.top = Math.round(top) + 'px';
    globo.style.left = Math.round(left) + 'px';
  }

  /* El elemento tiene que estar a la vista antes de medir: si queda bajo el
     pliegue, el globo se coloca sobre un hueco que nadie ve. */
  function acercar(el, luego) {
    var r = el.getBoundingClientRect();
    var fuera = r.top < 90 || r.bottom > window.innerHeight - 150;
    if (!fuera) { luego(); return; }
    var destino = window.scrollY + r.top - Math.max(100, window.innerHeight * 0.28);
    window.scrollTo({ top: Math.max(0, destino), behavior: 'smooth' });
    setTimeout(luego, 340);
  }

  function mostrar(n, saltos) {
    saltos = saltos || 0;
    if (n < 0) n = 0;
    if (n >= PASOS.length) { cerrar(true); return; }

    var paso = PASOS[n];
    if (!aqui(paso)) { guardar(n); indice = n; ocultarCapa(); verPildora(n); return; }

    var el = elementoDe(paso);
    if (!el) {
      /* La sección está vacía y su botón no existe (por ejemplo el estado
         vacío que no trae la acción anclada): se pasa al siguiente. */
      if (saltos > PASOS.length) { cerrar(true); return; }
      mostrar(n + 1, saltos + 1);
      return;
    }

    indice = n;
    guardar(n);
    ocultarPildora();
    armarCapa();
    contenido(n);
    objetivo = el;
    capa.classList.add('on');
    acercar(el, function () { colocar(); requestAnimationFrame(colocar); });
  }

  function avanzar(delta) {
    var n = indice + delta;
    if (n >= PASOS.length) { cerrar(true); return; }
    if (n < 0) n = 0;
    var paso = PASOS[n];
    if (!aqui(paso)) { guardar(n); location.href = rutaDe(paso); return; }
    mostrar(n);
  }

  function ocultarCapa() { if (capa) capa.classList.remove('on'); }

  function cerrar(definitivo) {
    ocultarCapa();
    objetivo = null;
    if (definitivo) {
      marcarTerminado();
      ocultarPildora();
      avisoFinal();
      marcarPasoTourHecho();
    } else {
      /* Salir con Escape o tocando el fondo no cancela el tour: queda la
         píldora para retomarlo donde iba. */
      verPildora(indice);
    }
  }

  function avisoFinal() {
    var aviso = crear('div', 'tour-fin');
    aviso.innerHTML = '<i class="fas fa-circle-check"></i><span>Listo. Puedes repetir el tour desde tu perfil.</span>';
    setTimeout(function () { aviso.classList.add('irse'); }, 4200);
    setTimeout(function () { if (aviso.parentNode) aviso.parentNode.removeChild(aviso); }, 4800);
  }

  /* ---------- píldora para retomar ---------- */

  function verPildora(n) {
    if (terminado() || n < 0) return;
    if (!pildora) {
      pildora = crear('div', 'tour-pildora');
      pildora.addEventListener('click', function (e) {
        if (e.target.closest('[data-tour-cerrar]')) { cerrar(true); return; }
        var paso = PASOS[indice];
        if (aqui(paso)) mostrar(indice); else location.href = rutaDe(paso);
      });
    }
    pildora.innerHTML =
      '<span class="tour-pildora-txt"><i class="fas fa-route"></i>' +
      'Seguir el tour · ' + (n + 1) + '/' + PASOS.length + '</span>' +
      '<button type="button" class="tour-pildora-x" data-tour-cerrar aria-label="No seguir el tour">✕</button>';
    pildora.classList.add('on');
  }

  function ocultarPildora() { if (pildora) pildora.classList.remove('on'); }

  /* ---------- checklist de primeros pasos ---------- */

  function marcarPasoTourHecho() {
    document.querySelectorAll('[data-paso-tour]').forEach(function (el) {
      el.classList.add('hecho');
    });
  }

  function prepararChecklist() {
    document.querySelectorAll('[data-pasos-ocultar]').forEach(function (b) {
      b.addEventListener('click', function () {
        try { localStorage.setItem(LS_PASOS_OCULTO, '1'); } catch (e) {}
        document.documentElement.classList.add('pasos-ocultos');
      });
    });
    document.querySelectorAll('[data-tour-iniciar]').forEach(function (b) {
      b.addEventListener('click', function (e) {
        e.preventDefault();
        reiniciar();
        indice = 0;
        if (aqui(PASOS[0])) mostrar(0); else location.href = rutaDe(PASOS[0]);
      });
    });
    if (terminado()) marcarPasoTourHecho();
  }

  /* ---------- arranque ---------- */

  function iniciar(cfg) {
    rutas = (cfg && cfg.rutas) || {};
    prepararChecklist();

    var pedido = /[?&]tour=1(&|$)/.test(location.search);
    if (pedido) {
      reiniciar();
      /* Se limpia el ?tour=1 para que un F5 no reinicie el recorrido. */
      if (window.history.replaceState) {
        var limpia = location.pathname + location.search.replace(/([?&])tour=1(&|$)/, '$1').replace(/[?&]$/, '');
        window.history.replaceState({}, '', limpia + location.hash);
      }
      mostrar(0);
      return;
    }

    if (terminado()) return;
    var n = leerPaso();
    if (n < 0) return;
    indice = n;
    if (aqui(PASOS[n])) mostrar(n); else verPildora(n);
  }

  window.finappTour = { iniciar: iniciar, mostrar: mostrar, reiniciar: reiniciar };
})();
