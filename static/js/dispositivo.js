(function () {
  var n = navigator;
  var ua = n.userAgent || '';
  var mm = function (q) { return !!(window.matchMedia && window.matchMedia(q).matches); };
  var ipad = n.platform === 'MacIntel' && n.maxTouchPoints > 1;
  var movil = /Android|iPhone|iPad|iPod|Mobile/i.test(ua) || ipad || (mm('(pointer: coarse)') && !mm('(hover: hover)'));
  if (movil) document.documentElement.classList.add('es-movil');
  window.FintoraDispositivo = { movil: movil };
})();
