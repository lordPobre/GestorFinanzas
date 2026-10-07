# 10 · Operación

Lo que hay que hacer para que el servicio siga funcionando: tareas programadas, respaldos, monitoreo, mantenimiento e incidentes.

## Servicios en Railway

| Servicio | Config | Qué corre | Cuándo (UTC) | Hora en Chile |
| --- | --- | --- | --- | --- |
| web | `railway.json` | gunicorn | Siempre | |
| Postgres | Base gestionada | PostgreSQL 18 | Siempre | |
| avisos | `railway/avisos.json` | `python manage.py avisar_pagos` | `0 13 * * *` | 9–10 AM |
| inactivas | `railway/inactivas.json` | `python manage.py limpiar_inactivas` | `0 12 * * *` | 8–9 AM |
| respaldo | `railway/respaldo.json` | `python manage.py respaldar_postgres` | `0 7 * * *` | 3–4 AM |
| avatares | `railway/avatares.json` | `python manage.py limpiar_avatares_huerfanos` | `0 4 * * 0` | Domingos de madrugada |
| limpieza | `railway/limpieza.json` | `python manage.py limpieza_diaria` | `30 6 * * *` | 2:30–3:30 AM |
| recordatorios | `railway/recordatorios.json` | `python manage.py enviar_recordatorios` | `0 12 * * *` | 8–9 AM |

Cada tarea es un servicio aparte del mismo repositorio, que arranca, corre y termina (`restartPolicyType: NEVER`). En *Settings → Config-as-code → Railway Config File* se apunta a su archivo. Sin eso, el servicio toma `railway.json` y arranca un servidor web.

## Tareas programadas

### `avisar_pagos`

Corre todos los días y la mayoría de los días no envía nada. A cada usuario activo con el aviso encendido y un correo guardado, le manda el resumen de lo que le queda por pagar **el día que eligió** (`aviso_dia`, por defecto el 20; en meses más cortos se usa el último día). Lo hace **una vez por mes** (`aviso_ultimo_periodo`) y solo si hay algo por pagar. Antes genera los cobros de suscripciones que falten.

```bash
python manage.py avisar_pagos --seco                 # qué enviaría hoy
python manage.py avisar_pagos --usuario ana --forzar # probar con una cuenta
```

### `limpiar_inactivas`

Cumple el plazo de conservación que promete la política:

1. A las cuentas sin ninguna señal de uso durante 12 meses les envía el correo “tu cuenta se va a borrar”. La señal es la más reciente entre `last_login`, `date_joined` y `ultima_actividad`. Si el correo no sale, la cuenta no queda marcada y se reintenta al día siguiente.
2. Borra las cuentas avisadas hace más de 30 días que no volvieron. Si la persona entró después del aviso, se limpia la marca y sale de la cola.
3. Purga los eventos de seguridad de más de 365 días.

Los superusuarios nunca entran en la lista.

```bash
python manage.py limpiar_inactivas --seco        # obligatorio antes de activarla en un entorno nuevo
python manage.py limpiar_inactivas --solo-avisos
```

### `limpieza_diaria`

Corre `clearsessions`, borra los contadores de `Contador` ya vencidos y las filas de `SesionActiva` cuya sesión de Django ya no existe.

### `enviar_recordatorios`

A cada cuenta activa con al menos un aparato le arma los avisos del día según sus opciones: lo que vence hoy, lo que vence mañana, los topes que llegaron al 80 % o al 100 % (un aviso por nivel y por mes) y, los domingos, el resumen. Pasa una vez al día por cada cuenta (`push_ultimo_dia`). Borra los aparatos que el servicio da por vencidos. Si una cuenta falla, lo anota en el log y sigue con las demás; esa cuenta se vuelve a intentar en la corrida siguiente. Sin `VAPID_PRIVADA` no hace nada.

```bash
python manage.py enviar_recordatorios           # los de hoy
python manage.py enviar_recordatorios --forzar  # aunque ya hayan salido hoy
python manage.py generar_vapid                  # el par de claves, una sola vez
```

### `avisar_politica`

Se corre a mano, una vez por versión, al menos una semana antes de la vigencia. Manda a cada cuenta activa con correo el resumen de `legal.CAMBIOS` y anota la versión en `politica_avisada`, así que repetirlo solo manda a las que faltan. Si un correo no sale, esa cuenta queda pendiente para la próxima corrida. Espera 0,6 segundos entre correos para no pasar el límite de Resend.

```bash
python manage.py avisar_politica --seco            # a cuántas cuentas avisaría
python manage.py avisar_politica --usuario carlos  # probar con una cuenta
python manage.py avisar_politica                   # a todas
```

En producción se corre dentro del servicio web: `railway ssh` (con el proyecto y el servicio web elegidos) y ahí el comando. Necesita `RESEND_API_KEY` y `SITE_URL`, que ese servicio ya tiene.

### `limpiar_avatares_huerfanos`

Lista los archivos de `avatares/` que ningún perfil referencia. Con `--borrar`, los elimina. Si todos parecen huérfanos, aborta: eso indica un problema de rutas, no archivos sobrantes.

## Respaldos

Hay dos líneas:

1. **Propia:** `respaldar_postgres` todos los días a un bucket **privado** de R2, distinto del de las fotos y con un token propio. Hace el volcado de la base, verifica que tenga datos de `auth_user`, `finanzas_transaccion` y `finanzas_userprofile`, calcula el SHA-256, lo sube a `postgres/fintora-AAAAMMDD-HHMMSS.dump` y deja las 30 copias más recientes. De `django_session`, `cache_finapp` y `finanzas_contador` guarda solo la estructura.
2. **Del proveedor:** los respaldos del Postgres de Railway, para volver atrás rápido.

El servicio `respaldo` se construye con `railway/Dockerfile.respaldo` (Python 3.13 más el cliente oficial de PostgreSQL), para que `pg_dump` sea de la misma versión mayor que el servidor. Si se actualiza Postgres, hay que definir `PG_MAJOR` con la versión nueva. El comando compara las versiones y falla con un mensaje claro si no calzan.

### Restaurar

Nunca directo sobre producción:

1. Descargar la copia desde R2 y comprobar su SHA-256 contra el metadato.
2. Crear un Postgres vacío.
3. `pg_restore --no-owner --no-privileges --dbname "$URL_DESTINO" fintora-AAAAMMDD-HHMMSS.dump`
4. Apuntar *staging* a esa base y revisar que se puede entrar y que están los movimientos.
5. Recién entonces, cambiar `DATABASE_URL` del servicio web o restaurar sobre producción con `--clean`.

### Simulacro mensual

El primer lunes de cada mes: descargar la última copia, verificar el hash, restaurarla en una base vacía, comparar la cantidad de usuarios y de movimientos con producción, borrar todo y anotar el resultado en la tabla de `docs/RESPALDOS.md`. El último fue el 24 de septiembre de 2026 y coincidió con producción.

## Monitoreo

| Qué | Dónde | Alerta |
| --- | --- | --- |
| Disponibilidad | UptimeRobot, cada 5 min, sobre `/salud/` buscando `"estado": "ok"` | Correo al caerse y al volver |
| Errores | Sentry (`SENTRY_DSN`) | Correo con cada error nuevo |
| Logs | Panel de Railway (consola). `seguridad.log` solo si hay un volumen con `LOG_DIR` | |
| Tareas | Panel de Railway: cada corrida de un servicio programado queda con su salida y su código de salida | Una corrida fallida queda en rojo |
| Costo | Panel de Railway | Límite y alerta de gasto |
| Voz | Deploy Logs: `ElevenLabs devolvió …` | Ninguna automática. 401 = clave mala; 404 = *voice ID* malo; 400 `free_users_not_allowed` o 402 `paid_plan_required` = voz que pide plan de pago; 402 `quota_exceeded` = sin créditos |
| IP real | `/perfil/diagnostico-ip/`, solo personal | Revisar al cambiar algo delante de Railway (por ejemplo, poner Cloudflare como proxy) |

`/salud/` prueba la base (`SELECT 1`) y la caché (escribir y leer una clave). Si algo falla, responde 503 con `degradado` y qué parte falló.

### Respuestas lentas

`RendimientoMiddleware` mide cada petición. Si tarda más de `RESPUESTA_LENTA_MS` (1500 ms), deja en el log `Respuesta lenta: GET <ruta>, N ms, M consultas`, con la ruta sin ids. Para una cuenta de personal, cada respuesta trae además la cabecera `Server-Timing`, que se ve en la pestaña Red del navegador. Sirve para decidir D5 y D8 con datos: buscar `Respuesta lenta` en los registros de Railway una vez por semana.

## Correo

- Proveedor: Resend, con dominio `perseustechnology.dev` verificado y SPF, DKIM y DMARC en `PASS`.
- DMARC está en `p=none` con informes a `soporte@`. **Pendiente entre el 9 y el 23 de octubre de 2026:** revisar los informes, confirmar el DKIM de Zoho y pasar a `p=quarantine`.
- En *staging* no sale ningún correo salvo que `CORREO_EN_STAGING=1`: el cuerpo se escribe en el log.

## Mantenimiento periódico

| Frecuencia | Tarea |
| --- | --- |
| Semanal | Revisar y fusionar los PR de Dependabot con el CI en verde |
| Mensual | Simulacro de restauración. Revisar Sentry y los eventos `bloqueo` y `admin_denegado` en el admin |
| Mensual | Revisar el consumo de la API de Anthropic, el tope diario del chat y los créditos de ElevenLabs |
| Trimestral | Volver a pasar SSL Labs y Mozilla Observatory, y actualizar `legal.REVISION_SEGURIDAD` y la tabla del `README.md` |
| Trimestral | Revisar `docs/CARTOLAS-COBERTURA.md` y los formatos que fallaron (las muestras anónimas que hayan llegado) |
| Anual | Rotar `SECRET_KEY` (cierra todas las sesiones, obliga a volver a vincular Face ID y hace que todos los aparatos cuenten como nuevos: avisar antes), las credenciales de R2 y las claves de API, incluida la de ElevenLabs. Anotar la fecha de cada rotación |
| Si se filtra `VAPID_PRIVADA` | Generar otra con `generar_vapid` y cambiarla en Railway. Todos los aparatos dejan de recibir avisos hasta que cada persona los active de nuevo. No se rota por calendario |
| Al cambiar la política | Subir `legal.VERSION` y `VIGENTE_DESDE`, escribir `legal.CAMBIOS`, correr `avisar_politica` al menos una semana antes de la fecha de vigencia y actualizar `docs/REGISTRO-TRATAMIENTOS.md` |

## Incidentes de seguridad

El procedimiento completo está en `docs/BRECHAS.md` y se lee el día que pasa. En resumen:

1. **Contener primero.** Si se filtró una credencial, rotarla y redesplegar (rotar `SECRET_KEY` cierra todas las sesiones). Si el problema es el admin, dejar `ADMIN_URL` vacía. Si es la base, rotar su contraseña y revisar las conexiones.
2. **Anotar la hora** en que se detectó, cómo y qué se hizo. El plazo legal corre desde ese momento.
3. **Determinar el alcance** con cinco preguntas: qué datos, de cuántas personas, si se copiaron, si hay datos de terceros (“Me deben”) y si la vía sigue abierta. Las fuentes son los logs de Railway, Sentry, `EventoSeguridad` y los registros de R2.
4. **Notificar** a la Agencia de Protección de Datos Personales si hay datos personales comprometidos (la duda se resuelve notificando), con un plazo de referencia de 72 h. Notificar a los titulares si la exposición puede perjudicarlos.
5. **Cerrar:** arreglar la causa, escribir una prueba que falle si el agujero vuelve y anotarlo en el historial de `BRECHAS.md`.

El historial registra un incidente: las claves de R2 publicadas en el historial de git (15 de septiembre de 2026), rotadas y cerradas sin evidencia de acceso de terceros.

## Soporte a usuarios

- Canal: `soporte@perseustechnology.dev`. Ahí llegan también los formularios del chat de ayuda y los avisos de fallas de seguridad (`security.txt`).
- Las solicitudes de derechos por escrito tienen un plazo de 30 días corridos.
- Si el envío de correos está caído, la pantalla de recuperación dice que se escriba a soporte. El restablecimiento manual se hace con `railway run python manage.py changepassword <usuario>`, después de verificar la identidad por un canal propio.
- Para investigar un problema de una cuenta se usan los eventos de seguridad y los logs. No se entra a la cuenta de la persona.
