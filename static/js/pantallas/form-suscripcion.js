(function () {
  function iniciar(raiz) {
    var monto = raiz.querySelector('#id_sub_monto');
    var anual = raiz.querySelector('#subAnual');
    if (!monto || !anual) return;
    function pintar() {
      anual.textContent = '$' + Math.round(Number(monto.value || 0) * 12).toLocaleString('es-CL');
    }
    monto.addEventListener('input', pintar);
    pintar();
  }

  window.finappFormSub = iniciar;
  iniciar(document);
})();
