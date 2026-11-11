(function () {
  var raiz = document.querySelector('.ac2c[data-modo]');
  if (!raiz) return;
  var bloque = document.getElementById('bloquePasskey');
  var conPasskey = !!bloque && !bloque.hidden;
  raiz.dataset.passkey = conPasskey ? 'si' : 'no';
  if (!conPasskey) raiz.dataset.modo = 'clave';

  function ir(modo) {
    raiz.dataset.modo = modo;
    if (modo === 'clave') {
      var usuario = document.querySelector('input[name=username]');
      if (usuario && !usuario.disabled) usuario.focus();
    } else {
      var boton = document.getElementById('btnPasskey');
      if (boton) boton.focus();
    }
  }

  Array.prototype.forEach.call(document.querySelectorAll('[data-modo-ir]'), function (b) {
    b.addEventListener('click', function () { ir(b.dataset.modoIr); });
  });
})();
