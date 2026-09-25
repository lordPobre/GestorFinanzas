(function () {
  var form = document.getElementById('formEncuesta');
  if (!form) return;
  var pasos = Array.prototype.slice.call(form.querySelectorAll('[data-paso]'));
  var contador = form.querySelector('[data-contador]');
  var progreso = form.querySelector('[data-progreso]');
  var atras = form.querySelector('[data-atras]');
  var siguiente = form.querySelector('[data-siguiente]');
  var enviar = form.querySelector('[data-enviar]');
  var omitir = form.querySelector('[data-omitir]');
  var razon = form.querySelector('[data-razon-titulo]');
  var i = 0;

  function marcado(nombre) { return !!form.querySelector('[name="' + nombre + '"]:checked'); }
  function valido(paso) { return !paso.dataset.obligatoria || marcado(paso.dataset.obligatoria); }

  function pintarChips() {
    form.querySelectorAll('.chip').forEach(function (c) {
      var input = c.querySelector('input');
      c.classList.toggle('on', !!(input && input.checked));
    });
  }

  function filasNotas() {
    var elegidas = Array.prototype.map.call(form.querySelectorAll('[name="secciones"]:checked'), function (x) { return x.value; });
    form.querySelectorAll('[data-seccion]').forEach(function (f) {
      f.hidden = elegidas.indexOf(f.dataset.seccion) === -1;
    });
  }

  function tituloRazon() {
    var r = form.querySelector('[name="recomienda"]:checked');
    razon.textContent = r && Number(r.value) >= 9 ? '¿Qué es lo que más valoras de la app?' : '¿Qué te faltó para darnos un 10?';
  }

  function mostrar() {
    var paso = pasos[i], ultimo = i === pasos.length - 1;
    pasos.forEach(function (p, k) { p.hidden = k !== i; });
    contador.textContent = 'Encuesta · ' + (i + 1) + ' de ' + pasos.length;
    progreso.style.width = ((i + 1) / pasos.length * 100) + '%';
    atras.hidden = i === 0;
    siguiente.hidden = ultimo;
    enviar.hidden = !ultimo;
    omitir.hidden = ultimo || !!paso.dataset.obligatoria;
    siguiente.disabled = !valido(paso);
    if (paso.hasAttribute('data-notas')) filasNotas();
    if (ultimo) tituloRazon();
  }

  function ir(k) {
    i = Math.max(0, Math.min(pasos.length - 1, k));
    mostrar();
    window.scrollTo(0, 0);
  }

  form.addEventListener('change', function () {
    pintarChips();
    siguiente.disabled = !valido(pasos[i]);
  });
  siguiente.addEventListener('click', function () { if (valido(pasos[i])) ir(i + 1); });
  omitir.addEventListener('click', function () { ir(i + 1); });
  atras.addEventListener('click', function () { ir(i - 1); });
  form.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA' && i < pasos.length - 1) e.preventDefault();
  });

  pintarChips();
  mostrar();
})();
