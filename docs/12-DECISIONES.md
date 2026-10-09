# 12 · Historial de decisiones

Las decisiones de diseño que explican por qué el código es como es, en orden cronológico. Cada una dice qué se decidió, por qué y cuándo convendría revisarla. Absorbe lo que estaba en `ARQUITECTURA.md`, `DECISION-CIFRADO.md`, `REVISION-CODIGO-2026-09.md`, `ACTUALIZAR-DJANGO-5.2.md`, `MIGRACION-POSTGRES.md`, `DESPLIEGUE-RAILWAY.md` y `GUIA-PENDIENTES-MANUALES.md`.

## Cronología

| Fecha | Hito |
| --- | --- |
| Hasta sep. 2026 | La app se llama **FinApp**. Corre en PythonAnywhere (cuenta gratuita) con SQLite, correo por API HTTP (el plan gratuito bloquea SMTP) y caché en memoria |
| 4 sep. 2026 | Primera documentación técnica |
| Sep. 2026 | Cambio de nombre a **Rekon** |
| 15 sep. 2026 | Incidente: claves de R2 en el historial de git. Se rotan (ver `docs/BRECHAS.md`) |
| 16–19 sep. 2026 | Lotes de cumplimiento de la Ley 21.719: política 1.0 y 1.1, consentimiento en el alta, descarga y borrado de datos, inactividad, registro de tratamientos. Se elimina `cifrado.py` |
| Sep. 2026 | **Salida de PythonAnywhere a Railway con Postgres**, para tener dominio propio sin pagar el plan Developer (USD 10/mes desde enero de 2026) y una base real. Migración con `dumpdata`/`loaddata` |
| 23–25 sep. 2026 | DPA con los cuatro proveedores, aviso por correo de la política 1.2 (enviado el 24), SPF/DKIM/DMARC, UptimeRobot, alertas de Sentry, primer simulacro de restauración (9 usuarios, 64 movimientos), dependencias con hash |
| 25 sep. 2026 | Revisión de código y **lotes 1 a 12**: `views.py` y `models.py` pasan a paquetes, `servicios/`, pruebas por tema, URLs con un solo estilo y redirecciones 308, scripts a `static/js/pantallas/`, estilos a clases y colores a variables, sin comentarios en el código, Python 3.13, acceso corto en el teléfono |
| Sep. 2026 | Django 5.2 LTS y `STORAGES` (los estáticos vuelven a servirse con hash y comprimidos) |
| 27 sep. 2026 | Landing pública, preguntas frecuentes, chat de ayuda con IA, rediseño de privacidad y términos. Cambio de nombre a **Fintora** |
| 29–30 sep. 2026 | Rediseño en vidrio (lotes 13 a 27). Inicio con botones Gastos, Ingresos y Puedes gastar; editar y borrar movimientos; Plan ordenado por pasos con **simulador de cuotas**; aviso de **ritmo de gasto**; **suscripciones sugeridas**; Face ID solo en celular y tablet; nueva lista de movimientos |
| Oct. 2026 | Lotes 29 a 39: franja de la barra de estado solo al hacer scroll, Me deben siempre en verde, teléfono de la portada con cuatro pantallas, correos oscuros como la app, íconos de línea en el acceso |
| Oct. 2026 | Lotes 40 a 45: **la esfera** en Inicio, Cuotas, Me deben, Suscripciones y Metas, con voz del navegador, en la portada y en el tour |
| Oct. 2026 | Lotes 46 a 49: páginas de error propias, SSL Labs **A+** y Observatory **A**, página `/seguridad/`, `security.txt` y Actividad de la cuenta |
| 1 oct. 2026 | Lotes 50 a 55: proyección de ahorro y depósito a plazo en el Plan, saludo con cielo animado, SEO, analítica y píxeles solo en las páginas públicas (**política 1.4**) y evento de registro |
| Oct. 2026 | Lotes 56 a 76: auditoría visual pantalla por pantalla, con una prueba por pantalla; esfera en la barra lateral del computador |
| Oct. 2026 | Lotes 77 a 80: **auditoría de seguridad**, en cuatro partes (A a D). Migración 0119 |
| Oct. 2026 | Lotes 81 a 83: la esfera saluda al entrar (migración 0120) y habla solo con **ElevenLabs**; propiedad intelectual en los términos y en la portada |
| Oct. 2026 | Lotes 86 y 87: **Debo**, topes por categoría y **recordatorios en el teléfono** (migración 0121), con sus pruebas |
| Oct. 2026 | Lote 88: política **1.6** y su aviso por correo con `avisar_politica` (migración 0122) |
| Oct. 2026 | Lotes 89 y 90: franja de la política en el Inicio; la cuenta se crea al confirmar el correo (migración 0123), estilos con nonce, medición de respuestas y pruebas de JavaScript |

## Decisiones vigentes

### D-01 · Monolito Django con plantillas del servidor, sin SPA

**Qué:** HTML renderizado en el servidor, un JavaScript pequeño por pantalla, sin API pública ni *framework* de front-end.

**Por qué:** es un solo desarrollador, las pantallas son formularios y listas, y así el CSRF, la sesión y la CSP funcionan sin configuración extra. No hay paso de compilación que mantener.

**Revisar si:** aparece una app nativa o un cliente que necesite una API.

### D-02 · Cobros mensuales identificados por `periodo = año*100 + mes`

**Qué:** cada cuota o suscripción pagada es una fila (`PagoCuota`, `PagoServicio`) con su periodo, y una restricción única impide pagar dos veces el mismo mes.

**Por qué:** reemplazó un contador de cuotas pagadas que no sabía *qué* mes se había pagado. Permite pagar atrasado, anular un mes concreto y calcular el arrastre. Es la pieza más sólida del modelo: no tocarla.

### D-03 · Se paga siempre el periodo pendiente más antiguo

**Qué:** el botón “pagar” de una cuota paga el mes pendiente más viejo, no el actual.

**Por qué:** coincide con cómo cobra el banco y evita estados raros, como un mes futuro pagado con uno pasado pendiente.

### D-04 · El egreso de la cuota se excluye de los gastos del mes

**Qué:** al pagar una cuota se crea un egreso con `es_cuota=True`, que `resumen_mes` no suma en `gastos`. La cuota ya cuenta en “cuotas del mes”.

**Por qué:** el movimiento tiene que existir para el historial y las exportaciones, sin contarse dos veces.

### D-05 · Vistas delgadas, cálculos en `servicios/`

**Qué:** una vista lee la petición y arma la respuesta. Un servicio recibe usuario y fechas y devuelve datos.

**Por qué:** `views.py` había llegado a unas 2500 líneas, con `dashboard()` de más de 300. Separarlo permitió probar los cálculos y reusarlos en los comandos programados.

**Descartado:** Repository, CQRS y Event Sourcing. Agregan capas sin resolver un problema que exista hoy.

### D-06 · CSP propia con nonce, sin `django-csp`

**Qué:** `PoliticaContenidoMiddleware` genera un nonce por respuesta y escribe la política.

**Por qué:** son 30 líneas que se entienden completas y la política es estricta: `connect-src 'self'` y ningún origen externo. Cambiarla por una librería no resuelve nada.

### D-07 · Nada de terceros en el navegador

**Qué:** fuentes, íconos y Chart.js servidos desde `static/vendor`. Google, Anthropic y Resend se llaman desde el servidor.

**Por qué:** privacidad (ningún tercero ve qué pantallas abre una persona) y una CSP cerrada. Hay pruebas que lo verifican.

**Desde el lote 52** vale para la app. Las páginas públicas pueden medir visitas (ver D-23).

### D-08 · No cifrar las descripciones a nivel de campo

**Qué:** `cifrado.py` (un `TextField` cifrado con Fernet) se eliminó el 19 de septiembre de 2026 sin haberse aplicado nunca.

**Por qué:**

1. La app filtra por esos textos (`descripcion__startswith='Suscripción: …'`). Con Fernet, el mismo texto cifra distinto cada vez y el filtro devolvería cero filas **sin error**.
2. La clave viviría en el mismo servicio que la base: quien accede a una suele acceder a la otra.
3. Perder o cambiar la clave deja todo ilegible para siempre.
4. La política no promete cifrado a nivel de campo.

**Qué protege entonces:** el cifrado en reposo del Postgres gestionado, que cubre todo, incluidos los montos, sin perder `Sum()`, los filtros ni los índices.

**Para reabrirla hace falta:** una migración que cifre lo existente con la clave respaldada aparte, y aceptar que no se podrá buscar en esos campos. El primer requisito, la FK `Transaccion → Suscripcion` en lugar del vínculo por texto, ya existe (D1).

### D-09 · Caché en la base, no en memoria ni en Redis

**Qué:** `DatabaseCache` en la tabla `cache_finapp`, creada con `createcachetable` en cada despliegue.

**Por qué:** con varios workers de gunicorn, `LocMemCache` hace que cada proceso lleve su propia cuenta y el tope se multiplica por la cantidad de workers. **Desde el lote 78** los contadores tienen su propia tabla (D-22): la caché queda para lo que se puede perder. La base ya existe, así que Redis sería un servicio más que pagar y mantener.

### D-10 · Topes de acceso por usuario, por cuenta y por IP a la vez

**Qué:** tres contadores (ver [06 · Seguridad](06-SEGURIDAD.md#topes-de-intentos-seguridadpy)).

**Por qué:** si fuera solo por usuario, cualquiera podría bloquear a otra persona fallando a propósito con su nombre. Si fuera solo por IP, una red compartida quedaría bloqueada entera, y un atacante con muchas IP no tendría límite contra una cuenta.

### D-11 · Correo por la API HTTP de Resend

**Qué:** `correo.py` usa `urllib` contra `api.resend.com`, sin el backend SMTP de Django.

**Por qué:** nació de la restricción de PythonAnywhere, que bloquea SMTP. Se mantiene porque funciona, no depende de puertos y da un id por envío. Hubo soporte para Mailgun y se quitó en el lote 1.

**Detalle:** User-Agent propio, porque Cloudflare, que está delante de Resend, rechaza `Python-urllib`.

### D-12 · Google por redirección, sin su script

**Qué:** OAuth 2.0 / OIDC a mano (unas 200 líneas en `google_login.py`).

**Por qué:** el botón oficial obliga a abrir `script-src`, `connect-src` y `frame-src` a Google. La redirección hace lo mismo con un enlace normal.

### D-13 · Cartolas: el signo sale de la cadena de saldos

**Qué:** el motor universal deduce si entró o salió plata por la diferencia entre saldos consecutivos, y se niega a leer si menos del 85 % de las filas cuadran.

**Por qué:** los bancos escriben los cargos de formas muy distintas. El saldo es la única verdad que todos imprimen. Preferimos no leer antes que leer mal.

### D-14 · La cartola no se guarda

**Qué:** el archivo se procesa en memoria y se descarta. Lo leído espera en la sesión hasta confirmar.

**Por qué:** es el documento más sensible que toca la app. La política declara, desde la versión 1.3, que lo leído queda en la sesión hasta 8 horas.

### D-15 · IA opcional, con agregados y con respaldo propio

**Qué:** el diagnóstico lo calcula `analisis.py`. La IA solo lo redacta y recibe números. Sin clave o con la opción apagada, la pantalla funciona igual.

**Por qué:** que la app no dependa de un proveedor externo para su función central, y no enviar textos personales a terceros.

### D-16 · Rutas nuevas con redirecciones 308 desde las antiguas

**Qué:** en el lote 9 las URL pasaron a un solo estilo (`/recurso/<id>/acción/`). Las viejas responden 308.

**Por qué:** 308 conserva el método y el cuerpo. Un formulario que quedó abierto en un teléfono con la URL vieja sigue funcionando.

### D-17 · Nombres internos `finapp` que no se cambian

Se cambió el nombre visible (FinApp → Rekon → Fintora), pero estos identificadores se dejaron a propósito:

| Identificador | Por qué no se cambia |
| --- | --- |
| `finapp.css`, `finapp.js` | Renombrarlos obliga a tocar cada `{% static %}` y no gana nada |
| `window.finappOpen`, `window.finappTour`, `__finappJsCargado` | Internos e invisibles |
| Claves `finapp.*` de `localStorage` | Son estado del usuario. Cambiarlas hace reaparecer lo que cada persona ocultó |
| Prefijo `finapp-` de los respaldos SQLite | La rotación los busca por ese prefijo |
| Tabla de caché `cache_finapp` | Habría que recrearla, y los contadores vigentes se perderían |
| Caché `finapp-estaticos-*` del *service worker* | El paso de limpieza borra por ese prefijo |

El prefijo de los respaldos de Postgres y los nombres del CI ya pasaron a `fintora`. Era seguro porque la rotación usa la carpeta `postgres/`.

### D-18 · Sin comentarios en el código

**Qué:** el código no lleva comentarios ni *docstrings* (lote 5). Las explicaciones viven en esta documentación, en los nombres y en las pruebas.

**Por qué:** es preferencia del proyecto (`CLAUDE.md`). La contrapartida es que esta documentación tiene que mantenerse al día: es el único lugar donde está el porqué.

### D-19 · Migraciones sin renumerar

El salto de `0016` a `0100` es inofensivo y renumerar rompería las bases existentes. Tampoco se separan los modelos en otra app: exigiría migraciones entre apps a cambio de poco.

### D-20 · La esfera habla solo con ElevenLabs

**Qué:** el audio lo genera ElevenLabs en el servidor. No hay respaldo en la voz del teléfono: si el audio no llega, la esfera lo avisa en pantalla.

**Por qué:** la voz del navegador cambia según el aparato, el idioma instalado y el sistema. Mezclarla con la de ElevenLabs hacía que la misma app hablara con voces distintas. Una sola voz se reconoce como la de Fintora.

**Costo:** sin ElevenLabs configurado, o con la IA apagada, la esfera no habla. El audio se pide al abrir la esfera para que suene en el mismo toque, que es lo que exige el iPhone.

**Revisar si:** el gasto en créditos se vuelve relevante. La caché de 6 horas ya evita pagar dos veces la misma frase.

### D-21 · Textos firmados para la voz

**Qué:** la vista de voz no recibe texto libre. Solo acepta textos que el servidor firmó para esa persona al dibujar la pantalla, con menos de 24 horas. El nombre del saludo viaja igual.

**Por qué:** una ruta que lee en voz alta lo que le manden sirve para gastar los créditos o para que ElevenLabs lea cualquier cosa con la marca de Fintora. Firmar evita guardar los textos y no exige estado extra.

### D-22 · Contadores en una tabla propia

**Qué:** los intentos fallidos y los topes de `limitar` viven en `Contador`, con sumas dentro de una transacción que bloquea la fila. Las IPv6 se agrupan por /64.

**Por qué:** la caché en la base leía, sumaba y escribía en tres pasos: dos workers podían perder un intento. Con una dirección IPv6 nueva por petición, el tope por IP no servía.

### D-23 · Medición solo en las páginas públicas y con consentimiento

**Qué:** Plausible (sin cookies) y, con el aviso de cookies aceptado, Google Analytics y los píxeles de Meta, TikTok y X, solo en la portada, las legales, entrar y registro. Cada uno se activa con su variable. Dentro de la app no se carga nada.

**Por qué:** para crecer hace falta medir de dónde llega la gente, pero la app guarda datos financieros: ningún tercero tiene que ver qué pantallas abre alguien con sesión.

### D-24 · Cookies `__Host-` y un solo dominio

**Qué:** las cookies de sesión y CSRF llevan el prefijo `__Host-`, y toda visita por otro nombre se redirige a `DOMINIO_CANONICO`.

**Por qué:** el prefijo impide que un subdominio fije o pise la sesión. Un solo dominio evita sesiones partidas y que el sitio se indexe con el nombre de Railway.

### D-25 · El registro no revela qué correos tienen cuenta

**Qué:** si el correo ya existe, la página responde lo mismo y el aviso llega por correo a esa dirección.

**Por qué:** sin esto, el registro servía para averiguar si alguien usa Fintora. Queda la diferencia de destino (D14 en [13](13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md)).

### D-26 · Web Push propio, sin `pywebpush`

**Qué:** `push.py` cifra (RFC 8291) y firma (VAPID, RFC 8292) con `cryptography`, que ya estaba, y envía con `urllib`.

**Por qué:** son unas 170 líneas que se leen completas y no suman dependencias que auditar. Sigue la línea de D-11 y D-12. `test_recordatorios.py` descifra lo enviado como lo haría el aparato y verifica la firma.

**Revisar si:** algún servicio de avisos cambia el formato o aparece un error que una librería mantenida ya resolvió.

### D-27 · Debo usa los mismos modelos que Me deben

**Qué:** `Persona.lado` separa los dos lados. Préstamos, cuotas y abonos son los mismos modelos.

**Por qué:** las dos listas se comportan igual y así no hay dos copias del mismo cálculo. Lo que cambia (WhatsApp, «Por pagar», «Puedes gastar») se decide con el lado. Las cartolas siguen anotando solo en Me deben.

### D-28 · Los topes avisan, no bloquean

**Qué:** al anotar un gasto que llega al 80 % o pasa el tope, aparece el aviso antes de guardar, pero se puede guardar igual.

**Por qué:** el gasto ya ocurrió. Si la app no lo deja anotar, la cifra del mes queda mal.

### D-29 · La cuenta se crea al confirmar el correo

**Qué:** el registro guarda los datos en `AltaPendiente` y crea el `User` recién cuando se abre el enlace y se toca «Crear mi cuenta».

**Por qué:** cierra D14. Un correo nuevo y uno repetido reciben la misma respuesta, así que el registro no sirve para averiguar quién usa Fintora. De paso, toda cuenta nueva tiene el correo confirmado.

**Detalle:** la base guarda el SHA-256 del enlace, no el enlace, y la contraseña ya con hash. El enlace no va firmado porque llevaría el hash de la contraseña dentro del correo.

### D-30 · Estilos: nonce para `<style>`, atributos permitidos

**Qué:** `style-src-elem` pide el nonce y `style-src-attr` mantiene `'unsafe-inline'`.

**Por qué:** una etiqueta `<style>` inyectada puede leer datos de la página con selectores; un atributo `style` no puede. Quitar los atributos exige reescribir casi todas las plantillas. Así se cierra lo más riesgoso sin tocarlas.

**Revisar si:** se reescriben las plantillas para sacar los `style=`. Entonces `style-src-attr` puede pasar a `'none'` (hecho en el lote 105).

**Lote 92:** el acceso y las legales ya no tienen `style=` y pasan a `style-src-attr 'none'`. La lista de rutas está en `RUTAS_SIN_ESTILO_EN_LINEA`, en `middleware.py`. Las demás pantallas siguen con `'unsafe-inline'` hasta que se limpien.

**Lote 96:** la plantilla base, Inicio, Mi perfil, anotar y editar un movimiento y la cuenta por pagar quedan sin `style=`. Sus estilos pasan a `static/css/sesion.css`, que carga después de la hoja de cada pantalla. Las reglas que reemplazan un atributo llevan `!important`, porque el atributo ganaba a cualquier selector y así se ven igual; las excepciones son lo que el JavaScript cambia en línea (`#avisoMonto`, `#montoView`, `#panelSeguridad`) y el ancho de los modales, que en el teléfono debe seguir cediendo a `max-width: none !important`. Donde `tema-vidrio.css` agrandaba los textos con `[style*="font-size:…"]`, la clase nueva ya trae el tamaño final. Lo que depende de los datos usa atributos `data-` que lee `estilos.js`, y solo acepta números y colores `#hex`. Estas rutas pasan a `'none'` solo con sesión, porque la ruta de Inicio sin sesión es la portada.

**Lote 103:** Cuotas, Me deben y Debo, Suscripciones y Metas, con sus formularios para crear y editar, quedan sin `style=` y sus rutas se suman a `RUTAS_SIN_ESTILO_CON_SESION`, con las mismas reglas del lote 96. Los cuadros y campos que el JavaScript muestra u oculta (`#cajaPlan`, `#cajaCuota`, `#cajaPr`, `#campoCuotas`, `#campoCuotasPersona`, `#campoCuotasPr`) parten ocultos desde `sesion.css`, sin `!important`, para que el valor en línea del script gane. Por eso `prestamos.js` los muestra con `display: block`: antes borraba el valor y volvía a mandar el atributo, que ya no existe. Las columnas de las cuotas van en `data-columnas`.

**Lote 104:** Categorías, Estadísticas, Análisis, el Plan, la cartola y las pantallas de seguridad del perfil (dos pasos, códigos de respaldo, Face ID, sesiones, actividad y eliminar la cuenta) quedan sin `style=`, y sus rutas se suman a `RUTAS_SIN_ESTILO_CON_SESION`. Con sesión, solo la bienvenida y la encuesta siguen con `'unsafe-inline'`. Lo que el JavaScript cambia en línea parte de reglas sin `!important`: el borde de los colores y el fondo de los íconos al crear o editar una categoría (`.swatch`, `.icono-op` y su clase `on`), el botón «Listo» de los códigos de respaldo (`#btnListo`) y los bloques de la explicación con IA (`#cajaIA`, `#iaContenido`, `#iaBloque…`). Los íconos que los scripts escriben con `innerHTML` usan clases, y el color de un ícono va en `data-color`.

**Lote 105:** la portada, la encuesta y sus resultados, y la bienvenida quedan sin `style=`. Con eso ninguna pantalla los usa y `style-src-attr` pasa a `'none'` en toda respuesta que no sea un error, con o sin sesión: las listas `RUTAS_SIN_ESTILO_EN_LINEA` y `RUTAS_SIN_ESTILO_CON_SESION` se quitan. La portada no carga `sesion.css` ni `tema-vidrio.css`, así que sus clases van en `static/css/portada.css`, con los tamaños tal como estaban; la bienvenida carga `sesion.css`. La escala de la encuesta pasa de `style="--cols:…"` a las clases `cols-5` y `cols-11`, y la regla de `finapp.css` que buscaba `[style*="--cols:11"]` usa la clase. Los resultados de la encuesta traen colores como `var(--text-muted)` o `rgba(…)`, por eso `estilos.js` los acepta en `data-fondo`, `data-tinta` y `data-color`, solo con esa forma. Para que nada nuevo traiga atributos `style`, la prueba revisa todas las plantillas de pantalla y todos los scripts, no una lista.

### D-31 · Medir antes de optimizar

**Qué:** `RendimientoMiddleware` anota las respuestas lentas y `resumen_mes` se calcula una vez por petición.

**Por qué:** D5 y D8 piden cambiar la plantilla base y las consultas del mes. Antes conviene saber qué pantallas son lentas de verdad. Recordar `resumen_mes` dentro de la petición ya evita repetirlo entre el Inicio y la barra lateral, y se olvida apenas cambia un movimiento, una cuota, una suscripción o un préstamo.

## Procedimientos históricos

### Migración de SQLite a Postgres (septiembre de 2026)

Se hizo con `dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission -e sessions`, luego `migrate` en la base nueva y `loaddata` desde la máquina local contra la URL pública del Postgres de Railway. El volcado definitivo se hizo con la app vieja apagada, y el archivo intermedio (la base entera en texto plano) se borró al terminar. Si hubiera que repetirlo, sirve el mismo método.

### Paso a Django 5.2

`STATICFILES_STORAGE` dejó de existir en Django 5.1 y producción la ignoraba sin avisar, así que los estáticos salían sin hash y sin comprimir. Con `STORAGES` WhiteNoise volvió a hacerlo. La forma de verificarlo: en las herramientas del navegador, los `.css` y `.js` tienen un hash en el nombre y responden con `Content-Encoding: br` o `gzip`.
