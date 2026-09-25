document.addEventListener('click', function (e) {
  var sw = e.target.closest('[data-swatches] > button');
  if (sw) {
    e.preventDefault();
    var grupo = sw.parentElement;
    var campo = document.querySelector(grupo.dataset.swatches);
    grupo.querySelectorAll('button').forEach(function (b) {
      b.style.borderColor = 'transparent';
    });
    sw.style.borderColor = '#f5f5f5';
    if (campo) campo.value = sw.dataset.value;
    return;
  }

  var ic = e.target.closest('[data-icons] > button');
  if (ic) {
    e.preventDefault();
    var g = ic.parentElement;
    var c = document.querySelector(g.dataset.icons);
    g.querySelectorAll('button').forEach(function (b) {
      b.style.background = 'var(--surface-2)';
      b.style.color = 'var(--text-secondary)';
    });
    ic.style.background = 'var(--amber)';
    ic.style.color = '#1a1200';
    if (c) c.value = ic.dataset.value;
  }
});
