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

Se guardan en la caché de la base, compartida por todos los workers. Con `LocMemCache` cada proceso llevaría su propia cuenta y el tope se multiplicaría por la cantidad de workers.

| Contador | Tope | Bloqueo | Para qué |
| --- | --- | --- | --- |
| Usuario escrito + IP | 5 fallos | 15 min | El caso normal |
| Por cuenta | 20 fallos/h | Hasta que vence la hora | Alguien que prueba desde muchas IP contra una cuenta |
| Por IP | 50 fallos/h | Hasta que vence la hora | Una IP que prueba muchas cuentas |
| 2FA (`2fa:{id}` + IP) | 5 códigos | 15 min | Adivinar el código de 6 dígitos |
| Face ID por IP | 5 fallos | 15 min | Credenciales inventadas |

Mientras el bloqueo esté activo, ni siquiera la contraseña correcta entra. Al entrar bien se limpian el contador del par y el de la cuenta, pero no el de la IP. Así una red que prueba muchas cuentas no se “lava” acertando una. `test_acceso_y_montos.py` cubre los cinco casos.

**La IP real.** `_ip()` no confía en `X-Forwarded-For` tal como viene, porque cualquiera puede escribirlo. Toma el tramo número `PROXIES_CONFIABLES` contando desde el final (en Railway, el último), que es el que agregó el proxy propio. Con `PROXIES_CONFIABLES=0` usa `REMOTE_ADDR`.

### Verificación en dos pasos (TOTP)

- El secreto se genera con `pyotp.random_base32()`. El QR se dibuja como SVG en el servidor, así el secreto no viaja a ningún servicio externo.
- Para activarla hay que ingresar un código válido. En ese momento se generan **8 códigos de respaldo** que se muestran una sola vez y se guardan con hash.
- El código se acepta con una ventana de ±30 s. **El mismo código no sirve dos veces**: se guarda el último usado.
- Desactivar o regenerar los códigos exige la contraseña.
- La recuperación de contraseña también exige el código si la cuenta tiene 2FA. Robar el correo no alcanza.
- Con Google o con Face ID también se pasa por el segundo paso si está activo.

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
- El código se canjea en el endpoint de token de Google con el `client_secret`, por TLS. La firma del `id_token` no se verifica, lo que OIDC Core 3.1.3.7 permite cuando el token llega directo del endpoint de token. Sí se validan `iss`, `aud`, `exp`, `sub` y `email_verified`.
- Primero se busca la cuenta por `google_sub`. Si no existe, se busca por correo; si tampoco existe, se crea una cuenta sin contraseña utilizable.
- Solo se vincula por correo si la cuenta existente lo tiene confirmado. Si no, pide entrar con usuario y contraseña, o recuperarla, y confirmar el correo desde el perfil.

### Recuperación de contraseña

- 3 solicitudes por IP cada 15 minutos.
- La respuesta es siempre “te mandamos un correo”, exista o no la cuenta. No sirve para averiguar quién está registrado.
- El enlace usa el generador de tokens de Django, vale 1 hora y deja de servir en cuanto la contraseña cambia.

### Sesiones

- Duran 8 horas y se renuevan en cada petición (`SESSION_SAVE_EVERY_REQUEST`).
- En producción las cookies son `Secure`, `HttpOnly` y `SameSite=Lax`.
- Cada sesión abierta queda registrada con IP y navegador (`SesionActiva`). En *Perfil → Sesiones* se puede cerrar cualquiera o todas las demás, y eso borra la sesión de Django.
- `login()` rota la clave de sesión, lo que evita la fijación de sesión.

## 2. Aislamiento entre usuarios

- Cada consulta filtra por `usuario=request.user`. Un id ajeno da **404**.
- `test_vistas.py` crea dos usuarios con datos de todos los tipos y prueba que ninguno alcance, modifique o liste lo del otro.
- La descarga de datos, el borrado y la encuesta también están probados contra la cuenta de al lado.
- Las fotos se sirven desde un almacenamiento privado con URL firmada de 6 horas. No hay listado público. `test_terceros_fotos_cache.py` lo verifica.
- El admin no existe si `ADMIN_URL` está vacía. Si existe, está en una ruta no adivinable y el login es el de la app. Una cuenta sin permiso recibe 404 y queda un evento `admin_denegado`.

## 3. XSS y contenido de terceros

**Content-Security-Policy** en cada respuesta HTML (`middleware.PoliticaContenidoMiddleware`):

```
default-src 'self';
script-src 'self' 'nonce-<aleatorio por respuesta>';
style-src 'self' 'unsafe-inline';
font-src 'self';
img-src 'self' data: blob: https:;
connect-src 'self';
frame-src 'none'; object-src 'none';
form-action 'self'; frame-ancestors 'none'; base-uri 'self'
```

- Todo `<script>` lleva `nonce="{{ csp_nonce }}"`. Si se cuela una inyección, el navegador no la ejecuta. Hay pruebas que recorren la landing y las páginas legales buscando scripts sin nonce.
- `style-src 'unsafe-inline'` se mantiene porque las plantillas usan atributos `style`. Eso no permite ejecutar código.
- `connect-src 'self'`: el JavaScript solo puede hablar con la propia app. Las llamadas a Anthropic y a Resend salen del servidor, nunca del navegador.
- Las fuentes, los íconos y Chart.js se sirven desde `static/vendor`. **El navegador no le pide nada a ningún tercero**, lo que prueba `test_terceros_fotos_cache.py`.
- `Permissions-Policy` bloquea cámara, micrófono, ubicación, pagos y USB.
- Además: `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin` y `Cross-Origin-Opener-Policy: same-origin`.
- El autoescape de Django está activo en todas las plantillas. Los textos que genera la IA o que vienen de una cartola se insertan con `textContent`, nunca como HTML.

## 4. Abuso y costos

`seguridad.limitar(veces, segundos)` pone un tope por usuario o, sin sesión, por IP. Responde 429 en JSON o redirige con un aviso.

| Vista | Tope |
| --- | --- |
| Interpretación con IA | 6 por hora |
| Chat de ayuda | 10 por hora por visitante, más un tope diario global de 300 llamadas (`CHAT_AYUDA_TOPE_DIARIO`) |
| Formulario de contacto | 3 por hora, más un campo trampa para bots |
| Registro | 5 por hora por IP |
| Importar cartola | 20 por hora |
| Reenviar confirmación | 4 por hora |
| Vuelta de Google | 15 por hora |
| Desafío de Face ID | 30 cada 15 min al entrar, 10 por hora al vincular |

Límites de tamaño: 6 MB por petición y por archivo, 3000 campos por formulario. Las cartolas tienen además un máximo de 80 páginas, 1,5 millones de caracteres y 2000 movimientos.

## 5. Infraestructura y secretos

- **Secretos** solo en variables de entorno de Railway: `SECRET_KEY`, `DATABASE_URL`, credenciales de R2 (fotos y respaldos por separado), `RESEND_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_CLIENT_ID/SECRET` y `SENTRY_DSN`. Ninguno en el repositorio (ver `.gitignore`).
- **Historial de git:** las claves de R2 estuvieron publicadas en commits antiguos y se rotaron en septiembre de 2026. El historial no se reescribió, así que esas claves viejas deben considerarse públicas para siempre.
- **Base:** conexión con SSL, en la red privada de Railway.
- **Respaldos:** bucket de R2 aparte del de fotos, con credenciales propias si se definen `R2_RESPALDOS_*`. El comando se niega a subir la copia al mismo bucket de las fotos.
- **Dependencias:** versiones exactas con hash (`--require-hashes`), `pip-audit --strict` en cada push y Dependabot semanal.
- **Sentry:** `send_default_pii=False`, sin trazas de rendimiento. Solo se envían los errores, sin cuerpos de petición ni datos del usuario.
- **Registro de seguridad:** ver [07 · Privacidad](07-PRIVACIDAD-Y-CUMPLIMIENTO.md#registro-de-seguridad). Es de solo lectura en el admin: nadie puede editarlo ni borrarlo a mano.

## Cómo verificar

```bash
python manage.py check --deploy --fail-level WARNING   # con DEBUG=False
python manage.py test finanzas.tests.test_vistas finanzas.tests.test_acceso_y_montos \
    finanzas.tests.test_passkeys_google_encuesta finanzas.tests.test_terceros_fotos_cache
curl -sI https://<dominio>/login/ | grep -iE 'content-security|strict-transport|x-frame|referrer|permissions'
```

La revisión completa más reciente está en `docs/AUDITORIA-SEGURIDAD.md`, que se conserva como anexo con su fecha.
