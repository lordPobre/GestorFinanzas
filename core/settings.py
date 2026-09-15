import os
import sys
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    load_dotenv(os.path.join(BASE_DIR, '.env'))
except ImportError:
    pass  

# ==========================================================
#  SEGURIDAD — valores sensibles vienen de variables de entorno
# ==========================================================
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# `collectstatic` corre en la etapa de construcción, donde el hosting todavía
# no inyecta las variables del servicio. No toca la base ni firma nada, así
# que exigirle SECRET_KEY solo hace fallar el build. Se le permite arrancar
# con una clave de mentira; el guardia del final del archivo sigue cubriendo
# al proceso que de verdad atiende peticiones.
_SOLO_ESTATICOS = 'collectstatic' in sys.argv

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG or _SOLO_ESTATICOS:
        SECRET_KEY = 'django-insecure-solo-desarrollo-local'
    else:
        raise RuntimeError(
            'Falta SECRET_KEY. En producción no hay valor por defecto: '
            'con la clave del repositorio se pueden forjar sesiones.'
        )


ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get(
        'ALLOWED_HOSTS',
        'localhost,127.0.0.1,finanzas.pythonanywhere.com,www.finanzas.pythonanywhere.com'
    ).split(',') if h.strip()
]

# Railway publica el dominio del servicio en RAILWAY_PUBLIC_DOMAIN y cambia
# cuando se conecta un dominio propio. Se agrega solo para no tener que
# editar ALLOWED_HOSTS a mano en cada despliegue.
DOMINIO_RAILWAY = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '').strip()
if DOMINIO_RAILWAY and DOMINIO_RAILWAY not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(DOMINIO_RAILWAY)


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'finanzas',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'finanzas.middleware.PoliticaContenidoMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'finanzas.context_processors.moneda_usuario',   
                'finanzas.middleware.nonce_contexto',
                'finanzas.google_login.google_disponible',
            ],
        },
    },
]
WSGI_APPLICATION = 'core.wsgi.application'

database_url = os.environ.get("DATABASE_URL")

# Exigir SSL a la base es lo correcto cuando se cruza internet, pero no
# cuando la base vive en la red privada del hosting: el Postgres interno de
# Railway se alcanza por `postgres.railway.internal` y ahí puede rechazar el
# handshake TLS, con lo que la app no arranca. DB_SSL=0 lo desactiva sin
# tocar código; el tráfico igual no sale de la red privada.
DB_SSL = os.environ.get('DB_SSL', '1').lower() not in ('0', 'false', 'no')

if database_url:
    DATABASES = {
        'default': dj_database_url.parse(
            database_url,
            conn_max_age=600,
            ssl_require=DB_SSL and not DEBUG,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }

# Modo WAL para SQLite: sin esto, cada escritura bloquea toda la base — un
# solo usuario guardando un gasto deja a todos los demás esperando. WAL
# permite lecturas concurrentes mientras alguien escribe, que es el caso
# real de la app (mucha gente mirando su dashboard, pocos escribiendo a la
# vez). No aplica si ya se usa Postgres (database_url), que maneja esto
# nativamente.
if not database_url:
    from django.db.backends.signals import connection_created

    def _activar_wal(sender, connection, **kwargs):
        if connection.vendor == 'sqlite':
            cursor = connection.cursor()
            cursor.execute('PRAGMA journal_mode=WAL;')
            cursor.execute('PRAGMA synchronous=NORMAL;')
            # Si dos escrituras chocan, reintenta hasta 5s en vez de fallar
            # de inmediato con "database is locked".
            cursor.execute('PRAGMA busy_timeout=5000;')

    connection_created.connect(_activar_wal)

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = 'static/'
STATICFILES_DIRS = [ BASE_DIR / 'static' ]

# Archivos que sube el usuario (hoy solo la foto de perfil).
#
# Faltaban por completo. Sin MEDIA_URL, FileSystemStorage.url() devuelve la
# ruta suelta ("avatares/3/ab12cd34.jpg"), que el navegador resuelve contra
# la página actual — /perfil/avatares/3/... — y da 404: la foto se subía
# bien pero no había forma de mostrarla cuando R2 no está configurado.
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
LOGIN_URL = 'login'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==========================================================
#  ESCUDOS DE SEGURIDAD 
# ==========================================================

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_REFERRER_POLICY = 'same-origin'

    SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

    CSRF_TRUSTED_ORIGINS = [
        o.strip() for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
        if o.strip()
    ]

    # El dominio de Railway también tiene que ser origen de confianza, o los
    # formularios POST se rechazan por CSRF apenas se despliega.
    if DOMINIO_RAILWAY:
        origen = f'https://{DOMINIO_RAILWAY}'
        if origen not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origen)

# Cuántos proxies de confianza hay delante de la app. Railway pone uno.
# seguridad.py lo usa para saber qué parte de X-Forwarded-For creer: ese
# encabezado lo puede escribir cualquiera, y solo los tramos que agrega la
# infraestructura propia son fiables. En local, 0.
PROXIES_CONFIABLES = int(os.environ.get('PROXIES_CONFIABLES', '0' if DEBUG else '1'))

# Acceso con cuenta de Google (ver finanzas/google_login.py). Si no están,
# el botón no se dibuja y el acceso con usuario y contraseña sigue igual.
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')

SESSION_COOKIE_AGE = 60 * 60 * 8         
SESSION_SAVE_EVERY_REQUEST = True        
SESSION_EXPIRE_AT_BROWSER_CLOSE = False 

DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024   
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

# La revisión de cartola manda varios campos por movimiento (marca,
# descripción, categoría, y los extras de cuotas, suscripción y "Me deben").
# Con 500 una cartola de más de ~70 líneas se caía con TooManyFieldsSent.
# 3000 cubre un extracto largo; el tamaño sigue topado por DATA_UPLOAD_MAX_MEMORY_SIZE.
DATA_UPLOAD_MAX_NUMBER_FIELDS = 3000

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# Cuánto vale un enlace de recuperación de contraseña. Django trae tres
# días por defecto, que para una app con datos financieros es demasiado:
# un correo olvidado abierto en un equipo ajeno sigue siendo una llave
# válida durante todo ese tiempo.
PASSWORD_RESET_TIMEOUT = 60 * 60   # 1 hora

# El correo sale por una API HTTP (ver finanzas/correo.py), no por SMTP:
# PythonAnywhere en cuenta gratuita bloquea los puertos de correo.
# Las credenciales viven en el entorno. Con Resend:
#   PROVEEDOR_CORREO=resend, RESEND_API_KEY, CORREO_FROM
# Con Mailgun:
#   PROVEEDOR_CORREO=mailgun, MAILGUN_API_KEY, MAILGUN_DOMAIN, CORREO_FROM
# En ambos casos SITE_URL para que los enlaces salgan absolutos y con https.
DEFAULT_FROM_EMAIL = os.environ.get(
    'CORREO_FROM', os.environ.get('MAILGUN_FROM', 'Rekon <no-responder@localhost>'))

# Dónde viven los contadores de seguridad.
#
# LocMemCache es memoria de UN proceso. seguridad.py ya lo advierte: con
# varios workers de gunicorn los contadores se dividen, y el tope de 5
# intentos de acceso pasa a ser 5 POR WORKER. Con dos workers son diez
# intentos reales, y el limitador de analisis_ia (6 por hora) permite doce
# llamadas pagadas. El bloqueo deja de ser el que crees que es.
#
# La caché en base de datos la comparten todos los workers. Cuesta una
# consulta por comprobación, que al lado de un Argon2 no se nota. Necesita
# la tabla una vez:  python manage.py createcachetable
#
# En local, sin DATABASE_URL, se queda en memoria: un solo proceso y sin
# tabla que crear.
if database_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'cache_finapp',
            'TIMEOUT': 300,
            'OPTIONS': {'MAX_ENTRIES': 20000, 'CULL_FREQUENCY': 4},
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'finapp',
            'TIMEOUT': 300,
            'OPTIONS': {'MAX_ENTRIES': 5000},
        }
    }

# Dónde se escribe el log de seguridad.
#
# En un contenedor (Railway, cualquier PaaS) el disco es efímero: el archivo
# se pierde en cada redespliegue, así que escribirlo ahí da una falsa
# sensación de tener registro. Solo se usa archivo si LOG_DIR apunta a algo
# persistente — un volumen montado — y en desarrollo, donde el disco es el
# tuyo. Sin LOG_DIR en producción queda solo la consola, que es lo que el
# panel del hosting recoge.
LOG_DIR = os.environ.get('LOG_DIR', '').strip() or (str(BASE_DIR) if DEBUG else '')
_DESTINOS_LOG = ['consola'] + (['archivo'] if LOG_DIR else [])

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '{asctime} {levelname} {name} {message}', 'style': '{'},
    },
    'handlers': {
        'consola': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'loggers': {
        # Intentos de acceso fallidos y peticiones sospechosas
        'django.security': {'handlers': _DESTINOS_LOG, 'level': 'WARNING'},
        # Peticiones con Host inválido, CSRF rechazado, 404 masivos
        'django.request': {'handlers': _DESTINOS_LOG, 'level': 'ERROR'},
        'finanzas': {'handlers': _DESTINOS_LOG, 'level': 'INFO'},
    },
}

if LOG_DIR:
    LOGGING['handlers']['archivo'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': os.path.join(LOG_DIR, 'seguridad.log'),
        'maxBytes': 2 * 1024 * 1024,
        'backupCount': 3,
        'formatter': 'simple',
    }

if not DEBUG and not _SOLO_ESTATICOS and 'runserver' not in sys.argv:
    if SECRET_KEY.startswith('django-insecure'):
        raise RuntimeError('SECRET_KEY de desarrollo en producción.')
