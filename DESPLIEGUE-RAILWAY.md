# Desplegar GestorFinanzas en Railway

Salida de PythonAnywhere. El motivo del cambio es poder enlazar un dominio
propio sin pagar el plan Developer ($10/mes desde enero de 2026), y tener
Postgres en vez de SQLite.

Railway corre un contenedor normal, así que el código va tal cual: `gunicorn`,
WhiteNoise, `LocMemCache` y los comandos de `manage.py` siguen funcionando
igual que hoy. No hay reescritura.

## Archivos que ya quedaron en el repo

| Archivo | Para qué |
| --- | --- |
| `requirements.txt` | Ya estaba en la raíz. Se le agregaron `pypdf` y `openpyxl` (ver el hallazgo más abajo). |
| `Procfile` | Cómo arrancar: `gunicorn` escuchando en `$PORT`. |
| `railway.json` | `collectstatic` en el build, `migrate` antes de cada despliegue, y la política de reinicio. |
| `.env.example` | Plantilla de todas las variables que lee el código, con qué pasa si falta cada una. No lleva secretos. |
| `.gitignore` | Se le agregaron `media/`, `respaldos/` y `*.sqlite3.gz`. Ver la nota de abajo. |
| `.python-version` | Fija Python 3.10, la misma que corre hoy en PythonAnywhere. Ver la nota de abajo: hay que subirla pronto, pero no en este traslado. |

Tres ajustes en `core/settings.py`, todos por variable de entorno y sin
cambiar el comportamiento en local:

- `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` agregan solos el dominio que
  Railway publica en `RAILWAY_PUBLIC_DOMAIN`. Sin esto, la app responde
  `DisallowedHost` y los formularios se caen por CSRF en el primer despliegue.
- El log de seguridad ya no escribe a un archivo salvo que definas `LOG_DIR`.
  El disco del contenedor es efímero: ese archivo se borraba en cada
  redespliegue, o sea que no era un registro. Queda en la consola, que es lo
  que recoge el panel de Railway.
- `DB_SSL` permite desactivar `sslmode=require`. Ver el paso 2.

## Lo que salió al revisar el repo

**El `.gitignore` no cubría las copias de la base.** `manage.py respaldar`
escribe en `respaldos/` por defecto, y cada archivo ahí es la base completa
comprimida. No estaba ignorado: bastaba un `git add .` desde la carpeta
equivocada para publicar los datos de todos tus usuarios en un repo. Tampoco
estaba `media/`, donde caen las fotos de perfil en local. Ya están los tres.

**Python 3.10 sirve, pero se te vence.** Es la versión que corres hoy y con la
que vas a desplegar, porque mover el hosting y el intérprete al mismo tiempo
convierte cualquier error en una adivinanza. Dicho eso: 3.10 llega a fin de
soporte en octubre de 2026, o sea el mes que viene. Después no recibe más
parches de seguridad. Subir a 3.12 es un cambio de una línea en
`.python-version` más correr los tests, y en Railway se prueba sin riesgo
porque el despliegue anterior sigue en línea hasta que el nuevo pasa. Hazlo
como paso aparte, una vez que el traslado esté firme.

**Faltaban dos dependencias en `requirements.txt`.** El código importa
`pypdf` (`finanzas/cartolas/base.py`) y `openpyxl` (`finanzas/exportar.py`),
pero ninguna estaba declarada. En PythonAnywhere no se nota porque las
instalaste a mano en el virtualenv; en Railway el build parte de cero y sin
ellas te quedas sin lectura de cartolas en PDF y sin exportar a Excel. Ya
están agregadas.

**`build.sh` no se usa en Railway y conviene no usarlo.** Está escrito para
un flujo tipo Render y corre `migrate` dentro del build. El build no debe
tocar la base: si falla a mitad te deja el esquema a medias sin haber
desplegado nada. En `railway.json` el `migrate` va en `preDeployCommand`, que
corre después de construir y antes de cambiar la versión en línea. Déjalo en
el repo si lo usas en otra parte, pero no lo apuntes como build command.

**`cifrado.py` es código muerto, y eso te ahorra un problema.** Define
`TextoCifrado` pero ningún modelo lo usa, así que `FIELD_ENCRYPTION_KEY` no
hace falta y no hay datos cifrados que puedan quedar ilegibles al mover la
base. Si estuviera conectado, esa clave sería el punto más delicado del
traslado: sin ella la app lanza `ImproperlyConfigured`, y con la clave
equivocada cada descripción se leería "[no se pudo descifrar]". Queda igual en
`.env.example`, apagada y documentada, para cuando la actives.

**La clave de Anthropic es `ANTHROPIC_API_KEY`** (`finanzas/ia.py`). Si no
está, el análisis con IA se desactiva solo y la app sigue funcionando con los
números del motor determinístico.

## 1. Crear el proyecto

1. En Railway, **New Project → Deploy from GitHub repo** → `lordPobre/GestorFinanzas`, rama `main`.
2. En el mismo proyecto, **New → Database → Add PostgreSQL**.
3. El primer despliegue va a fallar porque faltan las variables. Es esperable.

## 2. Variables de entorno

En el servicio web, pestaña **Variables**:

```
SECRET_KEY=<genera una nueva, no reutilices la de PythonAnywhere>
DEBUG=False
DATABASE_URL=${{Postgres.DATABASE_URL}}
DB_SSL=0
```

`DATABASE_URL` se escribe con esa sintaxis de referencia: Railway la resuelve
al Postgres del proyecto y usa la red privada, que no cobra egreso.

`DB_SSL=0` va porque esa conexión interna puede rechazar el handshake TLS y
dejar la app sin arrancar. El tráfico no sale de la red privada de todas
formas. Si conectas la base desde fuera (tu máquina, un cliente SQL), esa
otra URL sí lleva SSL.

Después, lo que ya tienes en PythonAnywhere — cópialo tal cual:

```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
PROVEEDOR_CORREO=resend
RESEND_API_KEY=
CORREO_FROM=
SITE_URL=https://<tu-dominio>
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=
R2_ENDPOINT_URL=
R2_PUBLIC_DOMAIN=
```

Y `ANTHROPIC_API_KEY` para el análisis con IA.

`ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` puedes dejarlos sin definir mientras
uses el dominio `.up.railway.app` — se agregan solos. Cuando conectes el
dominio propio, ponlos explícitos con el dominio final.

## 3. Migrar los datos

El esquema lo crea `migrate` solo (está en `preDeployCommand`). Los datos no.

Primero baja la base de PythonAnywhere: en su panel, **Files** → descarga
`db.sqlite3`. Déjala en tu carpeta local del proyecto.

El resto está en **`MIGRACION-POSTGRES.md`**, que ya cubre el `dumpdata` /
`loaddata` con las exclusiones correctas. Dos notas propias de este corte:

- Corre el `loaddata` desde tu máquina apuntando a la URL **pública** del
  Postgres de Railway (la que trae `containers-us-west-…` o similar, en la
  pestaña Connect de la base). La privada solo existe dentro de Railway.
- Haz el `dumpdata` definitivo con la app vieja ya apagada, no antes. Si no,
  pierdes lo que la gente escriba entre el volcado y el corte.
- **`datos_respaldo.json` es la base entera en texto plano**: descripciones,
  correos, montos, todo. Está en `.gitignore`, pero bórralo del disco en
  cuanto confirmes que Postgres quedó bien, y no lo mandes por correo ni lo
  dejes en Descargas.

## 4. Google OAuth

En Google Cloud Console → Credentials → tu cliente OAuth, agrega la URL de
vuelta nueva, **con la barra final**:

```
https://<tu-dominio>/entrar/google/listo/
```

Deja también la de PythonAnywhere hasta que confirmes que todo anda.

## 5. Dominio propio

En el servicio web → **Settings → Networking → Custom Domain**. Railway te da
un CNAME que apuntas donde tengas el DNS. El certificado lo emite solo.

Una vez propagado, fija `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` y `SITE_URL`
con el dominio definitivo, y actualiza la URL de vuelta de Google.

## 6. Tareas programadas

Railway las hace con servicios aparte del mismo repo, que arrancan, corren y
terminan. Por cada uno: **New → GitHub Repo** (el mismo), y en Settings pones
el **Start Command** y el **Cron Schedule**.

| Servicio | Start Command | Cron |
| --- | --- | --- |
| avisos | `python manage.py avisar_pagos` | `0 13 * * *` |
| avatares | `python manage.py limpiar_avatares_huerfanos` | `0 4 * * 0` |

Las 13:00 UTC son las 9 o 10 de la mañana en Chile, igual que la tarea que
tienes hoy. `avisar_pagos` está pensado justo para esto: corre todos los días
y no hace nada salvo cuando es el día que el usuario eligió.

Estos servicios necesitan las mismas variables de entorno que el web. Conviene
crear un **Shared Variable** en el proyecto para `DATABASE_URL` y las del
correo, y referenciarla desde los tres.

## 7. Respaldos

`python manage.py respaldar` queda fuera de servicio: es específico de SQLite
y lanza `CommandError` con Postgres, por diseño. En su lugar:

- Activa los backups del servicio Postgres en Railway.
- Y guarda un `pg_dump` propio de vez en cuando. Ese comando no solo copiaba:
  verificaba la copia con `integrity_check` y contaba usuarios y movimientos.
  Un respaldo que nadie abre no es un respaldo, y eso ahora te toca a ti.

`RESPALDOS.md` está escrito para SQLite; hay que reescribirlo cuando el corte
esté hecho.

## 8. Verificar antes de avisar que ya está

En este orden, con el dominio nuevo:

1. Entrar con usuario y contraseña. Debería ser rápido; si tarda mucho, el
   problema es Argon2 contra poca CPU y hay que revisar el tamaño del servicio.
2. Entrar con Google.
3. Verificación en dos pasos, si la tienes activa.
4. Dashboard: las cifras tienen que coincidir con las de PythonAnywhere.
5. Registrar un gasto y pagar una cuota — confirma que escribe en Postgres.
6. Ver tu foto de perfil (prueba R2) y subir otra.
7. Importar una cartola de verdad, de las grandes.
8. `python manage.py avisar_pagos --seco` desde el servicio de cron, para ver
   a quién le tocaría sin mandar nada.
9. Exportar a Excel.

## 9. Volver atrás

No borres nada de PythonAnywhere ni `db.sqlite3` por al menos una semana.
Revertir es apuntar el DNS de vuelta. Los datos escritos en Postgres durante
ese tiempo no vuelven solos a SQLite, así que si hay que revertir, hazlo
pronto o asume la pérdida.

## Sobre el costo

Estás en Hobby, $5/mes. Ese número es crédito de uso, no un techo: web +
Postgres corriendo todo el mes consumen más o menos eso, y si te pasas se
cobra la diferencia. Conviene poner un límite de gasto y una alerta en el
panel antes de dejarlo andando.
