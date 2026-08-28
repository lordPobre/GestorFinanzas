/* ============================================================
   FinApp · Interacciones
   Sin dependencias. Se carga al final del <body>.
   ============================================================ */
(function () {
  'use strict';

  /* Le avisa al respaldo inline de base.html que ya puede retirarse.
     ANTES esta bandera no se ponía nunca, así que los dos manejadores de
     clic corrían a la vez: cada botón abría su modal dos veces y el
     data-confirm podía preguntar dos veces. */
  window.__finappJsCargado = true;

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  /* ============================================================
     1. Luz que sigue el cursor sobre [data-spot]
     ============================================================ */
  var canHover = window.matchMedia('(hover: hover)').matches;
  if (canHover) {
    document.addEventListener('mousemove', function (e) {
      var el = e.target.closest && e.target.closest('[data-spot]');
      if (!el) return;

      /* ANTES se escribía backgroundImage inline, lo que BORRABA los
         degradados que algunas tarjetas declaran en su style (la tarjeta
         del titular en Análisis, por ejemplo). Mover el mouse encima las
         dejaba planas. Ahora se usa una variable CSS y el degradado de la
         luz vive en un ::after, sin tocar el fondo de la tarjeta. */
      var r = el.getBoundingClientRect();
      el.style.setProperty('--mx', (e.clientX - r.left) + 'px');
      el.style.setProperty('--my', (e.clientY - r.top) + 'px');
      el.style.setProperty('--spot-opacity', '1');
    });
    document.addEventListener('mouseleave', function (e) {
      var el = e.target.closest && e.target.closest('[data-spot]');
      if (el) el.style.setProperty('--spot-opacity', '0');
    }, true);
  }

  /* ============================================================
     2. Modales y paneles
     ============================================================ */
  var ultimoFoco = null;

  function open(id) {
    var m = $(id);
    if (!m) return;
    ultimoFoco = document.activeElement;
    m.classList.add('open');
    document.body.style.overflow = 'hidden';

    /* El foco entra al panel. ANTES quedaba detrás, en el botón que lo
       abrió: con teclado se seguía navegando la página de abajo, y un
       lector de pantalla no anunciaba nada. */
    var primero = m.querySelector('[autofocus]') ||
                  m.querySelector('input:not([type=hidden]), select, textarea') ||
                  m.querySelector('button:not([data-close])');
    if (primero) setTimeout(function () { primero.focus(); }, 60);
  }

  function closeAll() {
    var habia = $$('.modal-overlay.open');
    habia.forEach(function (m) { m.classList.remove('open'); });
    document.body.style.overflow = '';
    // Devolver el foco a donde estaba: si no, se pierde al principio de la página.
    if (habia.length && ultimoFoco && ultimoFoco.focus) ultimoFoco.focus();
    ultimoFoco = null;
  }

  window.finappOpen = open;
  window.finappClose = closeAll;

  document.addEventListener('click', function (e) {
    var opener = e.target.closest('[data-open]');
    if (opener) { e.preventDefault(); open(opener.getAttribute('data-open')); return; }
    if (e.target.closest('[data-close]')) { e.preventDefault(); closeAll(); return; }
    if (e.target.classList.contains('modal-overlay')) closeAll();
  });

  /* Tab circula dentro del panel abierto y no se escapa a la página */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeAll(); return; }
    if (e.key !== 'Tab') return;
    var abierto = $('.modal-overlay.open');
    if (!abierto) return;
    var foco = $$('a[href], button:not([disabled]), input:not([type=hidden]), select, textarea', abierto)
      .filter(function (el) { return el.offsetParent !== null; });
    if (!foco.length) return;
    var primero = foco[0], ultimo = foco[foco.length - 1];
    if (e.shiftKey && document.activeElement === primero) { e.preventDefault(); ultimo.focus(); }
    else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primero.focus(); }
  });

  /* ============================================================
     3. Teclado numérico
     ============================================================ */
  $$('[data-keypad]').forEach(function (pad) {
    var input = $(pad.dataset.target);
    var view = $(pad.dataset.display);
    var val = (input && input.value) || '';
    var fmt = function (n) { return n ? '$' + Number(n).toLocaleString('es-CL') : '$0'; };
    var paint = function () {
      if (input) input.value = val;
      if (view) view.textContent = fmt(val);
      pad.dispatchEvent(new CustomEvent('keypad:change', { bubbles: true, detail: { value: Number(val || 0) } }));
    };
    pad.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      e.preventDefault();
      var k = b.dataset.key;
      if (k === 'del') val = val.slice(0, -1);
      else if (val.length <= 8) val = (val + k).replace(/^0+/, '');
      paint();
    });

    /* Se puede escribir con el teclado físico, no solo con los botones.
       En escritorio nadie espera tener que hacer clic en un teclado en
       pantalla para escribir un número. */
    document.addEventListener('keydown', function (e) {
      var panel = pad.closest('.modal-overlay');
      if (!panel || !panel.classList.contains('open')) return;
      if (document.activeElement && /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) return;
      if (/^[0-9]$/.test(e.key)) { if (val.length <= 8) { val = (val + e.key).replace(/^0+/, ''); paint(); } }
      else if (e.key === 'Backspace') { e.preventDefault(); val = val.slice(0, -1); paint(); }
    });

    paint();
  });

  /* ============================================================
     4. Vista previa del impacto
     ============================================================ */
  document.addEventListener('keypad:change', function (e) {
    $$('[data-preview]').forEach(function (el) {
      var base = Number(el.dataset.base || 0);
      var sign = Number(el.dataset.sign || -1);
      var dias = Number(el.dataset.dias || 1);
      var v = base + sign * e.detail.value;
      el.textContent = '$' + Math.round(v).toLocaleString('es-CL');
      el.style.color = v < 0 ? 'var(--coral)' : '#f5f5f5';
      var perDia = el.parentElement.querySelector('[data-preview-dia]');
      if (perDia) perDia.textContent = '$' + Math.round(Math.max(0, v) / dias).toLocaleString('es-CL');
    });
  });

  /* ============================================================
     5. Segmentados y chips
     ============================================================ */
  $$('[data-field]').forEach(function (group) {
    var input = $(group.dataset.field);
    group.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      e.preventDefault();
      $$('button', group).forEach(function (x) { x.classList.remove('on'); });
      b.classList.add('on');
      if (input) { input.value = b.dataset.value; input.dispatchEvent(new Event('change', { bubbles: true })); }
    });
  });

  /* ============================================================
     6. Barras animan al entrar en pantalla
     ============================================================ */
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target;
        if (el.classList.contains('progress-fill')) {
          var w = el.dataset.width || el.style.width;
          el.style.width = '0%';
          requestAnimationFrame(function () { el.style.width = w; });
        }
        io.unobserve(el);
      });
    }, { threshold: .2 });
    $$('.progress-fill').forEach(function (el) { el.dataset.width = el.style.width; io.observe(el); });
  }

  /* ============================================================
     7. Toasts
     ============================================================ */
  $$('.toast').forEach(function (t, i) {
    /* Se puede cerrar a mano. Un aviso de error que se va solo en 3,8 s
       no alcanza a leerse, y no había forma de retenerlo. */
    t.style.cursor = 'pointer';
    t.title = 'Cerrar';
    var quitar = function () {
      t.style.transition = 'opacity .35s, transform .35s';
      t.style.opacity = '0';
      t.style.transform = 'translateX(20px)';
      setTimeout(function () { t.remove(); }, 350);
    };
    t.addEventListener('click', quitar);

    /* Los avisos de error y advertencia se quedan hasta que los cierres:
       suelen decir qué corregir, y desaparecían antes de terminar de leer. */
    var esAviso = /error|warning|danger/.test(t.className);
    if (!esAviso) setTimeout(quitar, 4200 + i * 300);
  });

  /* ============================================================
     8. Confirmación antes de borrar
     ============================================================ */
  document.addEventListener('submit', function (e) {
    var f = e.target.closest('form[data-confirm]');
    if (f && !window.confirm(f.dataset.confirm)) { e.preventDefault(); return; }

    /* Doble envío: el botón se bloquea al enviar.
       ANTES un doble clic en "Pagar" mandaba dos POST. Con las cuotas eso
       ya no duplica el pago (la restricción única lo impide), pero sí
       generaba un segundo mensaje de error confuso. En los formularios de
       registro sí creaba dos movimientos. */
    var form = e.target.closest('form');
    if (!form || form.dataset.enviado) return;
    var btn = form.querySelector('button[type=submit], button:not([type])');
    if (!btn) return;
    form.dataset.enviado = '1';
    var textoOriginal = btn.innerHTML;
    btn.disabled = true;
    btn.style.opacity = '.65';
    btn.innerHTML = '<i class="fas fa-circle-notch fa-spin" style="font-size:11px"></i>';
    // Si la navegación no ocurre (validación del navegador), se libera.
    setTimeout(function () {
      if (!document.hidden) {
        form.dataset.enviado = '';
        btn.disabled = false;
        btn.style.opacity = '';
        btn.innerHTML = textoOriginal;
      }
    }, 6000);
  });

  /* ============================================================
     9. Buscador
     ============================================================ */
  var search = $('[data-search]');
  if (search) {
    /* El atajo estaba anunciado en la interfaz (la tecla ⌘K junto al campo)
       pero no existía. Prometer un atajo que no funciona es peor que no
       tenerlo. */
    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        search.focus();
        search.select();
      }
      if (e.key === 'Escape' && document.activeElement === search) {
        search.value = '';
        search.dispatchEvent(new Event('input'));
        search.blur();
      }
    });

    var aviso = null;
    search.addEventListener('input', function () {
      var q = search.value.toLowerCase().trim();
      var visibles = 0, total = 0;

      $$('[data-searchable]').forEach(function (row) {
        total++;
        var coincide = !q || row.textContent.toLowerCase().indexOf(q) > -1;
        row.style.display = coincide ? '' : 'none';
        if (coincide) visibles++;
      });

      /* ANTES, al no haber coincidencias, todo desaparecía sin explicación:
         la página quedaba vacía y parecía roto. */
      if (q && total && visibles === 0) {
        if (!aviso) {
          aviso = document.createElement('div');
          aviso.className = 'glass';
          aviso.style.cssText = 'padding:24px;border-radius:20px;text-align:center;margin:16px 0';
          document.querySelector('.main').prepend(aviso);
        }
        aviso.innerHTML =
          '<div style="font-family:\'Sora\',sans-serif;font-size:14px;margin-bottom:5px">' +
          'Nada coincide con “' + search.value.replace(/</g, '&lt;') + '”</div>' +
          '<div style="font-size:12px;color:var(--text-muted)">' +
          'La búsqueda solo mira lo que hay en esta pantalla.</div>';
        aviso.style.display = 'block';
      } else if (aviso) {
        aviso.style.display = 'none';
      }
    });
  }

  /* ============================================================
     10. Puntos del carrusel de saldo
     ============================================================
     El carrusel se desliza con el dedo; los puntos dicen en cuál vas. Sin
     ellos no hay señal de que haya más tarjetas a la derecha. */
  var carrusel = $('[data-carrusel]');
  var dots = $('[data-dots]');
  if (carrusel && dots) {
    var marcas = $$('span', dots);
    var pintar = function () {
      var ancho = carrusel.scrollWidth / marcas.length;
      var i = Math.round(carrusel.scrollLeft / ancho);
      marcas.forEach(function (m, k) { m.classList.toggle('on', k === Math.min(i, marcas.length - 1)); });
    };
    carrusel.addEventListener('scroll', function () {
      window.clearTimeout(carrusel._t);
      carrusel._t = window.setTimeout(pintar, 60);
    }, { passive: true });

    /* Los puntos también sirven para navegar: en la plantilla son solo
       indicadores, pero un punto que no responde al toque se siente roto. */
    marcas.forEach(function (m, k) {
      m.style.cursor = 'pointer';
      m.addEventListener('click', function () {
        carrusel.scrollTo({ left: (carrusel.scrollWidth / marcas.length) * k, behavior: 'smooth' });
      });
    });
  }

  /* ============================================================
     11. Botón flotante: gasto con un toque, ingreso manteniéndolo
     ============================================================
     En móvil los botones del topbar están ocultos, así que no quedaba
     NINGUNA forma de registrar un ingreso desde el teléfono. El botón
     ahora abre un par de opciones si lo mantienes presionado o si tocas
     su flecha. */
  var fab = $('.fab');
  if (fab && !fab.dataset.mejorado) {
    fab.dataset.mejorado = '1';
    var timer = null;

    function abrirComo(tipo) {
      var panel = $('#modalGasto');
      if (!panel) return;
      var preset = document.querySelector('[data-preset-tipo="' + tipo + '"]');
      if (preset && preset !== fab) preset.click();
      else { fab.dataset.presetTipo = tipo; open('#modalGasto'); }
    }

    fab.addEventListener('touchstart', function () {
      timer = setTimeout(function () {
        timer = null;
        if (navigator.vibrate) navigator.vibrate(12);
        abrirComo('INGRESO');
      }, 480);
    }, { passive: true });

    fab.addEventListener('touchend', function (e) {
      if (timer) { clearTimeout(timer); timer = null; return; }
      // Ya se abrió como ingreso por la pulsación larga
      e.preventDefault();
    });
  }
})();
