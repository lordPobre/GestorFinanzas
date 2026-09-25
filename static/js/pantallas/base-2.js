  (function () {
    if (!('serviceWorker' in navigator)) return;
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js').then(function (reg) {

        reg.addEventListener('updatefound', function () {
          var nuevo = reg.installing;
          if (!nuevo) return;
          nuevo.addEventListener('statechange', function () {
            if (nuevo.state === 'installed' && navigator.serviceWorker.controller) {
              nuevo.postMessage('saltar-espera');
            }
          });
        });
      }).catch(function () {

      });

      var recargado = false;
      navigator.serviceWorker.addEventListener('controllerchange', function () {
        if (recargado) return;
        recargado = true;
        window.location.reload();
      });
    });
  })();
