# 09 · Instalación y despliegue

## Desarrollo local

Requiere Python 3.13 y git. Postgres es opcional: sin `DATABASE_URL` se usa SQLite.

```bash
git clone https://github.com/lordPobre/GestorFinanzas.git
cd GestorFinanzas
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
python -m pip install --require-hashes -r requirements.txt -r requirements-dev.txt
echo "DEBUG=True" > .env               # o copiar .env.example si existe
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Con `DEBUG=True` no hace falta nada más:

- `SECRET_KEY` usa una clave de desarrollo.
- La base es `db.sqlite3` en modo WAL.
- Las fotos van a `media/`.
- Sin `RESEND_API_KEY` los correos no salen: se anota un error en el log y la vista avisa. Para ver el enlace de confirmación o de recuperación, búscalo en la consola.
- Sin `ANTHROPIC_API_KEY`, el análisis muestra solo el motor propio y el chat de ayuda pasa directo al formulario.
- Sin `GOOGLE_CLIENT_ID`, el botón de Google no aparece.

Para probar Face ID en local hace falta `localhost` (WebAuthn exige un contexto seguro, y `localhost` cuenta como tal) o un túnel HTTPS con `WEBAUTHN_RP_ID` igual a su dominio.

## Variables de entorno

| Variable | Obligatoria | Para qué |
| --- | --- | --- |
| `SECRET_KEY` | Sí, en producción | Firma de sesiones, tokens y el *user handle* de Face ID. Rotarla cierra todas las sesiones y obliga a volver a vincular Face ID |
| `DEBUG` | | `True` solo en local |
| `ALLOWED_HOSTS` | Sí | Dominios propios separados por coma. El de Railway se suma solo |
| `CSRF_TRUSTED_ORIGINS` | Sí, con dominio propio | `https://dominio`. El de Railway se suma solo |
| `DATABASE_URL` | Sí, en producción | Postgres |
| `DB_SSL` | | `0` desactiva SSL. En Railway va en `0`: la conexión por la red privada puede rechazar TLS y el tráfico no sale de esa red. En el CI también |
| `PROXIES_CONFIABLES` | | `1` en Railway (valor por defecto sin `DEBUG`) |
| `ADMIN_URL` | | Ruta del admin, difícil de adivinar. Vacía, no hay admin |
| `ENTORNO` | | `staging` en el entorno de pruebas |
| `CORREO_EN_STAGING` | | `1` para que *staging* envíe correos de verdad |
| `SITE_URL` | Recomendada | `https://dominio`, para los enlaces de los correos. Sin ella, los correos de tareas programadas llevan rutas relativas |
| `RESEND_API_KEY`, `CORREO_FROM` | Para correo | Clave de Resend y remitente (`Fintora <no-responder@dominio>`), con el dominio verificado en Resend |
| `ANTHROPIC_API_KEY` | Para IA | Análisis y chat de ayuda |
| `CHAT_AYUDA_TOPE_DIARIO` | | Tope diario de llamadas del chat (300 por defecto) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Para Google | Cliente OAuth tipo “Aplicación web”, con URI de redirección `https://dominio/entrar/google/listo/` |
| `WEBAUTHN_RP_ID` | Recomendada | Dominio de Face ID (`fintora.cl`). Si cambia, las credenciales vinculadas dejan de servir |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_ENDPOINT_URL` | Para fotos | Cloudflare R2. Sin ellas, al disco (que en Railway no persiste) |
| `R2_BUCKET_RESPALDOS` | Para respaldos | Bucket privado y distinto del de fotos |
| `R2_RESPALDOS_ACCESS_KEY_ID`, `R2_RESPALDOS_SECRET_ACCESS_KEY` | Recomendada | Credenciales solo para respaldos. Sin ellas se usan las de fotos |
| `PG_MAJOR` | En el servicio de respaldo | Versión mayor de Postgres para instalar un `pg_dump` compatible |
| `RESPALDOS_DIR` | | Carpeta del respaldo SQLite |
| `SENTRY_DSN` | | Monitoreo de errores |
| `LOG_DIR` | | Carpeta para `seguridad.log` |

## Producción en Railway

El servicio web se despliega desde `main` en el plan Hobby (USD 5 al mes de crédito de uso: web y Postgres consumen más o menos eso; conviene fijar un límite y una alerta de gasto en el panel). `railway.json` define:

| Fase | Comando |
| --- | --- |
| Build (Nixpacks) | `python manage.py collectstatic --noinput`. El build no recibe las variables del servicio: `settings.py` usa una clave ficticia solo para este comando |
| Antes de cada despliegue | `python manage.py createcachetable && python manage.py migrate --noinput` |
| Arranque | `gunicorn core.wsgi --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60` |
| Comprobación de vida | `GET /salud/` con 30 s de margen |
| Reinicio | Si falla, hasta 3 veces |

Si la migración falla, el despliegue se detiene y queda corriendo la versión anterior.

### Primera puesta en marcha

1. Crear el proyecto en Railway con un servicio Postgres y otro web desde el repositorio.
2. En el servicio web, `DATABASE_URL=${{Postgres.DATABASE_URL}}` (red privada, sin costo de egreso), `DB_SSL=0` y el resto de las variables de la tabla. Conviene definir como *Shared Variables* las que usan también los servicios programados (`DATABASE_URL`, correo, `SECRET_KEY`, R2).
3. Desplegar. `createcachetable` y `migrate` corren solos.
4. `railway run python manage.py createsuperuser`.
5. Conectar el dominio propio y ponerlo en `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SITE_URL` y `WEBAUTHN_RP_ID`.
6. En Resend, verificar el dominio del remitente. En Google Cloud, agregar la URI de redirección y poner el nombre “Fintora” en la pantalla de consentimiento.
7. Crear el servicio de respaldo (ver [10 · Operación](10-OPERACION.md#respaldos)).
8. Programar las tareas (ver [10 · Operación](10-OPERACION.md#tareas-programadas)).
9. Verificar:

```bash
curl -s https://dominio/salud/                     # {"estado": "ok", ...}
railway run python manage.py check --deploy
```

### Staging

Es un segundo entorno con su propia base, `ENTORNO=staging` y sin `ANTHROPIC_API_KEY`, para no gastar cuota. Tiene `noindex`, una franja visible y el correo bloqueado. El detalle está en `docs/STAGING.md`, que se conserva como anexo.

## Dependencias

- Los rangos se declaran en `requirements.in` (producción) y `requirements-dev.in` (`ruff`, `coverage`, `pip-tools`, `pip-audit`).
- Los `.txt` se generan con versiones exactas y hashes:

```bash
pip-compile --generate-hashes --allow-unsafe --output-file requirements.txt requirements.in
pip-compile --generate-hashes --allow-unsafe --output-file requirements-dev.txt requirements-dev.in
```

- Se suben los `.in` y los `.txt` en el mismo commit. El CI instala con `--require-hashes`.
- Verificar que los `.in` estén en el repositorio (ver I1 en [13 · Deuda técnica](13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md#infraestructura-y-repositorio)).

## Migraciones

- Toda modificación de un modelo lleva su migración en el mismo commit. El CI lo comprueba con `makemigrations --check`.
- Las migraciones se aplican antes de levantar la versión nueva. Deben ser compatibles con el código anterior durante unos segundos: primero agregar, después usar y recién en otro despliegue borrar.
- Una migración destructiva (borrar una columna con datos) necesita un respaldo inmediatamente antes, con `respaldar_postgres --destino` o `--seco` para verificar.

## Volver atrás

1. En Railway, “Redeploy” del despliegue anterior. Revierte el código, no la base.
2. Si la migración nueva ya corrió y no es compatible hacia atrás, hay que revertirla: `railway run python manage.py migrate finanzas <migración anterior>`. Esto solo es posible si la migración tiene su operación inversa.
3. Como último recurso, restaurar el respaldo (ver [10 · Operación](10-OPERACION.md#restaurar)).
