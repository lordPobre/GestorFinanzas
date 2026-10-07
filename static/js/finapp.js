(function () {
  'use strict';

  window.__finappJsCargado = true;

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  $$('[data-quitar-si-falla]').forEach(function (img) {
    img.addEventListener('error', function () { img.remove(); });

    if (img.complete && img.naturalWidth === 0) img.remove();
  });

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-ver-pass]');
    if (!btn) return;
    e.preventDefault();

    var campo = btn.dataset.verPass
      ? document.getElementById(btn.dataset.verPass)
      : (btn.parentElement && btn.parentElement.querySelector('input'));
    if (!campo) return;

    var oculto = campo.type === 'password';
    campo.type = oculto ? 'text' : 'password';
    btn.setAttribute('aria-label', oculto ? 'Ocultar contraseña' : 'Ver contraseña');

    var icono = btn.querySelector('i');
    if (icono) icono.className = 'fas fa-eye' + (oculto ? '-slash' : '');

    var n = campo.value.length;
    campo.focus();
    try { campo.setSelectionRange(n, n); } catch (err) {}
  });

  var canHover = window.matchMedia('(hover: hover)').matches;
  if (canHover) {
    document.addEventListener('mousemove', function (e) {
      var el = e.target.closest && e.target.closest('[data-spot]');
      if (!el) return;

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

  var ultimoFoco = null;

  function open(id) {
    var m = $(id);
    if (!m) return;
    ultimoFoco = document.activeElement;
    m.classList.add('open');
    document.body.style.overflow = 'hidden';

    var primero = m.querySelector('[autofocus]') ||
                  m.querySelector('input:not([type=hidden]), select, textarea') ||
                  m.querySelector('button:not([data-close])');
    if (primero) setTimeout(function () { primero.focus(); }, 60);
  }

  function closeAll() {
    var habia = $$('.modal-overlay.open');
    habia.forEach(function (m) { m.classList.remove('open'); });
    document.body.style.overflow = '';
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

    document.addEventListener('keydown', function (e) {
      var panel = pad.closest('.modal-overlay');
      if (!panel || !panel.classList.contains('open')) return;
      if (document.activeElement && /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) return;
      if (/^[0-9]$/.test(e.key)) { if (val.length <= 8) { val = (val + e.key).replace(/^0+/, ''); paint(); } }
      else if (e.key === 'Backspace') { e.preventDefault(); val = val.slice(0, -1); paint(); }
    });

    paint();
  });

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

  $$('.toast').forEach(function (t, i) {

    t.style.cursor = 'pointer';
    t.title = 'Cerrar';
    var quitar = function () {
      t.style.transition = 'opacity .35s, transform .35s';
      t.style.opacity = '0';
      t.style.transform = 'translateX(20px)';
      setTimeout(function () { t.remove(); }, 350);
    };
    t.addEventListener('click', quitar);

    var esAviso = /error|warning|danger/.test(t.className);
    if (!esAviso) setTimeout(quitar, 4200 + i * 300);
  });

  var dlg = null;

  function pedirConfirmacion(texto, destructivo, alAceptar) {
    if (!dlg) {
      dlg = document.createElement('div');
      dlg.className = 'modal-overlay confirm-overlay';
      dlg.innerHTML =
        '<div class="confirm-box">' +
          '<span class="confirm-icono"><i class="fas fa-triangle-exclamation"></i></span>' +
          '<div class="confirm-texto"></div>' +
          '<div class="confirm-acciones">' +
            '<button type="button" class="btn btn-glass" data-cancelar>Cancelar</button>' +
            '<button type="button" class="btn btn-purple" data-aceptar></button>' +
          '</div>' +
        '</div>';
      document.body.appendChild(dlg);

      dlg.addEventListener('click', function (e) {

        if (e.target === dlg || e.target.closest('[data-cancelar]')) cerrarConfirm();
        else if (e.target.closest('[data-aceptar]')) {
          var fn = dlg._alAceptar;
          cerrarConfirm();
          if (fn) fn();
        }
      });
    }

    dlg.querySelector('.confirm-texto').textContent = texto;
    var btn = dlg.querySelector('[data-aceptar]');

    btn.textContent = destructivo ? 'Sí, eliminar' : 'Confirmar';
    btn.className = 'btn ' + (destructivo ? 'btn-red' : 'btn-purple');
    dlg.classList.toggle('destructivo', !!destructivo);
    dlg._alAceptar = alAceptar;
    dlg.classList.add('open');
    document.body.style.overflow = 'hidden';
    setTimeout(function () { btn.focus(); }, 60);
  }

  function cerrarConfirm() {
    if (!dlg) return;
    dlg.classList.remove('open');
    document.body.style.overflow = '';
    dlg._alAceptar = null;
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && dlg && dlg.classList.contains('open')) cerrarConfirm();
  });

  document.addEventListener('submit', function (e) {
    var f = e.target.closest('form[data-confirm]');
    if (f && !f.dataset.confirmado) {
      e.preventDefault();
      var texto = f.dataset.confirm;

      var destructivo = /elimin|borra|quita|cancel/i.test(texto);
      pedirConfirmacion(texto, destructivo, function () {
        f.dataset.confirmado = '1';

        if (f.requestSubmit) f.requestSubmit();
        else f.submit();
      });
      return;
    }

    var form = e.target.closest('form');
    if (!form || form.dataset.enviado) return;
    var btn = form.querySelector('button[type=submit], button:not([type])');
    if (!btn) return;
    form.dataset.enviado = '1';
    var textoOriginal = btn.innerHTML;
    btn.disabled = true;
    btn.style.opacity = '.65';
    var giro = document.createElement('i');
    giro.className = 'fas fa-circle-notch fa-spin';
    giro.style.fontSize = '11px';
    btn.textContent = '';
    btn.appendChild(giro);
    setTimeout(function () {
      if (!document.hidden) {
        form.dataset.enviado = '';
        btn.disabled = false;
        btn.style.opacity = '';
        btn.innerHTML = textoOriginal;
      }
    }, 6000);
  });

  var search = $('[data-search]');
  if (search) {

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

      if (q && total && visibles === 0) {
        if (!aviso) {
          aviso = document.createElement('div');
          aviso.className = 'glass';
          aviso.style.cssText = 'padding:24px;border-radius:20px;text-align:center;margin:16px 0';
          var avisoTitulo = document.createElement('div');
          avisoTitulo.style.cssText = "font-family:'Sora',sans-serif;font-size:14px;margin-bottom:5px";
          var avisoNota = document.createElement('div');
          avisoNota.style.cssText = 'font-size:12px;color:var(--text-muted)';
          avisoNota.textContent = 'La búsqueda solo mira lo que hay en esta pantalla.';
          aviso.appendChild(avisoTitulo);
          aviso.appendChild(avisoNota);
          aviso._titulo = avisoTitulo;
          document.querySelector('.main').prepend(aviso);
        }
        aviso._titulo.textContent = 'Nada coincide con “' + search.value + '”';
        aviso.style.display = 'block';
      } else if (aviso) {
        aviso.style.display = 'none';
      }
    });
  }

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

    marcas.forEach(function (m, k) {
      m.style.cursor = 'pointer';
      m.addEventListener('click', function () {
        carrusel.scrollTo({ left: (carrusel.scrollWidth / marcas.length) * k, behavior: 'smooth' });
      });
    });
  }

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
      e.preventDefault();
    });
  }

  $$('[data-plegable]').forEach(function (panel) {
    var lista = $('.mov-list', panel);
    var btn = $('[data-toggle-plegable]', panel);
    if (!lista || !btn) return;
    var txt = $('.mov-toggle-txt', btn);
    var cerradoTxt = txt ? txt.textContent : 'Ver todo';

    var VISIBLES = window.matchMedia('(max-width: 640px)').matches ? 4 : 5;

    function alturaCorte() {
      var filas = lista.children;
      if (filas.length <= VISIBLES) return null;
      var base = lista.getBoundingClientRect().top;

      return Math.round(filas[VISIBLES - 1].getBoundingClientRect().bottom - base);
    }

    var corte = alturaCorte();
    if (corte === null) { btn.style.display = "none"; return; }
    lista.style.maxHeight = corte + 'px';

    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(function () {
        if (panel.classList.contains('abierto')) return;
        var nuevo = alturaCorte();
        if (nuevo !== null && Math.abs(nuevo - corte) > 1) {
          corte = nuevo;
          lista.style.maxHeight = corte + 'px';
        }
      });
    }

    btn.addEventListener('click', function () {
      var abriendo = !panel.classList.contains('abierto');
      panel.classList.toggle('abierto', abriendo);
      lista.style.maxHeight = (abriendo ? lista.scrollHeight : corte) + 'px';
      if (txt) txt.textContent = abriendo ? 'Ver menos' : cerradoTxt;
      btn.setAttribute('aria-expanded', abriendo ? 'true' : 'false');

      if (!abriendo) {

        var arriba = panel.getBoundingClientRect().top;
        if (arriba < 0) window.scrollBy({ top: arriba - 12, behavior: 'smooth' });
      }
    });
  });

  var carriles = $$('.swipe');
  if (carriles.length) {

    function panelDe(carril, lado) {
      return $('.swipe-acciones.' + lado, carril) ||
             (lado === 'der' ? $('.swipe-acciones:not(.izq)', carril) : null);
    }
    function anchoDe(carril, lado) {
      var acc = panelDe(carril, lado || 'der');
      return acc ? Math.round(acc.getBoundingClientRect().width) + 8 : 144;
    }
    var UMBRAL = 40;
    var abierta = null;

    function esFlotante(c) { return c.classList.contains('swipe-mov'); }

    function cerrar(c) {
      if (!c) return;
      c.classList.remove('abierta', 'abierta-izq', 'abierta-der');
      var card = $('.swipe-card', c);
      if (card) card.style.transform = '';
      if (abierta === c) abierta = null;
    }

    function abrir(c, lado) {

      if (abierta && abierta !== c) cerrar(abierta);
      c.classList.add('abierta');
      c.classList.toggle('abierta-izq', lado === 'izq');
      c.classList.toggle('abierta-der', lado !== 'izq');
      var card = $('.swipe-card', c);

      if (card) {
        var d = anchoDe(c, lado);
        card.style.transform = 'translateX(' + (lado === 'izq' ? d : -d) + 'px)';
      }
      abierta = c;
    }

    carriles.forEach(function (carril) {
      var card = $('.swipe-card', carril);
      if (!card) return;
      var x0 = 0, y0 = 0, dx = 0, arrastrando = false, decidido = false;

      card.addEventListener('touchstart', function (e) {
        if (e.touches.length !== 1) return;
        x0 = e.touches[0].clientX;
        y0 = e.touches[0].clientY;
        dx = 0; arrastrando = true; decidido = false;
        card.style.transition = 'none';
      }, { passive: true });

      card.addEventListener('touchmove', function (e) {
        if (!arrastrando) return;
        var mx = e.touches[0].clientX - x0;
        var my = e.touches[0].clientY - y0;

        if (!decidido) {
          if (Math.abs(mx) < 8 && Math.abs(my) < 8) return;
          if (Math.abs(my) > Math.abs(mx)) { arrastrando = false; card.style.transition = ''; return; }
          decidido = true;
        }

        var hayIzq = !!panelDe(carril, 'izq');
        var hayDer = !!panelDe(carril, 'der');
        var ladoAbierto = carril.classList.contains('abierta-izq') ? 'izq'
                        : carril.classList.contains('abierta-der') ? 'der' : null;
        var base = ladoAbierto
          ? (ladoAbierto === 'izq' ? anchoDe(carril, 'izq') : -anchoDe(carril, 'der'))
          : 0;
        dx = base + mx;

        var topeDer = hayDer ? anchoDe(carril, 'der') : 0;
        var topeIzq = hayIzq ? anchoDe(carril, 'izq') : 0;
        if (dx > topeIzq) dx = topeIzq + (dx - topeIzq) * 0.25;
        else if (dx < -topeDer) dx = -topeDer + (dx + topeDer) * 0.25;
        card.style.transform = 'translateX(' + dx + 'px)';
      }, { passive: true });

      function soltar() {
        if (!arrastrando) return;
        arrastrando = false;
        card.style.transition = '';
        card.style.transform = '';
        if (!decidido) return;
        if (dx < -UMBRAL && panelDe(carril, 'der')) abrir(carril, 'der');
        else if (dx > UMBRAL && panelDe(carril, 'izq')) abrir(carril, 'izq');
        else cerrar(carril);
      }
      card.addEventListener('touchend', soltar);
      card.addEventListener('touchcancel', soltar);

      card.addEventListener('click', function (e) {
        if (carril.classList.contains('abierta')) {
          e.preventDefault();
          e.stopPropagation();
          cerrar(carril);
        }
      }, true);
    });

    document.addEventListener('touchstart', function (e) {
      if (abierta && !abierta.contains(e.target)) cerrar(abierta);
    }, { passive: true });
  }

})();
