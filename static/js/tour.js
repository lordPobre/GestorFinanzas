(function () {
  'use strict';

  var VERSION = 3;

  var LS_PASO = 'finapp.tour.paso';
  var LS_LISTO = 'finapp.tour.listo';
  var LS_VERSION = 'finapp.tour.version';
  var LS_MODO = 'finapp.tour.modo';
  var LS_PASOS_OCULTO = 'finapp.pasos.oculto';

  var PASOS = [
    {
      ruta: 'inicio', icono: 'fa-wallet',
      sel: '[data-tour="saldo"]',
      titulo: 'Cuánto puedes gastar',
      texto: 'Este número es lo que te queda para el resto del mes: lo que entró, menos tus gastos, las cuotas y lo que todavía tienes por pagar. Al lado están lo que debes y lo que te deben.'
    },
    {
      ruta: 'inicio', icono: 'fa-heart-pulse', desde: 2,
      sel: '[data-tour="salud"]',
      titulo: 'La salud de tu mes',
      texto: 'Un número del 1 al 100 que resume cuánto de lo que entró ya está comprometido en cuotas, suscripciones y cuentas por pagar. Baja cuando te endeudas y sube cuando pagas.'
    },
    {
      ruta: 'inicio', icono: 'fa-plus',
      sel: '[data-tour="registrar"]',
      titulo: 'Anotar un gasto o un ingreso',
      texto: 'Desde acá se anota todo, en cualquier pantalla. Se abre un panel con teclado de montos: eliges categoría, dices si ya lo pagaste y se guarda al toque.'
    },
    {
      ruta: 'importar', icono: 'fa-file-import', desde: 2,
      sel: '[data-tour="cartola"]',
      titulo: 'Subir la cartola del banco',
      texto: 'En vez de anotar movimiento por movimiento, sube el PDF que descargas del banco. Sirve la cartola de cualquier banco y el estado de cuenta de cualquier tarjeta de casa comercial. El archivo no se guarda: se lee en memoria y se descarta ahí mismo.'
    },
    {
      ruta: 'importar', icono: 'fa-list-check', desde: 2,
      sel: '[data-tour="cartola-cuotas"]',
      titulo: 'Las cuotas salen solas del estado de cuenta',
      texto: 'De un estado de cuenta de tarjeta se importa la cuota del mes, no el total de la compra: así una compra en doce cuotas no se cuenta doce veces. Cada fila queda marcada con su número —3 de 12— y antes de mostrarte nada se comprueba que todo sume el total que declara el propio documento.'
    },
    {
      ruta: 'cuotas', icono: 'fa-credit-card',
      sel: '[data-tour="cuotas"]',
      titulo: 'Tus compras en cuotas',
      texto: 'Pones el valor de la cuota y cuántas son; la app suma el total y deja una cuota en cada mes. Cada mes marcas la cuota como pagada desde su fila.'
    },
    {
      ruta: 'cuotas', icono: 'fa-hand-pointer', desde: 2, gesto: true,
      sel: '[data-tour="gesto"]',
      titulo: 'Desliza para editar o eliminar',
      texto: 'Arrastra la tarjeta con el dedo y asoman sus acciones: Editar por el canto izquierdo, Eliminar por el derecho. Son gestos opuestos a propósito, para no borrar algo cuando querías corregirlo. En el computador asoman al pasar el cursor.'
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
      ruta: 'analisis', icono: 'fa-wand-magic-sparkles', desde: 2,
      sel: '[data-tour="ia"], [data-tour="ia-alt"]',
      titulo: 'Que te lo expliquen en palabras',
      texto: 'Análisis ya te muestra en qué se te fue la plata. Este botón lo escribe en palabras: qué cambió respecto al mes pasado y qué conviene mirar. Se pide cuando tú quieras; no corre solo.'
    },
    {
      ruta: 'perfil', icono: 'fa-lock', desde: 3,
      pestana: '#segPerfil [data-panel="seguridad"]',
      sel: '[data-tour="seguridad"]',
      titulo: 'Tu seguridad, en un solo lugar',
      texto: 'En tu perfil, la pestaña Seguridad reúne todo lo que protege tu cuenta: cómo entras, en qué aparatos está abierta, la contraseña y la opción de borrar la cuenta.'
    },
    {
      ruta: 'perfil', icono: 'fa-fingerprint', desde: 3,
      pestana: '#segPerfil [data-panel="seguridad"]',
      sel: '[data-tour="face-id"]',
      titulo: 'Entrar con Face ID o huella',
      texto: 'Registra este teléfono o computador y la próxima vez entras con la cara o el dedo, sin escribir la contraseña. Puedes registrar varios aparatos y quitar cualquiera desde aquí.'
    },
    {
      ruta: 'perfil', icono: 'fa-shield-halved', desde: 3,
      pestana: '#segPerfil [data-panel="seguridad"]',
      sel: '[data-tour="dos-pasos"]',
      titulo: 'Verificación en dos pasos',
      texto: 'Además de la contraseña, al entrar te pedimos un código de una app como Google Authenticator. Si alguien consigue tu contraseña, igual no puede entrar. Al activarla recibes códigos de respaldo por si pierdes el teléfono.'
    },
    {
      ruta: 'perfil', icono: 'fa-laptop', desde: 3,
      pestana: '#segPerfil [data-panel="seguridad"]',
      sel: '[data-tour="sesiones"]',
      titulo: 'Dónde está abierta tu cuenta',
      texto: 'Muestra los aparatos que tienen tu sesión abierta. Si ves uno que no reconoces, ciérralo desde ahí.'
    },
    {
      ruta: 'perfil', icono: 'fa-key', desde: 3,
      pestana: '#segPerfil [data-panel="seguridad"]',
      sel: '[data-tour="contrasena"]',
      titulo: 'Cambiar la contraseña',
      texto: 'Necesitas la actual. Al cambiarla sigues con la sesión abierta en este aparato.'
    },
    {
      ruta: 'perfil', icono: 'fa-trash-can', desde: 3,
      pestana: '#segPerfil [data-panel="seguridad"]',
      sel: '[data-tour="eliminar-cuenta"]',
      titulo: 'Borrar tu cuenta',
      texto: 'Borra la cuenta y todo tu historial. No se puede deshacer, así que antes conviene descargar tus datos desde la pestaña Tus datos.'
    },
    {
      ruta: 'perfil', icono: 'fa-envelope-open-text', desde: 2,
      pestana: '#segPerfil [data-panel="datos"]',
      sel: '[data-tour="aviso"]',
      titulo: 'El aviso mensual por correo',
      texto: 'Una vez al mes te llega un correo con lo que queda por pagar: las cuotas, las suscripciones y las cuentas del mes. Eliges el día del envío y lo puedes apagar cuando quieras.'
    },
    {
      ruta: 'perfil', icono: 'fa-file-arrow-down',
      pestana: '#segPerfil [data-panel="datos"]',
      sel: '[data-tour="exportar"]',
      titulo: 'Tus datos son tuyos',
      texto: 'Desde tu perfil descargas todo en Excel o CSV, con una hoja por mes. Acá también se cambia el presupuesto y se vuelve a ver este tour.'
    }
  ];

  var NUEVOS = [];

  function calcularNuevos() {
    var vista = versionVista();
    NUEVOS = PASOS.filter(function (p) { return p.desde && p.desde > vista; });
  }

  var rutas = {};
  var indice = -1;
  var secuencia = PASOS;
  var modo = '';
  var invitacion = false;
  var capa = null, hueco = null, globo = null, pildora = null, objetivo = null;

  function fijarModo(m) {
    modo = m;
    secuencia = (m === 'novedades') ? NUEVOS : PASOS;
    try {
      if (m) localStorage.setItem(LS_MODO, m); else localStorage.removeItem(LS_MODO);
    } catch (e) {}
  }

  function guardar(n) { try { localStorage.setItem(LS_PASO, String(n)); } catch (e) {} }
  function leerPaso() {
    try {
      var v = localStorage.getItem(LS_PASO);
      return v === null ? -1 : Math.max(0, Math.min(secuencia.length - 1, Number(v) || 0));
    } catch (e) { return -1; }
  }
  function terminado() { try { return localStorage.getItem(LS_LISTO) === '1'; } catch (e) { return false; } }

  function versionVista() {
    try { return Number(localStorage.getItem(LS_VERSION)) || 1; } catch (e) { return 1; }
  }

  function marcarTerminado() {
    try {
      localStorage.setItem(LS_VERSION, String(VERSION));
      localStorage.removeItem(LS_PASO);
      localStorage.removeItem(LS_MODO);
      if (modo !== 'novedades') localStorage.setItem(LS_LISTO, '1');
    } catch (e) {}
    modo = '';
  }

  function reiniciar() {
    try {
      localStorage.removeItem(LS_LISTO);
      localStorage.setItem(LS_PASO, '0');
    } catch (e) {}
    fijarModo('');
  }

  function normalizar(u) {
    if (!u) return '';
    return u.replace(/[?#].*$/, '').replace(/\/+$/, '') || '/';
  }
  function rutaDe(paso) { return rutas[paso.ruta] || '/'; }
  function aqui(paso) { return normalizar(rutaDe(paso)) === normalizar(location.pathname); }

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

  function limpiarGesto() {
    document.querySelectorAll('.tour-gesto').forEach(function (el) {
      el.classList.remove('tour-gesto');
    });
  }

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
    var p = secuencia[n];
    var total = secuencia.length;
    var ultimo = n === total - 1;
    var puntos = '';
    for (var k = 0; k < total; k++) {
      puntos += '<span class="tour-punto' + (k === n ? ' on' : (k < n ? ' hecho' : '')) + '"></span>';
    }
    var eyebrow = (modo === 'novedades' ? 'Nuevo ' : 'Paso ') + (n + 1) + ' de ' + total;
    globo.innerHTML =
      '<div class="tour-cab">' +
        '<span class="tour-ficha"><i class="fas ' + p.icono + '"></i></span>' +
        '<div class="tour-cab-txt">' +
          '<div class="tour-eyebrow">' + eyebrow + '</div>' +
          '<div class="tour-titulo">' + p.titulo + '</div>' +
        '</div>' +
      '</div>' +
      '<p class="tour-texto">' + p.texto + '</p>' +
      '<div class="tour-puntos">' + puntos + '</div>' +
      '<div class="tour-pie">' +
        '<button type="button" class="tour-omitir" data-tour-accion="omitir">' +
          (modo === 'novedades' ? 'Ya está' : 'Saltar el tour') +
        '</button>' +
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
    if (n >= secuencia.length) { cerrar(true); return; }

    var paso = secuencia[n];
    if (!aqui(paso)) { guardar(n); indice = n; ocultarCapa(); verPildora(n); return; }

    if (paso.pestana) {
      var pestana = document.querySelector(paso.pestana);
      if (pestana && !pestana.classList.contains('on')) pestana.click();
    }

    var el = elementoDe(paso);
    if (!el) {
      if (saltos > secuencia.length) { cerrar(true); return; }
      mostrar(n + 1, saltos + 1);
      return;
    }

    indice = n;
    guardar(n);
    ocultarPildora();
    armarCapa();
    contenido(n);
    limpiarGesto();
    if (paso.gesto) el.classList.add('tour-gesto');
    objetivo = el;
    capa.classList.add('on');
    acercar(el, function () { colocar(); requestAnimationFrame(colocar); });
  }

  function avanzar(delta) {
    var n = indice + delta;
    if (n >= secuencia.length) { cerrar(true); return; }
    if (n < 0) n = 0;
    limpiarGesto();
    var paso = secuencia[n];
    if (!aqui(paso)) { guardar(n); location.href = rutaDe(paso); return; }
    mostrar(n);
  }

  function ocultarCapa() { if (capa) capa.classList.remove('on'); }

  function cerrar(definitivo) {
    ocultarCapa();
    limpiarGesto();
    objetivo = null;
    if (definitivo) {
      var eraNovedades = modo === 'novedades';
      marcarTerminado();
      ocultarPildora();
      avisoFinal(eraNovedades);
      marcarPasoTourHecho();
    } else {
      verPildora(indice);
    }
  }

  function avisoFinal(eraNovedades) {
    var aviso = crear('div', 'tour-fin');
    aviso.innerHTML = '<i class="fas fa-circle-check"></i><span>' +
      (eraNovedades
        ? 'Eso es todo lo nuevo. El tour completo sigue en tu perfil.'
        : 'Listo. Puedes repetir el tour desde tu perfil.') +
      '</span>';
    setTimeout(function () { aviso.classList.add('irse'); }, 4200);
    setTimeout(function () { if (aviso.parentNode) aviso.parentNode.removeChild(aviso); }, 4800);
  }

  function verPildora(n) {
    if (n < 0) return;
    if (terminado() && !invitacion && modo !== 'novedades') return;
    if (!pildora) {
      pildora = crear('div', 'tour-pildora');
      pildora.addEventListener('click', function (e) {
        if (e.target.closest('[data-tour-cerrar]')) { cerrar(true); return; }
        if (invitacion) {
          invitacion = false;
          fijarModo('novedades');
          indice = 0;
          guardar(0);
        }
        var paso = secuencia[indice];
        if (aqui(paso)) mostrar(indice); else location.href = rutaDe(paso);
      });
    }
    var txt = invitacion
      ? '<i class="fas fa-wand-magic-sparkles"></i>Ver lo nuevo · ' + NUEVOS.length
      : '<i class="fas fa-route"></i>' +
        (modo === 'novedades' ? 'Seguir con lo nuevo · ' : 'Seguir el tour · ') +
        (n + 1) + '/' + secuencia.length;
    pildora.innerHTML =
      '<span class="tour-pildora-txt">' + txt + '</span>' +
      '<button type="button" class="tour-pildora-x" data-tour-cerrar aria-label="No seguir el tour">✕</button>';
    pildora.classList.add('on');
  }

  function ocultarPildora() { if (pildora) pildora.classList.remove('on'); }

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
        invitacion = false;
        reiniciar();
        indice = 0;
        if (aqui(secuencia[0])) mostrar(0); else location.href = rutaDe(secuencia[0]);
      });
    });
    if (terminado()) marcarPasoTourHecho();
  }

  function iniciar(cfg) {
    rutas = (cfg && cfg.rutas) || {};
    calcularNuevos();
    prepararChecklist();

    var pedido = /[?&]tour=1(&|$)/.test(location.search);
    if (pedido) {
      reiniciar();
      if (window.history.replaceState) {
        var limpia = location.pathname + location.search.replace(/([?&])tour=1(&|$)/, '$1').replace(/[?&]$/, '');
        window.history.replaceState({}, '', limpia + location.hash);
      }
      mostrar(0);
      return;
    }

    var guardadoModo = '';
    try { guardadoModo = localStorage.getItem(LS_MODO) || ''; } catch (e) {}
    fijarModo(guardadoModo === 'novedades' ? 'novedades' : '');

    if (terminado()) {
      if (modo === 'novedades') {
        var k = leerPaso();
        if (k < 0) k = 0;
        indice = k;
        if (aqui(secuencia[k])) mostrar(k); else verPildora(k);
        return;
      }
      if (versionVista() >= VERSION || !NUEVOS.length) return;
      invitacion = true;
      indice = 0;
      verPildora(0);
      return;
    }

    var n = leerPaso();
    if (n < 0) return;
    indice = n;
    if (aqui(secuencia[n])) mostrar(n); else verPildora(n);
  }

  window.finappTour = { iniciar: iniciar, mostrar: mostrar, reiniciar: reiniciar };
})();
