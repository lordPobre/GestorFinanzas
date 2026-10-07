# 06 · Seguridad

Este capítulo describe los controles que están en el código y cómo verificarlos. La respuesta ante un incidente está en [10 · Operación](10-OPERACION.md#incidentes-de-seguridad). Lo que falta está en [13 · Deuda técnica](13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md#seguridad).

## Modelo de amenazas

La app guarda la vida financiera de personas reales: sus ingresos, sus deudas y a quién le prestaron plata. No mueve dinero ni se conecta a bancos, así que un atacante no puede robar fondos por aquí. Lo que sí puede hacer es:

1. **Entrar a la cuenta de otra persona**: adivinando la contraseña, con una sesión robada o aprovechando la vinculación con Google.
2. **Leer los datos de otra persona desde su propia cuenta**, cambiando un id en la URL.
3. **Ejecutar código en el navegador de la víctima (XSS)** y leer sus datos desde ahí.
4. **Gastar la cuota de la IA o del correo** con peticiones automáticas.
5. **Acceder a la infraestructura** (base, respaldos, R2) con una credencial filtrada.

## 1. Acceso a la cuenta

### Contraseñas

- Hash con **Argon2** (`PASSWORD_HASHERS`). PBKDF2 y BCrypt quedan solo para leer hashes antiguos: Django los rehace con Argon2 la próxima vez que la persona entra.
- Mínimo 8 caracteres, distinta del nombre de usuario, que no sea de las comunes ni solo números.
- Cambiarla en el perfil exige la actual y mantiene la sesión abierta (`update_session_auth_hash`).

### Topes de intentos (`seguridad.py`)

Desde el lote 78 se guardan en la tabla `Contador`, compartida por todos los workers. Cada suma corre en una transacción que bloquea la fila, así que dos peticiones a la vez no pierden intentos. Las direcciones IPv6 se agrupan por red /64: cambiar de dirección dentro de la misma red no reinicia la cuenta.

| Contador | Tope | Bloqueo | Para qué |
| --- | --- | --- | --- |
| Usuario escrito + IP | 5 fallos | 15 min | El caso normal |
| Por cuenta | 20 fallos/h | Hasta que vence la hora | Alguien que prueba desde muchas IP contra una cuenta |
| Por IP | 50 fallos/h | Hasta que vence la hora | Una IP que prueba muchas cuentas |
| 2FA (`2fa:{id}` + IP) | 5 códigos | 15 min | Adivinar el código de 6 dígitos |
| Face ID por IP | 5 fallos | 15 min | Credenciales inventadas |
| Contraseña con la sesión iniciada | 5 fallos | 15 min | Cambiar la contraseña, desactivar 2FA o regenerar códigos con una sesión robada |

Mientras el bloqueo esté activo, ni siquiera la contraseña correcta entra. Al entrar bien se limpian el contador del par y el de la cuenta, pero no el de la IP. Así una red que prueba muchas cuentas no se “lava” acertando una. `test_acceso_y_montos.py` cubre los cinco casos.

**La IP real.** `_ip()` no confía en `X-Forwarded-For` tal como viene, porque cualquiera puede escribirlo. Toma el tramo número `PROXIES_CONFIABLES` contando desde el final (en Railway, el último), que es el que agregó el proxy propio. Con `PROXIES_CONFIABLES=0` usa `REMOTE_ADDR`.

### Verificación en dos pasos (TOTP)

- El secreto se genera con `pyotp.random_base32()`. El QR se dibuja como SVG en el servidor, así el secreto no viaja a ningún servicio externo.
- Para activarla hay que ingresar un código válido. En ese momento se generan **8 códigos de respaldo** que se muestran una sola vez y se guardan con hash.
- El código se acepta con una ventana de ±30 s. **El mismo código no sirve dos veces**: se guarda el último usado.
- Desactivar o regenerar los códigos exige la contraseña.
- La recuperación de contraseña también exige el código si la cuenta tiene 2FA. Robar el correo no alcanza.
- Con Google o con Face ID también se pasa por el segundo paso si está activo.
- El código hay que escribirlo dentro de 5 minutos desde la contraseña. Pasado ese tiempo, se vuelve a empezar.
- **El admin la exige.** Una cuenta de personal sin la verificación activa no entra al panel: se la manda a activarla. Se revisa en cada página del admin.

### Face ID o huella (WebAuthn / passkeys)

- Clave residente y verificación de la persona obligatorias (`ResidentKeyRequirement.REQUIRED`, `UserVerificationRequirement.REQUIRED`).
- Vincular un dispositivo exige la contraseña actual, si la cuenta tiene una.
- El *user handle* es `HMAC-SHA256(SECRET_KEY, "passkey:{id}")`: no expone el id interno. Al entrar se compara con `compare_digest`.
- Se valida el desafío (de un solo uso, guardado en la sesión), el origen, el `rp_id`, la firma y el contador. Si el contador retrocede, el dispositivo podría estar clonado y se rechaza.
- Se guarda solo la clave pública. **Ningún dato biométrico llega al servidor.**
- Rotar `SECRET_KEY` cambia el *user handle*: las personas tendrían que volver a vincular sus dispositivos.

### Acceso con Google

- Flujo de redirección OAuth 2.0 / OpenID Connect, sin cargar el script de Google. Así la CSP no se abre a otro dominio.
- `state` aleatorio de 32 caracteres en la sesión, destino (`next`) solo local, `prompt=select_account`.
- **PKCE (S256) y `nonce`.** Un código robado no sirve sin el verificador guardado en la sesión, y un `id_token` emitido para otra sesión se rechaza.
- El código se canjea en el endpoint de token de Google con el `client_secret`, por TLS. La firma del `id_token` no se verifica, lo que OIDC Core 3.1.3.7 permite cuando el token llega directo del endpoint de token. Sí se validan `iss`, `aud`, `exp`, `sub` y `email_verified`.
- Primero se busca la cuenta por `google_sub`. Si no existe, se busca por correo; si tampoco existe, se crea una cuenta sin contraseña utilizable.
- Solo se vincula por correo si la cuenta existente lo tiene confirmado. Si no, pide entrar con usuario y contraseña, o recuperarla, y confirmar el correo desde el perfil.

### Recuperación de contraseña

- 3 solicitudes por IP cada 15 minutos y 3 correos por hora por dirección. Pasado el tope de la dirección, la página responde lo mismo pero no manda nada.
- La respuesta es siempre “te mandamos un correo”, exista o no la cuenta. No sirve para averiguar quién está registrado.
- El enlace usa el generador de tokens de Django, vale 1 hora y deja de servir en cuanto la contraseña cambia. Abrir enlaces de recuperación o de confirmación tiene un tope de 20 por hora por IP.

### Registro

Desde el lote 90 la cuenta se crea recién al abrir el enlace del correo. Un registro nuevo y uno con un correo que ya tiene cuenta responden igual: vuelven al acceso con «Te mandamos un correo». Al nuevo le llega el enlace para crear la cuenta; al repetido, el aviso con los enlaces para entrar o recuperar la contraseña (2 al día como máximo). Desde afuera no se puede saber cuál de los dos fue. El enlace es un secreto de 32 bytes; la base guarda solo su SHA-256 y la contraseña ya con hash. Abrirlo muestra un botón, para que el antivirus del correo no cree la cuenta al revisar el enlace.

### Cambio de correo

Pide la contraseña actual, o el código de la app si la cuenta entra solo con Google y tiene 2FA. El correo nuevo queda en `email_pendiente` y recibe un enlace válido 48 horas. La dirección anterior recibe un aviso al momento. Al confirmar, cambia el correo y se cierran las demás sesiones. Un pedido nuevo invalida el enlace anterior.

### Sesiones

- Vencen a las 8 horas sin uso y se renuevan en cada petición (`SESSION_SAVE_EVERY_REQUEST`). Además, `SesionAbsolutaMiddleware` las cierra a los 7 días desde que se entró, aunque se usen a diario (`SESION_MAXIMA_HORAS`, por defecto 168). Queda el evento `sesion_vencida`.
- En producción las cookies son `Secure`, `HttpOnly` y `SameSite=Lax`, y se llaman `__Host-sessionid` y `__Host-csrftoken`: el navegador solo las acepta por HTTPS, sin dominio y en `/`, así que un subdominio no puede pisarlas.
- **Aparato conocido.** Cada aparato recibe la cookie firmada `fintora_aparato`. Si se entra desde uno nuevo y la cuenta ya tenía otro, llega un aviso por correo y queda en *Perfil → Actividad de la cuenta*.
- **Sin caché.** `SinCacheMiddleware` pone `Cache-Control: no-store, private` en toda respuesta con sesión. Salir responde `Clear-Site-Data: "cache"`, y `base-2.js` recarga la página si Safari la saca de su memoria de Atrás. Después de salir, Atrás lleva al acceso.
- Cada sesión abierta queda registrada con IP y navegador (`SesionActiva`). En *Perfil → Sesiones* se puede cerrar cualquiera o todas las demás, y eso borra la sesión de Django.
- `login()` rota la clave de sesión, lo que evita la fijación de sesión.

## 2. Aislamiento entre usuarios

- Cada consulta filtra por `usuario=request.user`. Un id ajeno da **404**.
- `test_vistas.py` crea dos usuarios con datos de todos los tipos y prueba que ninguno alcance, modifique o liste lo del otro.
- La descarga de datos, el borrado y la encuesta también están probados contra la cuenta de al lado.
- **Prueba automática de todas las rutas con id** (`test_seguridad_80.py`): entra como otro usuario, prueba GET y POST con los ids de Ana y comprueba que nada responda 200 ni cambie. Si se agrega una ruta con id y no se suma a `DATOS`, la prueba falla.
- Las fotos se sirven desde un almacenamiento privado con URL firmada de 6 horas. No hay listado público. `test_terceros_fotos_cache.py` lo verifica.
- El admin no existe si `ADMIN_URL` está vacía. Si existe, está en una ruta no adivinable y el login es el de la app. Una cuenta sin permiso recibe 404 y queda un evento `admin_denegado`.

## 3. XSS y contenido de terceros

**Content-Security-Policy** en cada respuesta HTML (`middleware.PoliticaContenidoMiddleware`):

```
default-src 'self';
script-src 'self' 'nonce-<aleatorio por respuesta>';
style-src 'self' 'unsafe-inline'; style-src-elem 'self' 'nonce-…'; style-src-attr 'unsafe-inline' (o 'none' en acceso y legales);
font-src 'self';
img-src 'self' data: blob: <host de R2> <CSP_IMG_EXTRA>;
connect-src 'self';
media-src 'self' blob:;
frame-src 'none'; object-src 'none';
form-action 'self'; frame-ancestors 'none'; base-uri 'self';
upgrade-insecure-requests
```

- Todo `<script>` lleva `nonce="{{ csp_nonce }}"`. Si se cuela una inyección, el navegador no la ejecuta. Hay pruebas que recorren la landing y las páginas legales buscando scripts sin nonce.
- Desde el lote 90, una etiqueta `<style>` solo se aplica si trae el nonce de la respuesta (`style-src-elem`). Desde el lote 92, en el acceso (entrar, verificación en dos pasos, registro, crear la cuenta, confirmar el correo, recuperar y restablecer) y en las legales (privacidad, términos y seguridad) tampoco se aplican los atributos `style` (`style-src-attr 'none'`): sus estilos están en `static/css/acceso.css` y en las hojas que ya tenían. En el resto de la app los atributos siguen permitidos porque las plantillas los usan; eso no permite ejecutar código. Si la respuesta es un error (400 o más), la página usa la regla general. `style-src 'self' 'unsafe-inline'` queda solo para navegadores que no conocen las dos directivas nuevas. Si en la portada hay píxeles de medición activos, no se agregan las dos directivas, porque esos scripts pueden insertar estilos. Las páginas de error usan `static/css/errores.css`, y `test_csp_estilos.py` revisa que ninguna plantilla de pantalla traiga un bloque `<style>`.
- `connect-src 'self'`: el JavaScript solo puede hablar con la propia app. Las llamadas a Anthropic, ElevenLabs y Resend salen del servidor, nunca del navegador.
- `media-src blob:` es para reproducir el audio de la esfera, que llega como archivo y se reproduce desde la memoria.
- Las fuentes, los íconos y Chart.js se sirven desde `static/vendor`. **Dentro de la app el navegador no le pide nada a ningún tercero**, lo que prueba `test_terceros_fotos_cache.py`. En las páginas públicas, la CSP suma el dominio de cada proveedor de medición solo si su variable está puesta (ver [02](02-ARQUITECTURA.md#medición-en-las-páginas-públicas)).
- `Permissions-Policy` bloquea cámara, micrófono, ubicación, pagos y USB.
- Además: `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin` y `Cross-Origin-Opener-Policy: same-origin`.
- **Redirecciones abiertas.** Todo `next` pasa por `redirecciones.py`, que solo acepta rutas del propio dominio. `/\malo.com`, que el navegador trata como `//malo.com`, se rechaza.
- **Exportaciones.** Una descripción que empieza con `=`, `+`, `-` o `@` sale en el CSV con un `'` delante y en el Excel como texto, para que no se ejecute como fórmula.
- **Archivos subidos.** Antes de abrir un `.xlsx` se revisa el zip: más de 40 MB descomprimidos, más de 500 entradas o una compresión anómala se rechazan. openpyxl usa `defusedxml`. Toda foto de perfil se vuelve a guardar como JPEG de máximo 1024 px, sin EXIF y con la orientación corregida. Solo se aceptan JPG, PNG, WebP y GIF de hasta 40 megapíxeles.
- **Montos y textos.** `monto_post` rechaza `NaN`, `Infinity`, cero, negativos y lo que no cabe en la base. Las notas y los nombres se cortan al largo de su campo.
- **Páginas de error propias**, sin datos técnicos (ver [04](04-RUTAS-Y-VISTAS.md#páginas-de-error)).
- El autoescape de Django está activo en todas las plantillas. Los textos que genera la IA o que vienen de una cartola se insertan con `textContent`, nunca como HTML.

## 4. Abuso y costos

`seguridad.limitar(veces, segundos)` pone un tope por usuario o, sin sesión, por IP. Responde 429 en JSON o redirige con un aviso.

| Vista | Tope |
| --- | --- |
| Interpretación con IA | 6 por hora. Solo por POST con token CSRF, igual que la explicación del plan: otra web no puede gastar el cupo con un enlace |
| Voz de la esfera | 40 audios por hora por persona. Solo lee textos firmados por el servidor para esa persona, con menos de 24 horas. El audio queda 6 horas en caché |
| Chat de ayuda | 10 por hora y 30 por día por IP o red /64 (`CHAT_AYUDA_TOPE_IP`), más un tope diario global de 300 llamadas (`CHAT_AYUDA_TOPE_DIARIO`) guardado en `Contador` |
| Formulario de contacto | 3 por hora, más un campo trampa para bots |
| Registro | 5 por hora por IP. Aviso de registro repetido: 2 al día por correo |
| Enlaces de correo (recuperar y confirmar) | 20 por hora por IP |
| Correos de recuperación | 3 por hora por dirección |
| Importar cartola | 20 por hora |
| Reenviar confirmación | 4 por hora |
| Vuelta de Google | 15 por hora |
| Desafío de Face ID | 30 cada 15 min al entrar, 10 por hora al vincular |

Límites de tamaño: 6 MB por petición y por archivo, 3000 campos por formulario. Las cartolas tienen además un máximo de 80 páginas, 1,5 millones de caracteres y 2000 movimientos.

### Recordatorios en el teléfono (`push.py`)

- Web Push estándar (RFC 8291 y 8292) escrito con `cryptography`, sin librerías nuevas. Cada aviso se cifra para el aparato con una clave de un solo uso: el servicio de avisos del navegador lo transporta pero no lo puede leer.
- Solo se acepta un `endpoint` por HTTPS, sin usuario ni otro puerto, y de un servicio de avisos conocido. Así nadie puede usar la app para mandar peticiones a otra dirección. Si la dirección guardada deja de cumplirlo, se borra sin conectarse.
- `VAPID_PRIVADA` firma cada envío (ES256, vigencia de 12 horas). Es un secreto como `SECRET_KEY`. Si se filtra, se genera otra con `generar_vapid` y cada aparato tiene que volver a activar los avisos.
- Por defecto el aviso no muestra montos en la pantalla bloqueada (`push_montos`).
- Al tocar el aviso, `sw.js` solo abre direcciones de Fintora.
- «Probar aviso» admite uno cada 30 segundos por cuenta, y cada cuenta guarda hasta 10 aparatos.

## 5. Infraestructura y secretos

- **Secretos** solo en variables de entorno de Railway: `SECRET_KEY`, `DATABASE_URL`, credenciales de R2 (fotos y respaldos por separado), `RESEND_API_KEY`, `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `GOOGLE_CLIENT_ID/SECRET` y `SENTRY_DSN`. Ninguno en el repositorio (ver `.gitignore`). El trabajo `secretos` del CI corre Gitleaks sobre todo el historial en cada push; `.gitleaks.toml` ignora los valores de prueba conocidos.
- **Historial de git:** las claves de R2 estuvieron publicadas en commits antiguos y se rotaron en septiembre de 2026. El historial no se reescribió, así que esas claves viejas deben considerarse públicas para siempre.
- **Base:** conexión con SSL, en la red privada de Railway.
- **Respaldos:** bucket de R2 aparte del de fotos, con credenciales propias si se definen `R2_RESPALDOS_*`. El comando se niega a subir la copia al mismo bucket de las fotos. Desde el lote 79, la copia guarda la estructura de `django_session`, `cache_finapp` y `finanzas_contador` pero no sus datos: no lleva sesiones que alguien pueda reutilizar.
- **Dominio canónico:** cualquier visita por otro nombre (`*.up.railway.app`, `www.`) se redirige a `DOMINIO_CANONICO`. `/salud/` queda fuera.
- **Cloudflare:** TLS 1.2 como mínimo, TLS 1.3 activo y registros CAA para Let's Encrypt. DNSSEC y la inscripción en la lista de HSTS *preload* quedan pendientes (D15).
- **Dependencias:** versiones exactas con hash (`--require-hashes`), `pip-audit --strict` en cada push y Dependabot semanal.
- **Sentry:** `send_default_pii=False`, sin trazas de rendimiento. No se envían cuerpos de formularios, cookies, query string ni variables locales, y de las cabeceras solo `User-Agent`, `Content-Type`, `Accept` y `Content-Length`. Los tokens de `/recuperar/` y `/registro/confirmar/` se ocultan en la URL.
- **Registro de seguridad:** ver [07 · Privacidad](07-PRIVACIDAD-Y-CUMPLIMIENTO.md#registro-de-seguridad). Es de solo lectura en el admin: nadie puede editarlo ni borrarlo a mano.

## Cómo verificar

```bash
python manage.py check --deploy --fail-level WARNING   # con DEBUG=False
python manage.py test finanzas.tests.test_vistas finanzas.tests.test_acceso_y_montos \
    finanzas.tests.test_passkeys_google_encuesta finanzas.tests.test_terceros_fotos_cache
curl -sI https://<dominio>/login/ | grep -iE 'content-security|strict-transport|x-frame|referrer|permissions'
```

Revisiones externas, con la fecha en `legal.REVISION_SEGURIDAD` y los enlaces en `legal.INFORME_*`: SSL Labs **A+** y Mozilla Observatory **A** (octubre de 2026). `/seguridad/` las muestra al público y `/.well-known/security.txt` dice a quién avisar.

La revisión completa de septiembre está en `docs/AUDITORIA-SEGURIDAD.md`, que se conserva como anexo con su fecha. Los arreglos de la auditoría de octubre (lotes 77 a 80) están resumidos en [13](13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md).
