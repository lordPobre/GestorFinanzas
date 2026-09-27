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
| IA | API de Anthropic: `claude-sonnet-4-6` para el análisis y `claude-haiku-4-5` para el chat de ayuda |
| Acceso | Contraseña (Argon2), TOTP (`pyotp`), WebAuthn (`webauthn`) y Google OAuth/OIDC |
| Lectura de cartolas | `pypdf` 6 y `openpyxl` 3.1 |
| Servidor | gunicorn 23: 2 workers × 4 hilos, *timeout* de 60 s |
| Monitoreo | Sentry opcional (`SENTRY_DSN`), sin datos personales |
| Front-end | CSS propio (`finapp.css`), Chart.js 4 servido desde `static/vendor`, Font Awesome y las fuentes Manrope y JetBrains Mono servidas localmente |

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
    suscripciones.py  generación de cobros mensuales
    senales.py        invalidación de caché al cambiar datos
  cartolas/           lectores de extractos bancarios (ver 05)
  management/commands/  tareas programadas (ver 10)
  templates/finanzas/, templates/registration/
  templatetags/moneda.py  filtros de formato de dinero
  analisis.py         motor determinístico del diagnóstico
  ia.py               interpretación con Claude
  chat_ayuda.py       chat de la landing
  seguridad.py        topes de intentos y de peticiones
  middleware.py       CSP con nonce y registro de actividad
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
railway/respaldo.json servicio de respaldo programado
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
  → PoliticaContenidoMiddleware   genera el nonce; al salir, escribe la CSP
  → SessionMiddleware
  → WhiteNoiseMiddleware          /static/ se responde aquí y no llega a Django
  → CommonMiddleware
  → CsrfViewMiddleware
  → AuthenticationMiddleware
  → MessageMiddleware
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

## Configuración por entorno

Todo sale de variables de entorno (`python-dotenv` en local). Las decisiones que dependen de ellas:

| Variable | Efecto |
| --- | --- |
| `DEBUG` | `True` solo en local. Con `False` se activan HTTPS obligatorio, cookies seguras, HSTS de 1 año con *preload*, manifiesto de estáticos y el chequeo de `SECRET_KEY` |
| `SECRET_KEY` | Obligatoria fuera de `DEBUG` y de `collectstatic`. Si empieza con `django-insecure`, la app se niega a arrancar |
| `DATABASE_URL` | Postgres (`conn_max_age=600`, SSL si `DB_SSL` no es `0`). Sin ella, SQLite con WAL, `synchronous=NORMAL` y `busy_timeout=5000` |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Se les suma solo `RAILWAY_PUBLIC_DOMAIN`, y a los hosts además `healthcheck.railway.app` y `.railway.internal` |
| `PROXIES_CONFIABLES` | Cuántos proxies hay delante (1 en Railway, 0 en local). Decide qué IP se usa en los topes |
| `ENTORNO` | `staging` agrega `X-Robots-Tag: noindex`, muestra la franja de aviso y bloquea el correo salvo que `CORREO_EN_STAGING=1` |
| `ADMIN_URL` | Ruta del admin. Vacía, el admin no existe |
| `WEBAUTHN_RP_ID` | Dominio de las credenciales de Face ID. Por defecto, el host de la petición |
| `LOG_DIR` | Si existe, suma un archivo rotativo `seguridad.log` (2 MB × 3) |

La lista completa y dónde se configura cada una está en [09 · Instalación y despliegue](09-INSTALACION-Y-DESPLIEGUE.md#variables-de-entorno).

## Límites de la arquitectura actual

- **Un solo proceso de negocio.** Todo corre dentro de la petición, sin colas. Las llamadas a la IA y a Resend bloquean el hilo hasta 10 s (correo) o lo que tarde Anthropic. Con 2 × 4 hilos alcanza para el uso actual, pero con carga habría que pasarlas a una tarea en segundo plano.
- **Cálculos en Python sobre listas.** Muchas pantallas traen todos los objetos del usuario con `prefetch_related` y calculan en memoria. Es correcto y está probado que no hace consultas extra por fila, pero crece linealmente con el historial. El primer lugar donde se va a notar es `resumen_mes`, que recorre todas las compras en cuotas del usuario.
- **Vínculos por texto.** El egreso de una suscripción se encuentra por su descripción (`Suscripción: {nombre}`). Ver [13 · Deuda técnica](13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md).
