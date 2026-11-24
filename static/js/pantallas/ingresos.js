(function () {
  document.querySelectorAll('.ig2c-anillo[data-pct]').forEach(function (anillo) {
    var pct = Math.max(0, Math.min(100, Number(anillo.dataset.pct) || 0));
    anillo.style.setProperty('--pct', pct + '%');
  });
})();

(function () {
  function plata(n) {
    return '$' + Math.round(Math.abs(n)).toLocaleString('es-CL');
  }

  var form = document.querySelector('[data-ajustar]');
  if (!form) return;
  var mes = form.dataset.mes || '';
  var sueldo = Number(form.dataset.sueldo || 0) || 0;
  var base = Number(form.dataset.base || 0) || 0;
  var extra = form.querySelector('[data-extra]');
  var total = form.querySelector('[data-extra-total]');
  var nuevo = form.querySelector('[data-nuevo]');
  var dif = form.querySelector('[data-dif]');

  document.querySelectorAll('[data-modo]').forEach(function (boton) {
    boton.addEventListener('click', function () {
      var radio = form.querySelector('input[name="modo"][value="' + boton.dataset.modo + '"]');
      if (radio) radio.checked = true;
    });
  });

  if (extra && total) {
    extra.addEventListener('input', function () {
      total.textContent = 'Recibes ' + plata(sueldo + (Number(extra.value) || 0)) + ' en ' + mes;
    });
  }

  function pintarDif() {
    if (!nuevo || !dif) return;
    var valor = Number(nuevo.value) || 0;
    var resta = valor - base;
    if (!valor || !resta) { dif.hidden = true; return; }
    dif.hidden = false;
    dif.classList.toggle('menos', resta < 0);
    dif.textContent = (resta > 0 ? '+' : '−') + plata(resta) + (resta > 0 ? ' sobre' : ' bajo') + ' tu sueldo de ' + plata(base);
  }
  if (nuevo) nuevo.addEventListener('input', pintarDif);
  pintarDif();
})();

(function () {
  var form = document.querySelector('[data-dia-pago]');
  if (!form) return;
  var otro = form.querySelector('[data-dia-otro]');
  var oculto = form.querySelector('#id_ig_dia');
  var chips = form.querySelectorAll('.chip[data-value]');
  if (!otro) return;
  otro.addEventListener('input', function () {
    if (!otro.value) return;
    chips.forEach(function (c) { c.classList.remove('on'); });
    if (oculto) oculto.value = '';
  });
  chips.forEach(function (c) {
    c.addEventListener('click', function () { otro.value = ''; });
  });
})();
