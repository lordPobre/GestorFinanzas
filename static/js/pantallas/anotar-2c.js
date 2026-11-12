(function () {
  var form = document.getElementById('formRegistro');
  if (!form) return;

  function activo(b) {
    return b.classList.contains('on') || b.classList.contains('on-green') || b.classList.contains('on-coral');
  }

  function siguiente(seg) {
    var botones = Array.prototype.slice.call(seg.querySelectorAll('button'));
    var i = -1;
    botones.forEach(function (b, k) { if (activo(b)) i = k; });
    var otro = botones[(i + 1) % botones.length];
    if (otro) otro.click();
  }

  form.addEventListener('click', function (e) {
    var pildora = e.target.closest('.anotar-dia, .anotar-pago');
    if (!pildora || e.target.closest('input')) return;
    var seg = pildora.querySelector('.seg');
    if (!seg) return;
    var b = e.target.closest('.seg button');
    if (b && !activo(b)) return;
    e.preventDefault();
    e.stopPropagation();
    siguiente(seg);
  }, true);

  var btn = document.getElementById('btnGuardar');
  var monto = document.getElementById('montoView');
  if (!btn || !monto) return;
  var VACIO = 'Escribe un monto';
  function pintar() {
    var t = monto.textContent.trim();
    var vacio = !t || t === '$0';
    btn.classList.toggle('sin-monto', vacio);
    if (vacio && btn.textContent !== VACIO) btn.textContent = VACIO;
    if (!vacio && btn.textContent === VACIO) btn.textContent = 'Guardar ' + t;
  }
  new MutationObserver(pintar).observe(monto, { childList: true, characterData: true, subtree: true });
  new MutationObserver(pintar).observe(btn, { childList: true, characterData: true, subtree: true });
  pintar();
})();
