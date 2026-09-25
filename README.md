# Rekon — gestor de finanzas personales

Aplicación web para llevar el control del dinero del mes: ingresos, gastos,
compras en cuotas, préstamos por cobrar, suscripciones y metas de ahorro.
Django 5 con plantillas del servidor, sin framework de front-end. Instalable
como aplicación en el teléfono (PWA).

## Qué hace

| Pantalla | Para qué |
| --- | --- |
| Inicio | Lo que entró, lo que salió y lo que queda libre este mes |
| Cuotas | Compras a plazo, mes por mes, con estado de cada cobro |
| Me deben | Personas, préstamos y abonos |
| Suscripciones | Cobros recurrentes y su pago mensual |
| Estadísticas | Gasto por categoría y evolución |
| Análisis | Diagnóstico con motor propio, e interpretación con IA si hay clave |
| Cartolas | Importa un extracto bancario en PDF, Excel o CSV y lo clasifica |
| Perfil | Cuenta, seguridad, exportaciones y borrado de datos |

## Levantar el entorno

Requiere Python 3.13.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env             # y rellena lo que necesites
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Sin `DATABASE_URL` usa SQLite local con modo WAL. Sin credenciales de R2 las
fotos van al disco. Sin `ANTHROPIC_API_KEY` el análisis muestra solo los
números del motor determinístico. Nada de eso hace falta para desarrollar.

En `.env` basta con `DEBUG=True`.

## Variables de entorno

`.env.example` es la lista completa y comentada. Las imprescindibles en
producción:

| Variable | Para qué |
| --- | --- |
| `SECRET_KEY` | Firma de sesiones. Sin ella la app se niega a arrancar |
| `DEBUG` | `False` en producción |
| `ALLOWED_HOSTS` | Dominios propios, separados por coma |
| `DATABASE_URL` | Postgres. Sin ella, SQLite |
| `ADMIN_URL` | Ruta del panel de administración. Vacío lo desactiva |
| `CSRF_TRUSTED_ORIGINS` | Orígenes desde los que se aceptan formularios |
| `PROXIES_CONFIABLES` | Cuántos proxies hay delante. Railway: 1 |
| `SENTRY_DSN` | Monitoreo de errores. Opcional |
| `ENTORNO` | `staging` en el entorno de pruebas. Por defecto `produccion` |
| `CORREO_EN_STAGING` | `1` para que staging envíe correos de verdad. Vacío los bloquea |

## Pruebas

```bash
python manage.py test
python manage.py check --deploy
ruff check .
```

Las tres cosas corren automáticamente en cada push a `main` y en cada pull
request (`.github/workflows/ci.yml`). Un push que rompa las pruebas queda
marcado en rojo.

## Dependencias

Los rangos se declaran en `requirements.in` (producción) y
`requirements-dev.in` (ruff, coverage, pip-tools, pip-audit). Los `.txt` se
generan con versiones exactas y hashes, y el CI instala con
`--require-hashes`. Para agregar o actualizar una dependencia, edita el `.in`
y vuelve a compilar con Python 3.13:

```bash
pip-compile --generate-hashes --allow-unsafe --output-file requirements.txt requirements.in
pip-compile --generate-hashes --allow-unsafe --output-file requirements-dev.txt requirements-dev.in
```

Sube los `.in` y los `.txt` en el mismo commit.

## Desplegar

Railway, desde `main`. `railway.json` define el build
(`collectstatic`), el `preDeploy` (`migrate`), el arranque con gunicorn y la
comprobación de vida en `/salud/`.

Después del primer despliegue con Postgres, una vez:

```bash
python manage.py createcachetable
```

La caché en base de datos es la que hace que los bloqueos por intentos
fallidos cuenten igual en todos los workers.

Detalle completo en [docs/DESPLIEGUE-RAILWAY.md](docs/DESPLIEGUE-RAILWAY.md).

## Cómo está organizado

```
core/              settings, urls, wsgi
finanzas/
  models/          un archivo por tema: movimientos, cuotas, metas, suscripciones,
                   prestamos, perfil, seguridad, encuesta
  forms.py
  urls.py
  views/           una pantalla o grupo de pantallas por archivo
    comun.py       contexto compartido (menú, panel de registro) y utilidades de las vistas
    panel.py       inicio
    cuotas.py  movimientos.py  metas.py  prestamos.py  suscripciones.py
    categorias.py  estadisticas.py  analisis.py  descargas.py  sistema.py
    cuenta.py      entrar, registro, perfil, datos personales, sesiones
    cartola.py  encuesta.py  passkeys.py
  servicios/       cálculos sin request: reciben usuario y fechas, devuelven datos
    mes.py  cuotas.py  pendientes.py  suscripciones.py  panel.py
  cartolas/        un lector por banco, más uno genérico
  analisis.py      motor determinístico del diagnóstico
  ia.py            interpretación con Claude, opcional
  seguridad.py     bloqueo de intentos y límite de peticiones
  middleware.py    Content-Security-Policy con nonce
  almacenamiento.py  disco local o Cloudflare R2
  correo.py        envío por la API de Resend
  avisos.py        aviso mensual de cobros
  inactividad.py   aviso y borrado de cuentas abandonadas
  verificacion.py  confirmación del correo al registrarse
  sesiones.py      sesiones abiertas y cierre a distancia
  legal.py         versión de la política y páginas legales
  tests/           una prueba por tema (test_*.py)
static/            css, js, service worker
docs/              despliegue, respaldos, auditorías, cumplimiento
```

Una vista lee la petición, llama a `servicios/` y arma la respuesta. Un
servicio no lee `request`, no manda mensajes y no redirige.

## Tareas programadas

```bash
python manage.py avisar_pagos              # aviso mensual por correo
python manage.py limpiar_inactivas         # avisa y borra cuentas abandonadas
python manage.py respaldar                 # copia de seguridad
python manage.py limpiar_avatares_huerfanos
```

`limpiar_inactivas` corre a diario y no hace nada la mayoría de los días:
avisa a los 12 meses sin uso y borra 30 días después de ese aviso. Con
`--seco` dice qué haría sin enviar ni borrar nada.

## Documentación

- [docs/DESPLIEGUE-RAILWAY.md](docs/DESPLIEGUE-RAILWAY.md) — puesta en producción
- [docs/RESPALDOS.md](docs/RESPALDOS.md) — copias y restauración
- [docs/MIGRACION-POSTGRES.md](docs/MIGRACION-POSTGRES.md) — paso desde SQLite
- [docs/AUDITORIA-SEGURIDAD.md](docs/AUDITORIA-SEGURIDAD.md) — revisión de vulnerabilidades
- [docs/AUDITORIA-CUMPLIMIENTO-2026.md](docs/AUDITORIA-CUMPLIMIENTO-2026.md) — brechas de cumplimiento y plan
- [docs/REGISTRO-TRATAMIENTOS.md](docs/REGISTRO-TRATAMIENTOS.md) — qué dato personal vive dónde
- [docs/BRECHAS.md](docs/BRECHAS.md) — qué hacer ante un incidente de seguridad
- [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) — decisiones de diseño y por qué
- [docs/STAGING.md](docs/STAGING.md) — entorno de pruebas con base propia
- [docs/DECISION-CIFRADO.md](docs/DECISION-CIFRADO.md) — por qué no se cifran las descripciones
