(function () {
  var seg = document.getElementById('segTipoPersona');
  var campo = document.getElementById('campoCuotasPersona');
  if (!seg || !campo) return;
  seg.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    campo.style.display = b.dataset.value === 'CUOTAS' ? 'block' : 'none';
  });
})();
