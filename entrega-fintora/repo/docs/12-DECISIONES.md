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

**Por qué:** con varios workers de gunicorn, `LocMemCache` hace que cada proceso lleve su propia cuenta de intentos fallidos y el tope se multiplica por la cantidad de workers. La base ya existe, así que Redis sería un servicio más que pagar y mantener.

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

## Procedimientos históricos

### Migración de SQLite a Postgres (septiembre de 2026)

Se hizo con `dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission -e sessions`, luego `migrate` en la base nueva y `loaddata` desde la máquina local contra la URL pública del Postgres de Railway. El volcado definitivo se hizo con la app vieja apagada, y el archivo intermedio (la base entera en texto plano) se borró al terminar. Si hubiera que repetirlo, sirve el mismo método.

### Paso a Django 5.2

`STATICFILES_STORAGE` dejó de existir en Django 5.1 y producción la ignoraba sin avisar, así que los estáticos salían sin hash y sin comprimir. Con `STORAGES` WhiteNoise volvió a hacerlo. La forma de verificarlo: en las herramientas del navegador, los `.css` y `.js` tienen un hash en el nombre y responden con `Content-Encoding: br` o `gzip`.
