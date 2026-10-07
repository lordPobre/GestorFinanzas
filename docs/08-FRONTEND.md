# 08 · Frontend: HTML, CSS, JavaScript y PWA

## Principios

- **HTML desde el servidor.** Cada pantalla es una plantilla de Django. No hay SPA, *bundler* ni paso de compilación: lo que está en `static/` es lo que se sirve.
- **JavaScript por pantalla.** Cada plantilla carga su archivo de `static/js/pantallas/`, con `nonce`. Los datos que el script necesita viajan en atributos `data-*` o en `{{ valor|json_script }}`, nunca armando código JavaScript con plantillas.
- **Sin terceros.** Chart.js, Font Awesome, Manrope y JetBrains Mono están en `static/vendor/`. La CSP no permite otro origen.
- **Funciona sin JavaScript** en lo esencial: los formularios hacen POST normal y las vistas redirigen. El JavaScript agrega el panel deslizable, los pagos sin recargar, los gráficos y el recorrido guiado.

## Plantillas

| Base | Quién la usa | Qué trae |
| --- | --- | --- |
| `finanzas/base.html` | Todas las pantallas con sesión | Barra lateral, barra superior, barra inferior en el teléfono con botón central “Registrar”, panel de registro rápido, avisos, confirmación de acciones destructivas, franja de *staging*, *meta tags* de app instalable y registro del *service worker* |
| `registration/auth_base.html` | Acceso, registro, recuperar, restablecer, verificar | Panel de marca a la izquierda (arriba en el teléfono) y tarjeta con el formulario |
| `finanzas/legal_base.html` | Privacidad, términos y seguridad | Cabecera con versión, pestañas Privacidad / Términos / Seguridad, índice fijo y tarjeta de contacto |
| `finanzas/landing.html` | La página pública | Autónoma: hero con el teléfono que recorre cuatro pantallas en loop, la cifra, la esfera, funciones con pestañas, privacidad con la boleta y las notas de seguridad, preguntas frecuentes, ayuda, chat y cierre con redes y derechos reservados |
| `error_base.html` | `400`, `403`, `403_csrf`, `404` y `500` | Fondo oscuro con el brillo ámbar, sin depender de la sesión ni de la base |
| `finanzas/onboarding.html` | Bienvenida | Autónoma, por pasos |

Parciales que usan varias pantallas: `_esfera.html` (la esfera y su texto), `_consentimiento.html` (aviso de cookies) y `_evento.html` (evento de registro).

Hay además los correos (`correo_*.html` y `.txt`): HTML con estilos en línea y tablas, pensado para clientes de correo, siempre acompañado de su versión en texto plano. Usan el diseño oscuro de la app, 480 px de ancho y una cabecera que es una sola imagen (`static/img/correo-cabecera.png`) adjunta en línea con CID de Resend, así se ve igual en Gmail. Los enlaces se arman con `{% url_sitio %}` (`templatetags/correo_marca.py`). Los avisos de seguridad (aparato nuevo, cambio de correo, registro repetido) son solo texto.

Filtros de plantilla (`templatetags/moneda.py`): `money` (con símbolo y los decimales de la moneda del usuario), `money_signed`, `money_corto` (“$1,2 M”), `pct` y `a_json`.

## CSS (`static/css/finapp.css`)

La base es `finapp.css`, de unos 165 KB, ordenada por secciones. El índice con el selector donde empieza cada sección está en `docs/ESTILOS.md`, que se mantiene como anexo. La regla es que los estilos nuevos van en la sección de su pantalla, no al final.

Encima se cargan, en este orden:

| Archivo | Qué trae |
| --- | --- |
| `tema-vidrio.css` | El tema en vidrio de todas las pantallas con sesión y de acceso. Se carga después de `finapp.css` y gana sobre él |
| `encabezado.css` | La etiqueta del grupo del menú sobre cada título y la pastilla del saludo con el cielo animado |
| `inicio-esfera.css`, `salud-esfera.css` | La esfera en el teléfono y en la barra lateral |
| `plan-proyeccion.css`, `perfil.css`, `categorias.css`, `cartola.css`, `prestamos-acciones.css` | Ajustes de una pantalla. Se cargan después de `tema-vidrio.css` para ganarle en el teléfono |
| `landing-telefono.css`, `landing-esfera.css` | El teléfono animado y la sección de la esfera de la portada |

Las hojas por pantalla se piden con `?v=<lote>` para que el navegador no use una copia vieja.

**No tocar:** en `tema-vidrio.css`, dentro de `@media (max-width: 720px)`, las reglas `body:not(:has(.auth))::after` y `html.con-scroll body:not(:has(.auth))::after` (la franja de la barra de estado que aparece solo al hacer scroll, desde el lote 29). La clase `con-scroll` la pone `base-2.js`.

### Tokens (`:root`)

| Grupo | Variables |
| --- | --- |
| Fondos | `--bg` #191919 · `--bg-elev` #212121 · `--surface` #383838 · `--surface-2` · `--surface-3` |
| Líneas | `--line` (blanco 7 %) · `--line-fuerte` (13 %) |
| Acento | `--amber` #ffaa2c · `--amber-claro` · `--amber-oscuro` #f09000 · `--amber-tenue` · `--amber-borde` · `--tinta-ambar` #1a1200 (texto sobre ámbar) |
| Estados | `--green` #53d258 (entra, pagado, seguro) · `--coral` #e25c5c (sale, atrasado) · `--blue` · cada uno con `-tenue` y `-borde` |
| Texto | `--text-primary` #f5f5f5 · `--text-secondary` (72 %) · `--text-muted` (58 %) · `--text-tenue` (42 %) |
| Radios | `--r-sm`, `--r-md`, `--r-lg`, `--r-xl` y la píldora. Las auditorías visuales (lotes 56 a 66) pasaron todos los radios a estos tokens |
| Texto de error | `--coral-texto`: coral legible sobre fondo oscuro |
| Movimiento | `--ease-out` · `--ease-spring` |

Tipografía: Manrope para todo el texto y JetBrains Mono para cifras que se comparan (montos en tablas, números de cuota).

### Prefijos por zona

`.lp-` landing · `.legal-` páginas legales · `.auth-` acceso · `.ob-` bienvenida · `.tour-` recorrido · `.cartola-` importar · `.deuda-` cuotas · `.subs-` suscripciones · `.prestamo-` me deben · `.ia-` análisis con IA.

### Teléfono

- Hay dos cortes: `@media (max-width: 1000px)` (la barra lateral pasa a barra inferior) y `(max-width: 720px)`. La landing y las legales usan 900 px.
- Se respetan las áreas seguras (`env(safe-area-inset-*)`), la barra de estado translúcida en iPhone y objetivos táctiles de 44 px como mínimo. En pantallas táctiles sin mouse, lo que en el computador aparece al pasar el mouse se ve siempre.
- Letra de 12 px como mínimo en todas las pantallas.
- Los ajustes de teléfono de varias pantallas están juntos en la sección de la barra inferior. Moverlos puede cambiar qué regla gana (ver `docs/ESTILOS.md` y D12).

### Accesibilidad

- Foco visible en todos los controles.
- `prefers-reduced-motion` apaga las animaciones de la landing, del recorrido, del chat, del cielo del saludo y de los anillos de las metas.
- El contraste del texto sobre el fondo oscuro y sobre el ámbar se revisó en el lote 12.

## JavaScript

### Global: `static/js/finapp.js`

Se carga en `base.html`. Marca `window.__finappJsCargado`, para no inicializar dos veces.

| Función | Qué hace |
| --- | --- |
| Modales y hojas | `finappOpen(id)` y `finappClose()`, cierre con Esc y con el fondo |
| Confirmación | Intercepta el envío de los formularios que piden confirmación y la muestra en una hoja propia (`pedirConfirmacion(texto, destructivo, alAceptar)`), en vez de `confirm()` del navegador |
| Registro rápido | El panel del botón “Registrar”: gasto o ingreso (`abrirComo(tipo)`), teclado de monto, categorías según el tipo |
| Filas deslizables | En el teléfono, deslizar una fila de pago o de movimiento muestra las acciones (pagar, anular, editar) |
| Acciones AJAX | Los botones de pagar, anular y abonar envían con `fetch` y `X-Requested-With`, y actualizan la fila con la respuesta JSON |

### Por pantalla: `static/js/pantallas/*.js`

Hay 50 archivos, uno o más por plantilla, con el nombre de la plantilla (`dashboard.js`, `deudas.js`, `revisar-cartola.js`…). Los que terminan en `-2`, `-3`, etc. son bloques distintos de la misma plantilla que se separaron al sacar los `<script>` en línea (lote 4). Casos destacados:

- `dashboard.js` y `estadisticas.js`: gráficos con Chart.js, con formato chileno y cifras cortas en pantallas angostas.
- `analisis-2.js`: pide la interpretación a `/analisis/ia/` y la pinta con `textContent`.
- `revisar-cartola.js`: totales en vivo al marcar o desmarcar filas, y mostrar u ocultar las opciones de cuotas y “me deben”.
- `verificar.js`: seis casillas para el código, con pegado y avance automático.
- `landing.js`: teléfono animado, pestañas, aparición al bajar y chat de ayuda.
- `legal.js`: índice construido desde las secciones y marca de la sección actual.
- `inicio-cifra.js`: los botones Gastos, Ingresos y Puedes gastar del Inicio.
- `inicio-movimientos.js`: filtros, sumas y títulos de día de la lista de movimientos.
- `plan-simulador.js`: el simulador de cuotas del Plan.
- `plan-proyeccion.js`: los gráficos del fondo para imprevistos y del depósito a plazo.
- `inicio-esfera.js`: la hoja que se baja, la esfera, el saludo al entrar y la voz (ver [02](02-ARQUITECTURA.md#la-voz-de-la-esfera)). Deja `window.finappEsfera` para el tour.
- `saludo-cielo.js`: el sol o la luna del saludo según la hora, actualizado cada minuto.
- `categorias-2.js`: porcentaje y barra de cada categoría.
- `base-2.js`: la clase `con-scroll` y la recarga cuando Safari muestra una página guardada al ir Atrás.
- `recordatorios.js`: el interruptor de Perfil, el permiso del navegador, suscribir o quitar el aparato, «Probar aviso» y la invitación de Inicio, que «Ahora no» esconde en ese aparato (`localStorage`). En un iPhone sin la app instalada explica cómo agregarla.
- `categorias-topes.js`: la ventana «Poner tope», con el promedio y la sugerencia de un 10 % menos.
- `anotar-tope.js`: el aviso del panel Registrar cuando el gasto llega al 80 % o pasa el tope. Lee `topes_json`, que agrega `contadores`.

### Consentimiento: `static/js/consentimiento.js`

Solo en las páginas públicas y si hay al menos un píxel configurado. Muestra el aviso de cookies, carga Google Analytics y los píxeles solo después de «Aceptar», y al rechazar después de haber aceptado borra sus cookies y recarga.

### Face ID: `static/js/passkeys.js`

Expone `window.FintoraPasskeys = { soportado, registrar, entrar, mensaje }`. Convierte entre base64url y `ArrayBuffer`, llama a `navigator.credentials.create/get` con las opciones del servidor y envía la credencial con el token CSRF. `mensaje()` traduce los errores del navegador (cancelado, no permitido, sin soporte) a texto en español.

### Celular o computador: `static/js/dispositivo.js`

Expone `window.FintoraDispositivo.movil` y agrega la clase `es-movil` a `<html>` en iPhone, iPad, Android o pantallas táctiles sin mouse. El CSS oculta `[data-solo-movil]` en el computador y `[data-solo-pc]` en el celular. Se usa para que Face ID solo aparezca en celular y tablet; `login.js` además no muestra el botón si `movil` es falso.

### Recorrido guiado: `static/js/tour.js`

Expone `window.finappTour = { iniciar, mostrar, reiniciar }`. Recorre las pantallas con un foco sobre el elemento real (`data-tour="…"` en las plantillas) y una tarjeta de explicación. Arranca con `?tour=1` después de la bienvenida. `reiniciar()` lo vuelve a empezar. Guarda el avance en `localStorage` y distingue entre el recorrido completo y el de “novedades” para quien ya lo hizo, según la versión (hoy la 4, que sumó «La esfera de tu mes»). Hay pasos solo para el teléfono (la esfera, el botón «Gasto» de Inicio) y solo para el computador (la salud del mes de la barra lateral), así la cuenta de pasos sale bien en cada aparato.

### Estado en `localStorage`

Las claves usan el prefijo `finapp.` (por ejemplo, `finapp.pasos.oculto`, la lista de primeros pasos oculta, y las del recorrido). **No se deben renombrar:** cambiar la clave hace que reaparezca lo que cada persona ocultó o terminó.

## PWA

| Pieza | Dónde |
| --- | --- |
| Manifiesto | `static/site.webmanifest` (nombre, íconos, `display: standalone`, colores). Los íconos de 192 y 512 px, y el *maskable*, están en `static/img/` |
| Íconos | `static/img/favicon.svg`, `favicon.png`, `favicon-180.png` (iPhone) |
| *Service worker* | `static/js/sw.js`, servido en `/sw.js` para que controle todo el sitio |
| Entrada | La app instalada abre `/?fuente=pwa`: sin sesión va directo al acceso, sin pasar por la landing |

Estrategia del *service worker* (versión `v64` en el lote 86; se sube en cada lote que cambia CSS o JS):

- **Navegación:** siempre por la red. Si no hay conexión, muestra una página “Sin conexión” embebida. **Nunca guarda HTML**: una página con datos financieros no queda en la caché del teléfono.
- **`/static/`:** *stale-while-revalidate*. Sirve lo guardado y actualiza en segundo plano. Los nombres llevan hash (manifiesto de WhiteNoise), así que una versión nueva nunca choca con una vieja.
- **Al activarse:** borra las cachés `finapp-*` de versiones anteriores, toma control de las pestañas abiertas y las recarga, para que nadie quede con un JavaScript viejo.
- **Avisos:** el evento `push` muestra el aviso con título, cuerpo y etiqueta (uno nuevo con la misma etiqueta reemplaza al anterior). Al tocarlo, abre la dirección que trae si es de Fintora, en una pestaña abierta si la hay.
- **Para forzar una actualización** de algo que no esté en `/static/`, se sube `VERSION`.

## Cómo agregar una pantalla

1. La vista en `finanzas/views/<tema>.py`, con `@login_required` y `context.update(contadores(request.user))`.
2. La ruta en `urls.py` con el estilo `/<recurso>/<id>/<acción>/`.
3. La plantilla extendiendo `finanzas/base.html`, con `{% block title %}… · Fintora{% endblock %}`.
4. Los estilos en su sección de `finapp.css` o en una hoja propia que se carga después de `tema-vidrio.css`, con los tokens y sin colores escritos a mano. Actualizar `docs/ESTILOS.md` si es una sección nueva. Subir la versión de `sw.js`.
5. El script en `static/js/pantallas/<plantilla>.js`, cargado con `<script src="{% static … %}" nonce="{{ csp_nonce }}">`. Nada de `onclick=` en el HTML: la CSP lo bloquea.
6. Si la pantalla tiene un paso en el recorrido, agregar `data-tour` y el paso en `tour.js`.
