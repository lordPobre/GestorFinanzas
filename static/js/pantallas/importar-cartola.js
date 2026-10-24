(function () {
  var input = document.getElementById('inputCartola');
  var zona = document.getElementById('zona');
  var titulo = document.getElementById('zonaTitulo');
  var nota = document.getElementById('zonaNota');
  var btn = document.getElementById('btnLeer');
  if (!input) return;

  function kb(n) { return (n / 1024 / 1024).toFixed(1) + ' MB'; }

  function mostrar(archivo) {
    if (!archivo) return;
    zona.classList.add('con-archivo');
    titulo.textContent = archivo.name;
    nota.textContent = kb(archivo.size) + ' · toca para cambiarlo';
    btn.disabled = false;
  }

  input.addEventListener('change', function () { mostrar(input.files[0]); });

  ['dragenter', 'dragover'].forEach(function (ev) {
    zona.addEventListener(ev, function (e) {
      e.preventDefault();
      zona.classList.add('encima');
    });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    zona.addEventListener(ev, function (e) {
      e.preventDefault();
      zona.classList.remove('encima');
    });
  });
  zona.addEventListener('drop', function (e) {
    var f = e.dataTransfer && e.dataTransfer.files[0];
    if (!f) return;
    input.files = e.dataTransfer.files;
    mostrar(f);
  });

  var form = document.getElementById('formCartola');
  var urlTarea = form.dataset.urlTarea;
  var notaInicial = nota.textContent;

  function volver(texto) {
    btn.disabled = false;
    btn.textContent = 'Leer cartola';
    zona.classList.remove('leyendo');
    nota.textContent = texto || notaInicial;
  }

  function esperar(tarea, intentos) {
    return new Promise(function (listo) { setTimeout(listo, 1000); })
      .then(function () {
        return fetch(urlTarea + '?t=' + encodeURIComponent(tarea), {
          credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
      })
      .then(function (r) { return r.json(); })
      .then(function (d) { return d.listo || intentos <= 0 ? d : esperar(tarea, intentos - 1); });
  }

  form.addEventListener('submit', function (e) {
    btn.disabled = true;
    if (!window.fetch || !window.FormData || !urlTarea) {
      btn.textContent = 'Leyendo…';
      return;
    }
    e.preventDefault();
    var datos = new FormData(form);
    btn.textContent = 'Leyendo tu cartola…';
    zona.classList.add('leyendo');
    nota.textContent = 'Si es larga puede tardar un poco. No cierres esta pantalla.';
    fetch(window.location.pathname, {
      method: 'POST', body: datos, credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    }).then(function (r) {
      if (r.redirected) { window.location.href = r.url; return null; }
      return r.json();
    }).then(function (d) {
      if (!d) return null;
      if (!d.ok || !d.tarea) { volver(d.msg || 'No se pudo leer la cartola.'); return null; }
      return esperar(d.tarea, 120).then(function (f) {
        if (f && f.url) { window.location.href = f.url; return; }
        volver('Está tardando más de lo normal. Intenta de nuevo en un momento.');
      });
    }).catch(function () {
      volver('No se pudo enviar el archivo. Revisa tu conexión e intenta de nuevo.');
    });
  });

  var copiar = document.getElementById('btnCopiarDiag');
  if (copiar) {
    copiar.addEventListener('click', function () {
      var caja = document.getElementById('diagTexto');
      var aviso = document.getElementById('diagAviso');
      caja.select();
      var listo = false;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(caja.value);
        listo = true;
      } else {
        try { listo = document.execCommand('copy'); } catch (e) { listo = false; }
      }
      aviso.textContent = listo ? 'Copiado.' : 'Selecciónalo y cópialo a mano.';
    });
  }
})();
