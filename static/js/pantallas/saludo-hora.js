      (function () {
        function texto(h) {
          if (h >= 7 && h < 12) return 'Buenos días';
          if (h >= 12 && h < 20) return 'Buenas tardes';
          return 'Buenas noches';
        }
        function pintar() {
          var t = texto(new Date().getHours());
          var nodos = document.querySelectorAll('[data-saludo]');
          for (var i = 0; i < nodos.length; i++) nodos[i].textContent = t;
        }
        pintar();

        window.setInterval(pintar, 60000);
        document.addEventListener('visibilitychange', function () {
          if (!document.hidden) pintar();
        });
      })();
