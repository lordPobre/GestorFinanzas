

const VERSION = 'v139';
const CACHE_ESTATICOS = `finapp-estaticos-${VERSION}`;

const ORIGENES_CACHEABLES = [];

const HTML_SIN_CONEXION = `<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#F3EFE7">
<title>Sin conexión · Fintora</title>
</head>
<body style="margin:0;min-height:100dvh;display:flex;align-items:center;justify-content:center;box-sizing:border-box;
             padding:calc(32px + env(safe-area-inset-top)) 24px calc(32px + env(safe-area-inset-bottom));
             background:#F3EFE7;color:#1E1A15;font-family:'Familjen Grotesk',system-ui,-apple-system,'Segoe UI',sans-serif;
             -webkit-font-smoothing:antialiased">
  <div style="max-width:360px;display:flex;flex-direction:column;align-items:center;gap:14px;text-align:center">
    <span aria-hidden="true" style="width:132px;height:132px;margin-bottom:14px;border-radius:50%;
          background:radial-gradient(circle at 32% 26%,rgba(255,255,255,.85),rgba(255,255,255,0) 28%),radial-gradient(circle at 46% 56%,#E4DCCD 0%,#B9AE9C 50%,#7E7465 92%);
          box-shadow:0 40px 70px -30px rgba(126,116,101,.7),inset 0 -10px 30px rgba(0,0,0,.15)"></span>
    <span style="padding:5px 12px;border-radius:999px;background:#E7E3DC;color:#5A5248;font-size:13px;font-weight:700">Sin conexión</span>
    <h1 style="margin:0;font-size:32px;line-height:1.1;font-weight:700;letter-spacing:-.03em;text-wrap:balance">No pudimos alcanzar el servidor</h1>
    <p style="margin:0;font-size:16px;line-height:1.55;color:#4F4840;text-wrap:pretty">Tus datos están a salvo. Revisa la red y vuelve a intentar.</p>
    <button onclick="location.reload()"
            style="margin-top:8px;height:52px;padding:0 28px;border:none;border-radius:999px;cursor:pointer;
                   background:#1E1A15;color:#F3EFE7;font:inherit;font-size:16px;font-weight:700">
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

    if (/\.(css|js|json)$/.test(url.pathname)) return (await red) || guardado || Response.error();
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
