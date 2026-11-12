(function () {
  var script = document.querySelector('script[data-js="editar-flotante"]');
  if (!script || !window.fetch || !window.DOMParser) return;
  var d = script.dataset;
  var nonce = script.nonce || '';
  var cargados = {};
  var modal = null;
  var ocupado = false;

  function patron(url, fija) {
    if (!url) return null;
    var texto = url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (!fija) texto = texto.replace(/\/0(\/|$)/, '/\\d+$1');
    return new RegExp('^' + texto + '$');
  }

  var rutas = [
    { patron: patron(d.mov), js: d.jsMov, iniciar: 'finappFormMov' },
    { patron: patron(d.sub), js: d.jsSub, iniciar: 'finappFormSub' },
    { patron: patron(d.subNueva, true), js: d.jsSub, iniciar: 'finappFormSub' }
  ].filter(function (r) { return r.patron; });

  function cargar(src, luego) {
    if (!src || cargados[src]) { luego(); return; }
    var s = document.createElement('script');
    s.src = src;
    if (nonce) s.nonce = nonce;
    s.onload = function () { cargados[src] = true; luego(); };
    s.onerror = function () { luego(); };
    document.body.appendChild(s);
  }

  function caja() {
    if (modal) return modal;
    modal = document.createElement('div');
    modal.className = 'modal-overlay fo2c-modal';
    modal.id = 'modalEditarFlotante';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    var box = document.createElement('div');
    box.className = 'modal-box';
    modal.appendChild(box);
    document.body.appendChild(modal);
    return modal;
  }

  function chips(raiz) {
    raiz.querySelectorAll('[data-field]').forEach(function (grupo) {
      var campo = raiz.querySelector(grupo.dataset.field);
      grupo.addEventListener('click', function (e) {
        var b = e.target.closest('button');
        if (!b) return;
        e.preventDefault();
        grupo.querySelectorAll('button').forEach(function (x) { x.classList.remove('on'); });
        b.classList.add('on');
        if (campo) {
          campo.value = b.dataset.value;
          campo.dispatchEvent(new Event('change', { bubbles: true }));
        }
      });
    });
  }

  function mostrar(hoja, ruta) {
    var box = caja().firstChild;
    box.textContent = '';
    Array.prototype.forEach.call(hoja.children, function (n) { box.appendChild(document.importNode(n, true)); });
    var titulo = box.querySelector('.modal-title');
    if (titulo) {
      titulo.id = 'editarFlotanteTitulo';
      modal.setAttribute('aria-labelledby', titulo.id);
    }
    box.querySelectorAll('a.modal-close').forEach(function (a) {
      a.setAttribute('data-close', '');
      a.setAttribute('role', 'button');
      a.setAttribute('aria-label', 'Cerrar');
    });
    var aqui = location.pathname + location.search;
    box.querySelectorAll('input[name="next"]').forEach(function (campo) { campo.value = aqui; });
    chips(box);
    if (typeof window[ruta.iniciar] === 'function') window[ruta.iniciar](box);
    if (window.finappEstilos) window.finappEstilos(box);
    if (window.finappOpen) window.finappOpen('#modalEditarFlotante');
  }

  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || a.target === '_blank' || a.hasAttribute('download')) return;
    var url = new URL(a.href, location.href);
    if (url.origin !== location.origin) return;
    var ruta = null;
    rutas.forEach(function (r) { if (!ruta && r.patron.test(url.pathname)) ruta = r; });
    if (!ruta) return;
    e.preventDefault();
    if (ocupado) return;
    ocupado = true;
    a.setAttribute('aria-busy', 'true');
    var soltar = function () { ocupado = false; a.removeAttribute('aria-busy'); };
    Promise.all([
      fetch(url.href, { credentials: 'same-origin' }).then(function (r) {
        if (!r.ok || r.redirected) throw new Error('sin hoja');
        return r.text();
      }),
      new Promise(function (listo) { cargar(ruta.js, listo); })
    ]).then(function (res) {
      var hoja = new DOMParser().parseFromString(res[0], 'text/html').querySelector('.fo2c-hoja');
      if (!hoja) throw new Error('sin hoja');
      soltar();
      mostrar(hoja, ruta);
    }).catch(function () {
      soltar();
      location.href = url.href;
    });
  });
})();
