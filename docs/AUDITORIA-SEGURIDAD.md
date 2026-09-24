# Auditoría de seguridad — GestorFinanzas

Revisión del repositorio `lordPobre/GestorFinanzas` (`main`) el 15 de
septiembre de 2026, con la app ya corriendo en Railway sobre Postgres.

Primero lo que conviene decir, porque cambia cómo leer el resto: **la base
está bien construida.** Las 40 vistas que tocan datos filtran por
`usuario=request.user` sin una sola excepción, todas las que escriben exigen
POST, hay CSP con nonce, HSTS, Argon2, verificación en dos pasos, `state` en
el flujo de Google y topes de intentos. No hay inyección SQL —ni un `raw()`
ni un `extra()`—, no hay `csrf_exempt`, y el único `|safe` de las plantillas
pinta un QR generado en el servidor.

Lo que sigue no es una lista de agujeros. Son cuatro problemas concretos, y
uno de ellos es urgente.

---

## 1. RESUELTO — Las claves de Cloudflare R2 estaban publicadas en el repositorio

> **Cerrado en septiembre de 2026.** El token se rotó en Cloudflare, que es lo
> único que cierra el agujero. Lo que sigue queda como registro de qué pasó y
> por qué; el token que aparece más abajo ya no es válido.

`finanzas/migrations/0107_alter_transaccion_categoria_alter_userprofile_foto.py`,
línea 23. Cuando generaste esa migración, `makemigrations` congeló el objeto
`S3Storage` entero dentro del campo, con las credenciales incluidas:

```
access_key='18dee3fc1f42ba24be7620f6ca9ab52a'
secret_key='493cc6b21ce277342770...'
bucket_name='finapp'
endpoint_url='https://223db563a6d18d9d16e20d340d0b05fd.r2.cloudflarestorage.com'
```

Es un token de API con acceso de escritura al bucket. Con eso, cualquiera que
lea el repositorio puede listar, descargar, reemplazar o borrar todas las
fotos de perfil de tus usuarios. Y si el repositorio es público, "cualquiera"
significa cualquiera: hay rastreadores que buscan justo este patrón en los
commits nuevos de GitHub, en cuestión de minutos.

Hiciste todo bien en `settings.py` —las credenciales por variables de
entorno, `.env` ignorado— y la migración las filtró por detrás. Es un fallo
conocido de `makemigrations` con `django-storages`, y no es culpa tuya.

**Qué hacer, en este orden:**

1. **Rota el token en Cloudflare, ahora.** Panel de R2 → Manage API Tokens →
   borra ese token y crea uno nuevo. Esto es lo único que de verdad cierra el
   agujero: el token viejo queda en el histórico de git para siempre y no hay
   forma de borrarlo de ahí que sirva de algo.
2. Pon las credenciales nuevas en las variables de Railway
   (`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`).
3. Sube la migración corregida que está en `entrega-seguridad/`. Apunta el
   campo al callable `obtener_almacen`, igual que hace la 0108. Un `storage`
   no afecta al esquema de la base, así que editar esa migración es seguro y
   no necesita `makemigrations` ni rompe el histórico.
4. Revisa el bucket por si alguien ya estuvo: en Cloudflare, los registros de
   R2 te dicen si hubo accesos que no vengan de tu app.

**Y revisa lo mismo en tus otros catorce repositorios.** El patrón que causó
esto —`makemigrations` con un storage configurado con literales— se repite en
cualquier proyecto Django que use `django-storages` así.

Mientras estás en eso: la contraseña del Postgres de Railway también se
expuso, en nuestra conversación, al pegar la URL de conexión. Y el proxy
público de la base sigue abierto. En el servicio Postgres de Railway,
desactiva el **TCP Proxy** ahora que terminaste de migrar — la app usa la red
privada y no lo necesita. Eso deja la credencial inservible desde fuera.

---

## 2. El bloqueo por intentos fallidos vale la mitad de lo que crees

`seguridad.py` guarda los contadores en `LocMemCache`, que es la memoria de
**un** proceso. El `Procfile` que te armé arranca `gunicorn --workers 2`.
Resultado: cada worker lleva su propia cuenta, y el tope de 5 intentos son en
realidad 10 —el balanceador reparte, y quien prueba contraseñas no nota
nada—. El propio archivo lo advertía en su comentario de cabecera; el
`Procfile` lo activó. Es mi error, no tuyo.

Lo mismo afecta a los otros topes, y uno cuesta dinero: `analisis_ia` permite
6 llamadas por hora, o sea 12 reales contra la API de Anthropic.

**Arreglo:** caché en base de datos, que los workers comparten. Ya está en el
`settings.py` de `entrega-seguridad/`, activa solo cuando hay `DATABASE_URL`
(en local sigue en memoria, que es lo correcto con un proceso). Cuesta una
consulta por comprobación, invisible al lado de un Argon2.

Necesita crear la tabla una vez. Añádelo al **Pre-Deploy Command** de
Railway, antes del `migrate` —es idempotente, puede correr en cada
despliegue—:

```
python manage.py createcachetable && python manage.py migrate --noinput
```

---

## 3. El bloqueo por IP se puede esquivar con un encabezado

`seguridad.py`, función `_ip()`. Lee la **primera** entrada de
`X-Forwarded-For`, y ese encabezado lo escribe quien quiera. Basta mandar
`X-Forwarded-For: 1.2.3.4` y cambiar el número en cada petición para que cada
intento cuente como una IP nueva: el bloqueo por IP no se activa jamás.

Afecta al tope de acceso, al de registro (5 por hora) y al de recuperación de
contraseña, que es el que protege tu cuota de correo.

La lógica correcta es la contraria: cada proxy **añade al final** la
dirección de quien le habló. Con un proxy propio delante —Railway pone uno—
el encabezado queda `<lo que invente el cliente>, <IP real>` y la buena es la
última. El `seguridad.py` de `entrega-seguridad/` lo lee así, con
`PROXIES_CONFIABLES` en settings diciendo cuántos tramos creer (1 en
producción, 0 en local).

No añadas `PROXIES_CONFIABLES` a las variables de Railway: se ajusta solo
según `DEBUG`. Solo tócala si algún día pones Cloudflare por delante, y ahí
son 2.

---

## 4. El panel de administración está en la puerta que todos prueban

`/admin/` en un dominio público recibe escaneo automatizado desde el primer
día. No es que el admin de Django sea inseguro; es que regala un formulario
de acceso contra el que probar contraseñas, y una sesión de staff ahí ve y
edita los datos de todos tus usuarios sin pasar por ninguno de los filtros
`usuario=request.user` que tan bien tienes puestos. Súmale que tu propio
middleware deja `/admin` fuera de la política de contenido, a propósito y con
razón.

En `entrega-seguridad/core/urls.py` la ruta sale de `ADMIN_URL`:

- `ADMIN_URL=panel-9f3a2c` (algo que solo tú sepas) lo saca del barrido.
- `ADMIN_URL=` vacío lo desactiva por completo, y **esto es lo que te
  recomiendo**: no tienes `admin.py` con modelos registrados, así que no lo
  estás usando. Lo que necesites hacer a mano lo haces mejor con
  `manage.py shell` contra la base, como ya hiciste al migrar.

Esconder una ruta no es seguridad de verdad. Apagar lo que no usas, sí.

---

## Lo que revisé y está bien

Vale saber dónde no hace falta gastar esfuerzo.

**Aislamiento entre usuarios.** Las 40 vistas con `id` en la URL usan
`get_object_or_404(Modelo, id=..., usuario=request.user)`. Las de préstamos
cruzan bien la relación (`persona__usuario=request.user`). Cambiar el número
en la URL da 404, no los datos de otro. Esto es lo que más importa en una app
con varios usuarios y está sólido.

**CSRF y métodos.** Ninguna vista que escribe responde a GET: todas abren con
`request.method == 'POST'`. Así la protección CSRF de Django cubre de verdad
cada acción destructiva, y `eliminar-deuda/5/` pegado en una etiqueta de
imagen no borra nada.

**Contraseñas y sesiones.** Argon2 primero en `PASSWORD_HASHERS`, cuatro
validadores con mínimo de 8, enlaces de recuperación de 1 hora en vez de los
3 días que trae Django. Cookies `Secure`, `HttpOnly`, `SameSite=Lax`;
`login()` de Django rota la sesión, así que no hay fijación de sesión.

**Google OAuth.** `state` aleatorio en sesión y comparado a la vuelta; se
valida `iss`, `aud` y `exp` del `id_token`; se exige `email_verified` antes de
vincular por correo; el `next` se filtra contra redirección abierta; y el
segundo factor se pide igual aunque Google ya acreditara el correo. Está
mejor resuelto que muchos que usan una librería.

**CSP.** Con nonce por respuesta, `object-src 'none'`, `frame-ancestors
'none'`, `form-action 'self'` y `connect-src 'self'`. El `unsafe-inline` de
estilos está justificado y no permite ejecutar código.

**Cifrado de campos.** `cifrado.py` existe pero ningún modelo lo usa. No es
un problema de seguridad hoy, y te ahorró un dolor de cabeza al migrar la
base. Si algún día lo conectas, la clave pasa a ser tan crítica como la base
misma.

---

## Tres cosas que no son fallos, pero que dejaría anotadas

**No hay registro persistente de accesos fallidos.** En Railway los logs van
a la consola y se retienen poco. Si alguien te ataca, no vas a tener con qué
reconstruirlo. Si algún día importa, un modelo `IntentoAcceso` en la base es
media hora de trabajo y te da algo consultable.

**La verificación en dos pasos es opcional y nadie la tiene activa.** Lo vi
al migrar: `SegundoFactor` tiene 1 fila entre 9 usuarios. El mecanismo está
construido y probado; solo falta usarlo. Empieza por tu propia cuenta.

**Python 3.10 vence el mes que viene.** Fin de soporte en octubre de 2026, o
sea sin más parches de seguridad. Ya lo hablamos: es un cambio de una línea
en `.python-version` más correr los tests, y en Railway se prueba sin riesgo.
Para una app con datos financieros es lo siguiente en la lista, después de
rotar las claves de R2.

---

## Orden de trabajo

| | Qué | Dónde |
| --- | --- | --- |
| 1 | Rotar el token de R2 en Cloudflare | Panel de Cloudflare |
| 2 | Cerrar el TCP Proxy del Postgres | Panel de Railway |
| 3 | Subir la migración 0107 corregida | `entrega-seguridad/` |
| 4 | Subir `seguridad.py` y `settings.py` | `entrega-seguridad/` |
| 5 | `createcachetable` en el Pre-Deploy | Panel de Railway |
| 6 | `ADMIN_URL=` vacío en las variables | Panel de Railway |
| 7 | Activarte la verificación en dos pasos | La app |
| 8 | Subir a Python 3.12 | `.python-version` |

Los pasos 1 y 2 no dependen de ningún despliegue: hazlos antes de seguir
leyendo cualquier otra cosa.
