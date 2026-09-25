(function () {
  var script = document.currentScript;
  var btn = document.getElementById('btnIA');
  if (!btn || !script) return;
  var urlIA = script.dataset.urlIa;
  var caja = document.getElementById('cajaIA');
  var estado = document.getElementById('iaEstado');
  var contenido = document.getElementById('iaContenido');

  function fallo(msg) {
    contenido.style.display = 'none';
    estado.style.display = 'block';
    estado.textContent = msg;
  }

  function pintar(ia) {
    if (!ia || typeof ia !== 'object' || !ia.diagnostico) {
      fallo('La respuesta llegó incompleta. Vuelve a intentarlo.');
      return;
    }

    document.getElementById('iaDiagnostico').textContent = ia.diagnostico;

    var recs = Array.isArray(ia.recomendaciones) ? ia.recomendaciones : [];
    var cajaRecs = document.getElementById('iaRecs');
    cajaRecs.innerHTML = '';
    recs.forEach(function (r, i) {
      var fila = document.createElement('div');
      fila.className = 'ia-rec';
      var num = document.createElement('span');
      num.className = 'ia-rec-num';
      num.textContent = i + 1;
      var txt = document.createElement('div');
      txt.className = 'ia-rec-txt';
      txt.textContent = r;
      fila.appendChild(num);
      fila.appendChild(txt);
      cajaRecs.appendChild(fila);
    });
    document.getElementById('iaBloqueRecs').style.display = recs.length ? 'block' : 'none';

    if (ia.proyeccion_texto) {
      document.getElementById('iaProyeccion').textContent = ia.proyeccion_texto;
      document.getElementById('iaBloqueProy').style.display = 'block';
    }
    if (ia.mensaje_motivacional) {
      document.getElementById('iaMotivacional').textContent = ia.mensaje_motivacional;
      document.getElementById('iaBloqueMotiv').style.display = 'block';
    }

    estado.style.display = 'none';
    contenido.style.display = 'block';
  }

  btn.addEventListener('click', function () {
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-circle-notch fa-spin" style="font-size:11px"></i>Pensando…';
    caja.style.display = 'block';
    contenido.style.display = 'none';
    estado.style.display = 'block';
    estado.textContent = 'Leyendo tus números…';

    fetch(urlIA, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) pintar(d.ia);
        else fallo('La IA no está disponible ahora. Los números de arriba no dependen de ella.');
      })
      .catch(function () {
        fallo('No se pudo conectar. Los números de arriba no dependen de la IA.');
      })
      .finally(function () {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-wand-magic-sparkles" style="font-size:11px"></i>Explicarlo con IA';
      });
  });
})();
