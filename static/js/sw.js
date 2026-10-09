

const VERSION = 'v65';
const CACHE_ESTATICOS = `finapp-estaticos-${VERSION}`;

const ORIGENES_CACHEABLES = [];

const HTML_SIN_CONEXION = `<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#191919">
<title>Sin conexión · Fintora</title>
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
      No pudimos alcanzar el servidor. Tus datos están a salvo: revisa la red y vuelve a intentar.
    </p>
    <button onclick="location.reload()"
            style="margin-top:26px;padding:13px 26px;border:none;border-radius:13px;cursor:pointer;
                   background:#ffaa2c;color:#1a1200;font:inherit;font-size:14.5px;font-weight:700">
      Reintentar
    </button>
  </div>
</body></html>`;

self.addEventListener('install', (evento) => {

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

  if (pedido.method !== 'GET') return;

  const url = new URL(pedido.url);
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return;

  if (url.pathname === '/sw.js') return;

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

  evento.respondWith((async () => {
    const cache = await caches.open(CACHE_ESTATICOS);
    const guardado = await cache.match(pedido);

    const red = fetch(pedido).then((respuesta) => {

      if (respuesta && (respuesta.ok || respuesta.type === 'opaque')) {
        cache.put(pedido, respuesta.clone());
      }
      return respuesta;
    }).catch(() => null);

    return guardado || (await red) || Response.error();
  })());
});

self.addEventListener('message', (evento) => {
  if (evento.data === 'saltar-espera') self.skipWaiting();
});

self.addEventListener('push', (evento) => {
  let datos = {};
  try { datos = evento.data ? evento.data.json() : {}; } catch (e) { datos = { cuerpo: evento.data ? evento.data.text() : '' }; }
  evento.waitUntil(self.registration.showNotification(datos.titulo || 'Fintora', {
    body: datos.cuerpo || '',
    icon: '/static/img/favicon-180.png',
    badge: '/static/img/favicon-180.png',
    tag: datos.etiqueta || 'fintora',
    lang: 'es',
    data: { url: datos.url || '/' },
  }));
});

self.addEventListener('notificationclick', (evento) => {
  evento.notification.close();
  const destino = new URL((evento.notification.data && evento.notification.data.url) || '/', self.location.origin);
  if (destino.origin !== self.location.origin) return;
  evento.waitUntil((async () => {
    const ventanas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const v of ventanas) {
      if (new URL(v.url).origin === destino.origin && 'focus' in v) {
        await v.focus();
        if ('navigate' in v) await v.navigate(destino.href);
        return;
      }
    }
    await self.clients.openWindow(destino.href);
  })());
});
