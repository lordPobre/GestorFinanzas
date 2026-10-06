# 02 · Arquitectura

## Panorama

Fintora es un monolito Django que renderiza HTML en el servidor. No hay API pública ni *framework* de front-end: cada pantalla es una plantilla de Django con CSS propio y un JavaScript pequeño por pantalla, y las acciones rápidas (pagar una cuota, abonar) usan `fetch` contra las mismas vistas. Se instala en el teléfono como PWA.

| Capa | Tecnología |
| --- | --- |
| Lenguaje | Python 3.13 |
| Framework | Django 5.2 LTS (5.2.17; soporte hasta abril de 2028) |
| Base de datos | PostgreSQL 17 en producción (Railway) y SQLite en modo WAL en desarrollo |
| Caché | `DatabaseCache` (tabla `cache_finapp`) con Postgres, `LocMemCache` sin él |
| Archivos estáticos | WhiteNoise, con manifiesto y compresión en producción |
| Fotos de perfil | Cloudflare R2 (API S3, `django-storages`) con URL firmada de 6 h. Sin credenciales, al disco |
| Correo | API HTTP de Resend |
| IA | API de Anthropic: `claude-sonnet-4-6` para el análisis y el plan, y `claude-haiku-4-5` para el chat de ayuda |
| Voz | API de ElevenLabs para la esfera (`voz.py`). Modelo `eleven_multilingual_v2` por defecto |
| Acceso | Contraseña (Argon2), TOTP (`pyotp`), WebAuthn (`webauthn`) y Google OAuth/OIDC |
| Lectura de cartolas | `pypdf` 6 y `openpyxl` 3.1, con `defusedxml` para abrir los Excel |
| Fotos | Pillow: toda foto subida se vuelve a guardar como JPEG de máximo 1024 px, sin EXIF (`fotos.py`) |
| Servidor | gunicorn 23: 2 workers × 4 hilos, *timeout* de 60 s |
| Monitoreo | Sentry opcional (`SENTRY_DSN`), sin datos personales |
| Front-end | CSS propio (`finapp.css`, el tema en vidrio `tema-vidrio.css` y hojas por pantalla), Chart.js 4 servido desde `static/vendor`, Font Awesome y las fuentes Manrope y JetBrains Mono servidas localmente |

## Estructura del repositorio

```
core/                 settings, urls raíz, wsgi/asgi
finanzas/
  models/             un archivo por tema (ver 03)
  views/              una pantalla o grupo por archivo (ver 04)
    comun.py          contexto compartido y utilidades de vista
  servicios/          cálculos puros: reciben usuario y fechas, devuelven datos
    mes.py            resumen del mes, salud financiera, caché de meses cerrados
    cuotas.py         series y proyecciones de cuotas
    pendientes.py     lista de pagos del mes y calendario
    panel.py          series, desglose, avisos y primeros pasos del inicio
    ritmo.py          aviso de ritmo de gasto por categoría
    suscripciones.py  generación de cobros mensuales
    detectar_suscripciones.py  cobros repetidos que parecen suscripciones
    esfera.py         color y frase de la esfera de cada pantalla
    esfera_bienvenida.py  saludo al entrar y cambio de estado desde la última vez
    actividad.py      la lista de Actividad de la cuenta
    senales.py        invalidación de caché al cambiar datos
  cartolas/           lectores de extractos bancarios (ver 05)
  management/commands/  tareas programadas (ver 10)
  templates/finanzas/, templates/registration/
  templatetags/       moneda.py (dinero), voz.py (textos firmados para la voz), esfera_salud.py, marketing.py, correo_marca.py
  analisis.py         motor determinístico del diagnóstico
  ia.py               interpretación con Claude
  chat_ayuda.py       chat de la landing
  seguridad.py        topes de intentos y de peticiones (tabla Contador)
  redirecciones.py    destinos `next` solo del propio dominio
  aparatos.py         cookie de aparato conocido y aviso de acceso nuevo
  fotos.py            normaliza las fotos de perfil
  voz.py              síntesis de voz con ElevenLabs y caché del audio
  marketing.py        analítica y píxeles de las páginas públicas
  comprobaciones.py   comprobaciones propias de check --deploy
  middleware.py       dominio canónico, CSP con nonce, sin caché, sesión absoluta y registro de actividad
  auditoria.py        eventos de seguridad
  sesiones.py         sesiones abiertas y cierre a distancia
  verificacion.py     confirmación de correo
  google_login.py     acceso con Google
  correo.py           envío por Resend
  avisos.py           contenido del aviso mensual
  inactividad.py      aviso y borrado de cuentas abandonadas
  encuesta.py         reglas y resumen de la encuesta
  exportar.py         Excel y CSV
  almacenamiento.py   disco o R2
  legal.py            versión de la política y páginas legales
  context_processors.py  moneda y entorno
  tests/
static/               css, js (finapp.js, tour.js, passkeys.js, sw.js, pantallas/), img, vendor
docs/                 esta documentación
railway.json          build y despliegue del servicio web
railway/              servicios programados: avisos, inactivas, respaldo, avatares y limpieza
.gitleaks.toml        excepciones del escaneo de secretos del CI
```

## La regla de las capas

Una **vista** lee la petición, llama a `servicios/` o a los modelos y arma la respuesta. Un **servicio** no lee `request`, no manda mensajes y no redirige: recibe usuario y fechas y devuelve diccionarios. Un **modelo** calcula lo que se deduce de sus propios campos (periodos de una cuota, urgencia, marca de una suscripción).

Esto permite probar los cálculos sin simular peticiones y reusarlos desde los comandos programados: `avisar_pagos` usa los mismos servicios que el inicio.

## Recorrido de una petición

```
Navegador
  → Railway (TLS, proxy: agrega X-Forwarded-For y X-Forwarded-Proto)
  → gunicorn
  → SecurityMiddleware            HTTPS, HSTS, nosniff, referrer, COOP
  → DominioCanonicoMiddleware     otro nombre de host → DOMINIO_CANONICO (301 en GET, 308 en el resto)
  → PoliticaContenidoMiddleware   genera el nonce; al salir, escribe la CSP y el X-Robots-Tag
  → SessionMiddleware
  → WhiteNoiseMiddleware          /static/ se responde aquí y no llega a Django
  → CommonMiddleware
  → CsrfViewMiddleware
  → AuthenticationMiddleware
  → SinCacheMiddleware            Cache-Control: no-store, private si hay sesión
  → MessageMiddleware
  → SesionAbsolutaMiddleware      cierra la sesión a los SESION_MAXIMA_HORAS desde que se entró
  → XFrameOptionsMiddleware       DENY
  → ActividadMiddleware           una vez al día: ultima_actividad; cada 15 min: SesionActiva.ultima_vez
  → vista → servicios → modelos → plantilla (+ context processors)
```

Los *context processors* agregan a toda plantilla: símbolo y decimales de la moneda del usuario, si el entorno es *staging* (para mostrar la franja de aviso), el `csp_nonce`, los datos legales (`legal.version`, `legal.correo_contacto`…) y si el acceso con Google está disponible.

Las señales que se registran en `FinanzasConfig.ready()` son tres. `sesiones` anota las sesiones al entrar y al salir. `auditoria` anota el acceso, la salida y los fallos. `servicios.senales` invalida la caché del mes cuando cambia una `Transaccion`, una `Deuda` o un `PagoCuota`.

## El cálculo del mes

Es el corazón del producto: la cifra “cuánto puedes gastar”. Vive en `servicios/mes.resumen_mes(usuario, año, mes)`.

```
ingresos        = Σ INGRESO del mes
gastos          = Σ EGRESO del mes que no son cuota (pagados + por pagar)
                  incluye los cobros de suscripciones y las cuentas por pagar,
                  porque ambos generan su propio egreso
cuotas del mes  = Σ cuota de cada compra con cobro este mes
                  (monto del PagoCuota si está pagada, monto_cuota_de si no)
arrastrado      = Σ cuotas de meses anteriores que siguen sin pagar
                  (solo cuando se mira el mes en curso)
comprometido    = gastos + cuotas del mes + arrastrado
disponible      = ingresos − comprometido
por día         = max(0, disponible) / días que quedan del mes, contando hoy
```

Los egresos con `es_cuota=True`, los que se crean al pagar una cuota, se excluyen de `gastos` porque la cuota ya está en `cuotas del mes`. `test_cuotas.py` cubre ese caso y el del arrastre sin doble conteo.

Encima del resumen se calculan dos cosas:

- **Salud financiera** (`salud_financiera`): parte de 100 y resta puntos según lo que queda libre, el peso de las cuotas sobre el ingreso (DTI) y el porcentaje ya gastado. Termina en *muy buena*, *buena*, *justa* o *apretada*, con una frase que explica por qué.
- **Meses cerrados en caché** (`numeros_mes`): los meses pasados se guardan 7 días en caché. La clave incluye una versión por usuario (`mes-version:{id}`). Cuando cambia un dato, las señales cambian la versión y toda la caché de ese usuario queda obsoleta de una vez, sin tener que buscar clave por clave. El mes en curso siempre se calcula en vivo.

## Motor de análisis

`analisis.analizar_finanzas(usuario)` no usa IA. Hace estos cálculos:

- Promedia el ingreso y el gasto (sin cuotas) de los 3 meses anteriores. Si da cero, usa el mes en curso.
- Calcula la deuda restante, la cuota mensual total, el DTI, el flujo libre y la fecha en que termina de pagar todo.
- Proyecta 7 meses de saldo de deuda y pago mensual.
- Asigna un puntaje de riesgo de 0 a 100 con factores explicados: DTI sobre 20, 35 o 45 %; flujo negativo o menor al 10 %; deudas sin ingresos anotados; cinco o más compras a plazo. El nivel resultante es *saludable*, *moderado*, *alto* o *crítico*.

La IA (`ia.py`) solo recibe esos agregados y los redacta en lenguaje natural. Ver [07 · Privacidad](07-PRIVACIDAD-Y-CUMPLIMIENTO.md#inteligencia-artificial).

## Suscripciones: cómo aparecen solas cada mes

`servicios/suscripciones.generar_cobros_suscripciones(usuario)` recorre las suscripciones activas y crea un egreso `Suscripción: {nombre}` por cada mes que falte, desde `ultimo_mes_generado` hasta el mes en curso. El del mes en curso queda por pagar y los anteriores, pagados. Se llama al abrir el inicio, al crear o reactivar una suscripción y antes de mandar el aviso mensual. No hay un proceso de fondo: los cobros se generan cuando el usuario vuelve.

## Ritmo de gasto

`servicios/ritmo.ritmo_del_mes(usuario, hoy)` arma los avisos «A este ritmo» de la campana. Solo mira el gasto del día a día: excluye cuotas, cobros de suscripciones y cuentas por pagar, porque son fijos.

- Por cada categoría suma lo que se lleva este mes y lo que en promedio se gastó **desde este mismo día hasta fin de mes** en los 3 meses anteriores.
- Avisa si esa proyección queda **20% o más** sobre el promedio mensual y la diferencia es de al menos **$10.000**. Muestra hasta 3, las que más se pasan, con cuánto queda por día para volver al promedio.
- No avisa antes del **día 7** ni con menos de **2 meses** de historial. Si nada se pasa y el total va 15% o más bajo el promedio, felicita.
- Solo corre al mirar el mes en curso. Las constantes están al inicio del archivo.

## Suscripciones sugeridas

`servicios/detectar_suscripciones.sugerencias(usuario, hoy)` revisa los egresos de los últimos 6 meses que no son cuota ni ya están unidos a una suscripción. Agrupa por una clave: la marca si `buscar_marca` la reconoce, o las tres primeras palabras de la descripción sin números ni palabras de relleno («PAC», «PAGO», «COMPRA»…).

- Sugiere un grupo si tiene **un solo cobro por mes**, en **3 meses seguidos** o más, con montos a menos de **10%** de la mediana y el último cobro hace 45 días o menos.
- Descarta lo que ya se parece a una suscripción registrada y lo que la persona marcó con «No es» (`SugerenciaDescartada`). Muestra hasta 5, las más caras primero.
- Al agregar, crea la `Suscripcion`, une a ella los cobros detectados y, si ya se cobró este mes, crea el `PagoServicio` y marca el mes como generado para no duplicarlo.

## Simulador de cuotas

`static/js/pantallas/plan-simulador.js` corre entero en el navegador con los datos que `plan.armar_plan` ya entrega. Parte de lo que sobra al mes y, mes a mes, suma la cuota de cada compra activa que ya terminó y resta la cuota nueva mientras dure. Verde si alcanza y sigue el plan, ámbar si alcanza pero no para lo apartado en ahorro y deudas, rojo si falta plata.

## La esfera

En el teléfono, la hoja de Inicio, Cuotas, Me deben, Suscripciones y Metas se baja arrastrando la manilla y detrás aparece la esfera. `servicios/esfera.py` calcula para cada pantalla el estado, el color, la etiqueta, la nota y la frase que se lee en voz alta. La plantilla es `_esfera.html` y el comportamiento, `inicio-esfera.js`.

| Pantalla | Rojo | Amarillo | Verde |
| --- | --- | --- | --- |
| Inicio | 100 % o más del ingreso del mes gastado | De 80 % a 99 % (`UMBRAL_AMARILLO`) | Bajo 80 % |
| Cuotas | Hay cuotas atrasadas | Alguna vence pronto | Al día |
| Me deben | | Alguien debe | Nadie debe |
| Suscripciones | Alguna atrasada | Falta pagar alguna este mes | Todas pagadas |
| Metas | Una meta sin cumplir pasó su fecha | Bajo 70 % del total (`UMBRAL_METAS_VERDE`) | Desde 70 % |

Metas sin metas, e Inicio sin ingresos, quedan en gris. Los topes de lo que se lee (5 personas, 8 suscripciones, 5 metas) son constantes al inicio de `esfera.py`.

**Al entrar.** La primera visita a Inicio después de iniciar sesión abre con la hoja bajada. `servicios/esfera_bienvenida.py` compara el estado actual con `UserProfile.esfera_estado_visto` y arma el saludo («Buenas tardes, Ana») y el cambio («Tus finanzas siguen sanas», «mejoraron», «cambiaron de estado»). La marca de primera visita la pone `sesiones.py` al entrar. Como el estado visto se guarda en el perfil, la comparación vale aunque se entre desde otro aparato.

**En el computador.** `templatetags/esfera_salud.py` dibuja la esfera en la tarjeta de salud de la barra lateral con los mismos tramos de Inicio, calculados con `resumen_mes`.

## La voz de la esfera

Solo habla la voz de ElevenLabs. No hay respaldo en la voz del teléfono: si el audio no llega, la esfera lo dice en pantalla y no habla.

1. Al dibujar la pantalla, `{% voz_firmada %}` firma cada texto (la frase, el cambio de estado y el nombre) con `signing.dumps`, la sal `finanzas.voz` y el id del usuario. Si ElevenLabs no está configurado o la persona apagó la IA, el atributo queda vacío y la esfera no ofrece hablar.
2. Cuando la esfera se abre, `inicio-esfera.js` pide el audio por adelantado a `/inicio/voz/` con los textos firmados y el saludo según la hora del teléfono.
3. `views/voz.hablar` rechaza los textos sin firma, de otro usuario o con más de 24 horas. Solo acepta los saludos «Buenos días», «Buenas tardes» y «Buenas noches». Tiene un tope de 40 audios por hora por persona.
4. `voz.sintetizar` llama a la API de ElevenLabs y guarda el MP3 en la caché 6 horas, con una clave que incluye voz, modelo y texto. La misma frase no se paga dos veces.
5. Al tocar, el audio suena. Si todavía no llegó, el script reproduce un silencio generado en el navegador dentro del mismo toque, porque el iPhone solo deja sonar audio que arranca en un toque. Cuando el audio llega, suena en ese mismo reproductor.

La CSP agrega `media-src 'self' blob:` para reproducir el audio.

## Medición en las páginas públicas

`marketing.py` decide qué se carga en la portada, las páginas legales, entrar y registro. Dentro de la app no se carga nada. Cada proveedor se activa con su variable (ver [09](09-INSTALACION-Y-DESPLIEGUE.md#variables-de-entorno)). Plausible no usa cookies y carga siempre que esté configurado. Google Analytics y los píxeles de Meta, TikTok y X cargan solo si la persona acepta el aviso de cookies (`consentimiento.js`). La CSP abre el dominio de cada proveedor solo en esas páginas y solo si su variable está puesta.

Toda página HTML que no es pública lleva `X-Robots-Tag: noindex, nofollow`. `/robots.txt` y `/sitemap.xml` los arma `views/sistema.py`.

Al terminar el registro, la pantalla siguiente manda el evento de registro (`sign_up` en GA4, `CompleteRegistration` en Meta y TikTok, el evento de `X_EVENTO_REGISTRO` en X) una sola vez y solo con consentimiento, sin datos personales.

## Configuración por entorno

Todo sale de variables de entorno (`python-dotenv` en local). Las decisiones que dependen de ellas:

| Variable | Efecto |
| --- | --- |
| `DEBUG` | `True` solo en local. Con `False` se activan HTTPS obligatorio, cookies seguras con prefijo `__Host-`, HSTS de 1 año con *preload*, manifiesto de estáticos y el chequeo de `SECRET_KEY` |
| `SECRET_KEY` | Obligatoria fuera de `DEBUG` y de `collectstatic`. Si empieza con `django-insecure`, la app se niega a arrancar |
| `DATABASE_URL` | Postgres (`conn_max_age=600`, SSL si `DB_SSL` no es `0`). Sin ella, SQLite con WAL, `synchronous=NORMAL` y `busy_timeout=5000` |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Se les suma solo `RAILWAY_PUBLIC_DOMAIN`, y a los hosts además `healthcheck.railway.app` y `.railway.internal` |
| `PROXIES_CONFIABLES` | Cuántos proxies hay delante (1 en Railway, 0 en local). Decide qué IP se usa en los topes |
| `ENTORNO` | `staging` agrega `X-Robots-Tag: noindex`, muestra la franja de aviso y bloquea el correo salvo que `CORREO_EN_STAGING=1` |
| `ADMIN_URL` | Ruta del admin. Vacía, el admin no existe |
| `WEBAUTHN_RP_ID` | Dominio de las credenciales de Face ID. Por defecto, el host de la petición |
| `DOMINIO_CANONICO` | Host al que se redirige cualquier otro nombre. Si falta, se toma de `SITE_URL`. Apagado en local y en las pruebas |
| `SESION_MAXIMA_HORAS` | Duración máxima de una sesión desde que se entró, aunque se use a diario. Por defecto 168 (7 días) |
| `CSP_IMG_EXTRA` | Orígenes extra para `img-src`, separados por espacio |
| `LOG_DIR` | Si existe, suma un archivo rotativo `seguridad.log` (2 MB × 3) |

La lista completa y dónde se configura cada una está en [09 · Instalación y despliegue](09-INSTALACION-Y-DESPLIEGUE.md#variables-de-entorno).

## Límites de la arquitectura actual

- **Un solo proceso de negocio.** Todo corre dentro de la petición, sin colas. Las llamadas a la IA, a ElevenLabs y a Resend bloquean el hilo hasta 10 s (correo) o lo que tarde Anthropic. Con 2 × 4 hilos alcanza para el uso actual, pero con carga habría que pasarlas a una tarea en segundo plano.
- **Cálculos en Python sobre listas.** Muchas pantallas traen todos los objetos del usuario con `prefetch_related` y calculan en memoria. Es correcto y está probado que no hace consultas extra por fila, pero crece linealmente con el historial. El primer lugar donde se va a notar es `resumen_mes`, que recorre todas las compras en cuotas del usuario.
- **Vínculos por texto.** El egreso de una suscripción se encuentra por su descripción (`Suscripción: {nombre}`). Ver [13 · Deuda técnica](13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md).
