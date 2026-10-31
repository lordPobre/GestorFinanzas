var datos = document.getElementById('datosPorMes');
var raiz = document.getElementById('porMes');
if (datos && raiz) iniciar(JSON.parse(datos.textContent), raiz);

function nuevo(tag, clase, texto) {
  var el = document.createElement(tag);
  if (clase) el.className = clase;
  if (texto) el.textContent = texto;
  return el;
}

function iniciar(d, raiz) {
  var estado = { esc: 'aldia', vista: 'saldo', sel: d.hoy };
  var contBarras = raiz.querySelector('#pmBarras');
  var contEventos = raiz.querySelector('#pmEventos');
  var contPersonas = raiz.querySelector('#pmPersonas');
  var leyendaEsperado = raiz.querySelector('[data-pm-leyenda-esperado]');
  var total = d.escenarios.aldia.meses.length;
  var barras = [];

  d.escenarios.aldia.meses.forEach(function (m, i) {
    var b = nuevo('button', 'pm-barra');
    b.type = 'button';
    var zona = nuevo('span', 'pm-barra-zona');
    var esperado = nuevo('span', 'pm-barra-esperado');
    var pila = nuevo('span', 'pm-barra-pila');
    var proy = nuevo('span', 'pm-barra-proy');
    var real = nuevo('span', 'pm-barra-real');
    pila.append(proy, real);
    zona.append(esperado, pila);
    var mes = nuevo('span', 'pm-barra-mes');
    mes.append(nuevo('span', '', m.corto));
    if (m.tipo === 'hoy') mes.append(nuevo('span', 'pm-hoy', 'hoy'));
    b.append(zona, mes);
    b.addEventListener('click', function () { elegir(i); });
    contBarras.append(b);
    barras.push({ boton: b, esperado: esperado, pila: pila, proy: proy, real: real });
  });

  contBarras.addEventListener('keydown', function (e) {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault();
    elegir(estado.sel + (e.key === 'ArrowLeft' ? -1 : 1));
    barras[estado.sel].boton.focus();
  });

  raiz.querySelectorAll('[data-pm-mover]').forEach(function (b) {
    b.addEventListener('click', function () { elegir(estado.sel + Number(b.dataset.pmMover)); });
  });

  function conectar(atributo, clave) {
    var botones = raiz.querySelectorAll('[' + atributo + ']');
    botones.forEach(function (b) {
      b.addEventListener('click', function () {
        estado[clave] = b.getAttribute(atributo);
        botones.forEach(function (x) {
          var on = x === b;
          x.classList.toggle('on-green', on);
          x.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
        pintar();
      });
    });
  }
  conectar('data-pm-esc', 'esc');
  conectar('data-pm-vista', 'vista');

  function elegir(i) {
    estado.sel = Math.max(0, Math.min(total - 1, i));
    pintar();
  }

  function poner(selector, texto) {
    raiz.querySelectorAll(selector).forEach(function (el) { el.textContent = texto; });
  }

  function lectura(m) {
    if (estado.vista === 'saldo') {
      var etq = m.tipo === 'hoy' ? 'Te deben hoy' : (m.tipo === 'real' ? 'Te debían a fin de mes' : 'Te deberían a fin de mes');
      return { etiqueta: etq, valor: m.saldo_txt, nota: m.tipo === 'proy' ? 'Proyección' : '' };
    }
    if (m.tipo === 'real') {
      return { etiqueta: 'Te pagaron', valor: m.real_txt, nota: m.esperado >= 1 ? 'de ' + m.esperado_txt + ' que vencía' : '' };
    }
    if (m.tipo === 'hoy') {
      return { etiqueta: 'Te pagaron este mes', valor: m.real_txt, nota: m.proy >= 1 ? 'faltan ' + m.proy_txt : '' };
    }
    var parcial = m.esperado - m.proy >= 1;
    return { etiqueta: 'Cobros esperados', valor: m.proy_txt, nota: parcial ? 'de ' + m.esperado_txt + ' que vence' : '' };
  }

  function pintarBarras(meses) {
    var cobros = estado.vista === 'cobros';
    var tope = 1;
    meses.forEach(function (m) {
      tope = Math.max(tope, cobros ? Math.max(m.real + m.proy, m.esperado) : m.saldo);
    });
    meses.forEach(function (m, i) {
      var b = barras[i];
      var real = cobros ? m.real : (m.tipo === 'proy' ? 0 : m.saldo);
      var proy = cobros ? m.proy : (m.tipo === 'proy' ? m.saldo : 0);
      var suma = real + proy;
      b.pila.style.height = (suma / tope * 100) + '%';
      b.real.style.height = suma ? (real / suma * 100) + '%' : '0';
      b.proy.style.height = suma ? (proy / suma * 100) + '%' : '0';
      var verEsperado = cobros && m.esperado >= 1;
      b.esperado.hidden = !verEsperado;
      if (verEsperado) b.esperado.style.height = (m.esperado / tope * 100) + '%';
      var on = i === estado.sel;
      b.boton.classList.toggle('on', on);
      b.boton.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.boton.tabIndex = on ? 0 : -1;
      b.boton.setAttribute('aria-label', m.largo + ': ' + (cobros ? (m.tipo === 'proy' ? m.proy_txt : m.real_txt) : m.saldo_txt));
    });
    leyendaEsperado.hidden = !cobros;
  }

  function pintarEventos(m) {
    contEventos.replaceChildren();
    if (!m.eventos.length) {
      contEventos.append(nuevo('span', 'pm-vacio', 'Sin préstamos ni pagos este mes.'));
      return;
    }
    m.eventos.forEach(function (e) {
      var fila = nuevo('div', 'pm-fila');
      var icono = nuevo('span', 'pm-icono ' + e.tipo);
      icono.append(nuevo('i', 'fas ' + e.icono));
      icono.setAttribute('aria-hidden', 'true');
      var txt = nuevo('span', 'pm-fila-txt');
      txt.append(nuevo('span', 'pm-fila-nombre', e.nombre), nuevo('span', 'pm-fila-det', e.detalle));
      var fin = nuevo('span', 'pm-fila-fin');
      fin.append(nuevo('span', 'pm-fila-monto ' + e.tipo, e.monto), nuevo('span', 'pm-fila-tag', e.tag));
      fila.append(icono, txt, fin);
      contEventos.append(fila);
    });
  }

  function pintarPersonas(lista) {
    contPersonas.replaceChildren();
    lista.forEach(function (p) {
      var caja = nuevo('div', 'pm-persona');
      var cab = nuevo('div', 'pm-persona-cab');
      var txt = nuevo('span', 'sec-txt');
      txt.append(nuevo('span', 'sec-nombre', p.nombre), nuevo('span', 'sec-meta', p.detalle));
      cab.append(nuevo('span', 'md-avatar', p.inicial), txt, nuevo('span', 'pm-persona-monto', p.pendiente));
      var barra = nuevo('span', 'pm-progreso');
      var lleno = nuevo('span');
      lleno.style.width = p.pct + '%';
      barra.append(lleno);
      var pie = nuevo('div', 'pm-persona-pie');
      pie.append(nuevo('span', 'pm-estado ' + p.estado, p.estado_txt), nuevo('span', 'pm-fin', p.fin_txt));
      if (p.ritmo_txt) pie.append(nuevo('span', '', p.ritmo_txt));
      caja.append(cab, barra, pie);
      contPersonas.append(caja);
    });
  }

  function pintar() {
    var esc = d.escenarios[estado.esc];
    var m = esc.meses[estado.sel];
    raiz.querySelectorAll('[data-pm-nota]').forEach(function (p) { p.hidden = p.dataset.pmNota !== estado.esc; });
    Object.keys(esc.resumen).forEach(function (k) { poner('[data-pm="' + k + '"]', esc.resumen[k]); });

    var l = lectura(m);
    poner('[data-pm-lectura="mes"]', m.largo);
    poner('[data-pm-lectura="etiqueta"]', l.etiqueta);
    poner('[data-pm-lectura="valor"]', l.valor);
    poner('[data-pm-lectura="nota"]', l.nota);

    poner('[data-pm-det="saldo_etq"]', m.tipo === 'hoy' ? 'Te deben hoy' : 'Saldo a fin de mes');
    poner('[data-pm-det="saldo"]', m.saldo_txt);
    if (m.tipo === 'proy') {
      poner('[data-pm-det="cobros_etq"]', 'Cobros esperados');
      poner('[data-pm-det="cobros"]', m.proy_txt);
    } else {
      poner('[data-pm-det="cobros_etq"]', m.tipo === 'hoy' ? 'Te pagaron este mes' : 'Te pagaron');
      poner('[data-pm-det="cobros"]', m.tipo === 'real' && m.esperado >= 1 ? m.real_txt + ' de ' + m.esperado_txt : m.real_txt);
    }

    raiz.querySelector('[data-pm-mover="-1"]').disabled = estado.sel <= 0;
    raiz.querySelector('[data-pm-mover="1"]').disabled = estado.sel >= total - 1;

    pintarBarras(esc.meses);
    pintarEventos(m);
    pintarPersonas(esc.personas);
  }

  pintar();
}
