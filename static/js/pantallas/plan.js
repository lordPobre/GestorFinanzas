(function () {
  var script = document.currentScript;
  var nodo = document.getElementById('d-plan');
  if (!nodo || !script) return;
  var d = JSON.parse(nodo.textContent);
  var urlIA = script.dataset.urlIa;
  var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
               'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  var estado = { ahorro: d.ahorro, extra: d.extra, estrategia: 'saldo' };

  var $ = function (id) { return document.getElementById(id); };
  var inAhorro = $('planAhorro');
  var inExtra = $('planExtra');

  function plata(n) {
    return (n < 0 ? '−' : '') + (d.simbolo || '$') + Math.round(Math.abs(n)).toLocaleString('es-CL');
  }
  function mes(n) {
    var t = d.mes - 1 + n - 1;
    return MESES[t % 12] + ' ' + (d.anio + Math.floor(t / 12));
  }
  function mayus(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  function meses(n) { return n + (n === 1 ? ' mes' : ' meses'); }
  function sinExtra(x) { return Math.ceil(x.saldo / x.cuota); }

  function ordenar(lista, estrategia) {
    return lista.slice().sort(function (a, b) {
      return estrategia === 'cuota' ? (b.cuota - a.cuota) || (a.saldo - b.saldo)
                                    : (a.saldo - b.saldo) || (b.cuota - a.cuota);
    });
  }

  function simular(lista, extra, estrategia) {
    var filas = ordenar(lista, estrategia).map(function (x) {
      return { nombre: x.nombre, saldo: x.saldo, cuota: x.cuota, resta: x.saldo, fin: 0 };
    });
    if (extra <= 0) {
      filas.forEach(function (f) { f.resta = 0; f.fin = sinExtra(f); });
      return filas;
    }
    var liberado = 0, m = 0;
    var quedan = function () { return filas.some(function (f) { return f.resta > 0; }); };
    while (quedan() && m < 600) {
      m++;
      var bolsa = extra + liberado;
      filas.forEach(function (f) {
        if (f.resta <= 0) return;
        var pago = Math.min(f.cuota, f.resta);
        f.resta -= pago;
        bolsa += f.cuota - pago;
      });
      for (var i = 0; i < filas.length && bolsa > 0; i++) {
        if (filas[i].resta <= 0) continue;
        var p = Math.min(bolsa, filas[i].resta);
        filas[i].resta -= p;
        bolsa -= p;
      }
      liberado = 0;
      filas.forEach(function (f) {
        if (f.resta <= 0) { f.fin = f.fin || m; liberado += f.cuota; }
      });
    }
    return filas;
  }

  function texto(sel, valor) {
    document.querySelectorAll('[data-plan="' + sel + '"]').forEach(function (el) { el.textContent = valor; });
  }

  function pct(v) { return Math.max(0, Math.min(100, v)) + '%'; }

  function pintarResumen() {
    var total = estado.ahorro + estado.extra;
    var escala = total > d.sobra && total > 0 ? d.sobra / total : 1;
    $('planBarAhorro').style.width = pct(estado.ahorro * escala / d.sobra * 100);
    $('planBarExtra').style.width = pct(estado.extra * escala / d.sobra * 100);
    var libre = d.sobra - total;
    var elLibre = $('planLibre');
    elLibre.textContent = plata(libre);
    elLibre.classList.toggle('rojo', libre < 0);
    $('planExcede').hidden = libre >= 0;
    texto('ahorro', plata(estado.ahorro));
    texto('extra', plata(estado.extra));
  }

  function pintarFondo() {
    var avance = d.meta ? Math.round(d.llevas / d.meta * 100) : 0;
    if ($('planFondoBar')) {
      $('planFondoBar').style.width = pct(avance);
      $('planFondoPct').textContent = avance + '% de la meta';
    }
    var falta = Math.max(0, d.meta - d.llevas);
    var r = $('planFondoResultado');
    if (!falta) r.textContent = 'Ya completaste el fondo.';
    else if (!estado.ahorro) r.textContent = 'Sin aporte mensual el fondo no avanza.';
    else {
      var n = Math.ceil(falta / estado.ahorro);
      r.textContent = 'Completas el fondo en ' + mes(n) + ', en ' + meses(n) + '.';
    }
  }

  function pintarDeudas() {
    var caja = $('planDeudas');
    if (!caja) return;
    var filas = simular(d.deudas, estado.extra, estado.estrategia);
    caja.innerHTML = '';
    filas.forEach(function (f, i) {
      var antes = sinExtra(f) - f.fin;
      var fila = document.createElement('div');
      fila.className = 'pl-deuda' + (i === 0 ? ' on' : '');
      var pos = document.createElement('span');
      pos.className = 'pl-pos';
      pos.textContent = i + 1;
      var medio = document.createElement('span');
      medio.className = 'sec-txt';
      var nom = document.createElement('span');
      nom.className = 'sec-nombre';
      nom.textContent = f.nombre;
      var det = document.createElement('span');
      det.className = 'sec-meta';
      det.textContent = 'Debes ' + plata(f.saldo) + ' · cuota ' + plata(f.cuota);
      medio.appendChild(nom);
      medio.appendChild(det);
      var fin = document.createElement('span');
      fin.className = 'pl-fin';
      var cuando = document.createElement('b');
      cuando.textContent = mayus(mes(f.fin));
      var dif = document.createElement('span');
      if (antes > 0) dif.className = 'antes';
      dif.textContent = antes > 0 ? meses(antes) + ' antes' : 'sin cambio';
      fin.appendChild(cuando);
      fin.appendChild(dif);
      fila.appendChild(pos);
      fila.appendChild(medio);
      fila.appendChild(fin);
      caja.appendChild(fila);
    });

    var finTodo = Math.max.apply(null, filas.map(function (f) { return f.fin; }));
    var finBase = Math.max.apply(null, filas.map(sinExtra));
    var primera = Math.min.apply(null, filas.map(function (f) { return f.fin; }));
    $('planDeudaResultado').textContent = estado.extra > 0
      ? 'Terminas todo en ' + mes(finTodo) + ', ' + meses(finBase - finTodo) + ' antes. La primera cuota se libera en ' + mes(primera) + '.'
      : 'Sin extra terminas en ' + mes(finBase) + ', cuando vence la última cuota.';
    $('planEstrategiaNota').textContent = estado.estrategia === 'saldo'
      ? 'Terminas antes la primera deuda y ves avance rápido.'
      : 'Liberas antes la cuota más grande y el mes queda más holgado.';

    document.querySelectorAll('[data-estrategia]').forEach(function (b) {
      var activo = b.dataset.estrategia === estado.estrategia;
      b.setAttribute('aria-pressed', activo ? 'true' : 'false');
    });
  }

  function pintar() { pintarResumen(); pintarFondo(); pintarDeudas(); }

  inAhorro.addEventListener('input', function () { estado.ahorro = +inAhorro.value; pintar(); });
  if (inExtra) inExtra.addEventListener('input', function () { estado.extra = +inExtra.value; pintar(); });
  document.querySelectorAll('[data-estrategia]').forEach(function (b) {
    b.addEventListener('click', function () { estado.estrategia = b.dataset.estrategia; pintar(); });
  });

  var btn = $('planIABtn');
  var btnTexto = $('planIABtnTexto');
  var estadoIA = $('planIAEstado');
  var parrafos = $('planIAParrafos');

  function avisoIA(msg) {
    parrafos.hidden = true;
    estadoIA.hidden = false;
    estadoIA.textContent = msg;
  }

  btn.addEventListener('click', function () {
    btn.disabled = true;
    btnTexto.textContent = 'Leyendo tu plan…';
    avisoIA('Leyendo tu plan…');
    var q = new URLSearchParams({ ahorro: estado.ahorro, extra: estado.extra, estrategia: estado.estrategia });
    fetch(urlIA + '?' + q.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (!res.ok || !Array.isArray(res.parrafos)) {
          avisoIA(res.desactivado ? 'Tienes el análisis con IA desactivado. Puedes activarlo en Perfil.'
                                  : 'La IA no está disponible ahora. Los números del plan no dependen de ella.');
          return;
        }
        parrafos.innerHTML = '';
        res.parrafos.forEach(function (t) {
          var p = document.createElement('p');
          p.textContent = t;
          parrafos.appendChild(p);
        });
        estadoIA.hidden = true;
        parrafos.hidden = false;
        btnTexto.textContent = 'Volver a explicar';
        btn.classList.add('vidrio');
      })
      .catch(function () { avisoIA('No se pudo conectar. Los números del plan no dependen de la IA.'); })
      .finally(function () {
        btn.disabled = false;
        if (btnTexto.textContent === 'Leyendo tu plan…') btnTexto.textContent = 'Explicar mi plan';
      });
  });

  pintar();
})();
