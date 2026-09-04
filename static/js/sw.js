/* Service worker de FinApp.
   ---------------------------------------------------------------------------
   Existe por dos razones, en este orden:

   1. Chrome en Android solo ofrece "Instalar app" si hay un service worker
      registrado que además responda al evento fetch. Los meta del <head>
      alcanzan para iOS, pero no para el prompt de instalación.
   2. Que la app abra con algo en pantalla cuando no hay señal, en vez del
      dinosaurio del navegador.

   Lo que NO hace, a propósito: guardar HTML de páginas con sesión iniciada.
   Esto es una app de finanzas; si el teléfono se presta o se pierde, saldos y
   movimientos no deberían quedar en el disco fuera de la sesión. Por eso las
   navegaciones van siempre a la red y, si falla, muestran la pantalla de
   abajo. Lo único que se cachea son archivos estáticos: CSS, tipografías,
   iconos e imágenes.

   Al cambiar este archivo hay que subir VERSION. El navegador compara el
   archivo byte a byte, ve la diferencia, instala el nuevo y borra los caches
   viejos en 'activate'. Sin ese cambio los usuarios se quedan con el anterior.
*/

const VERSION = 'v1';
const CACHE_ESTATICOS = `finapp-estaticos-${VERSION}`;

/* Orígenes de terceros que la app carga en cada página. Se cachean igual que
   lo propio: son inmutables y son los que más pesan en una conexión lenta. */
const ORIGENES_CACHEABLES = [
  'https://fonts.googleapis.com',
  'https://fonts.gstatic.com',
  'https://cdnjs.cloudflare.com',
];

/* La pantalla de sin conexión se arma acá y no como plantilla de Django a
   propósito: pedirla al servidor para guardarla sería pedirle algo al
   servidor justamente para el caso en que el servidor no responde. Va con los
   colores y la tipografía de la app para que no parezca un error del sistema. */
const HTML_SIN_CONEXION = `<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#191919">
<title>Sin conexión · FinApp</title>
</head>
<body style="margin:0;min-height:100dvh;display:flex;align-items:center;justify-content:center;padding:32px;
             background:#191919;color:#f5f5f5;font-family:Manrope,system-ui,-apple-system,sans-serif;
             text-align:center;-webkit-font-smoothing:antialiased">
  <div style="max-width:340px">
    <div style="width:58px;height:58px;margin:0 auto 22px;border-radius:17px;display:flex;
                align-items:center;justify-content:center;background:#ffaa2c;color:#1a1200;
                font-size:26px;font-weight:800">!</div>
    <h1 style="margin:0;font-size:22px;font-weight:800;letter-spacing:-.03em">Sin conexión</h1>
    <p style="margin:12px 0 0;font-size:14.5px;line-height:1.55;color:#a3a3a3;text-wrap:pretty">
      No pudimos alcanzar el servidor. Tus datos están a salvo: revisá la red y volvé a intentar.
    </p>
    <button onclick="location.reload()"
            style="margin-top:26px;padding:13px 26px;border:none;border-radius:13px;cursor:pointer;
                   background:#ffaa2c;color:#1a1200;font:inherit;font-size:14.5px;font-weight:700">
      Reintentar
    </button>
  </div>
</body></html>`;

self.addEventListener('install', (evento) => {
  /* Sin precache: las rutas de los estáticos llevan hash en producción
     (CompressedManifestStaticFilesStorage), así que una lista fija de URLs
     quedaría desactualizada en cada despliegue. Se llenan solos al usarse. */
  self.skipWaiting();
});

self.addEventListener('activate', (evento) => {
  evento.waitUntil((async () => {
    const nombres = await caches.keys();
    await Promise.all(
      nombres
        .filter((n) => n.startsWith('finapp-') && n !== CACHE_ESTATICOS)
        .map((n) => caches.delete(n))
    );
    await self.clients.claim();
  })());
});

function esEstatico(url) {
  if (ORIGENES_CACHEABLES.includes(url.origin)) return true;
  if (url.origin !== self.location.origin) return false;
  return url.pathname.startsWith('/static/');
}

self.addEventListener('fetch', (evento) => {
  const pedido = evento.request;

  /* Solo GET. Un POST cacheado sería un movimiento registrado dos veces. */
  if (pedido.method !== 'GET') return;

  const url = new URL(pedido.url);
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return;

  /* El propio service worker nunca se sirve desde cache: si no, una versión
     rota se perpetúa sola y no hay forma de reemplazarla. */
  if (url.pathname === '/sw.js') return;

  /* Navegaciones: red primero, y si no hay red, la pantalla de arriba.
     La respuesta no se guarda nunca. */
  if (pedido.mode === 'navigate') {
    evento.respondWith(
      fetch(pedido).catch(() => new Response(HTML_SIN_CONEXION, {
        status: 503,
        headers: { 'Content-Type': 'text/html; charset=utf-8' },
      }))
    );
    return;
  }

  if (!esEstatico(url)) return;

  /* Estáticos: se responde desde el cache al instante y se revalida por
     detrás (stale-while-revalidate). La primera carga paga la red; las
     siguientes son inmediatas aunque el servidor esté lento. */
  evento.respondWith((async () => {
    const cache = await caches.open(CACHE_ESTATICOS);
    const guardado = await cache.match(pedido);

    const red = fetch(pedido).then((respuesta) => {
      /* 'opaque' son las respuestas de otro origen sin CORS: no se puede leer
         su estado, pero sirven igual para mostrar la fuente o el icono. */
      if (respuesta && (respuesta.ok || respuesta.type === 'opaque')) {
        cache.put(pedido, respuesta.clone());
      }
      return respuesta;
    }).catch(() => null);

    return guardado || (await red) || Response.error();
  })());
});

/* Permite forzar la actualización desde la página sin esperar al próximo
   arranque en frío. Lo usa el script de registro en base.html. */
self.addEventListener('message', (evento) => {
  if (evento.data === 'saltar-espera') self.skipWaiting();
});
