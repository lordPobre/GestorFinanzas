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

DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

_SOLO_ESTATICOS = 'collectstatic' in sys.argv

if sys.argv[1:2] == ['test']:
    for _clave in ('RESEND_API_KEY', 'MAILGUN_API_KEY', 'MAILGUN_DOMAIN', 'PROVEEDOR_CORREO'):
        os.environ.pop(_clave, None)

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

DOMINIO_RAILWAY = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '').strip()
if DOMINIO_RAILWAY and DOMINIO_RAILWAY not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(DOMINIO_RAILWAY)

for _host in ('healthcheck.railway.app', '.railway.internal'):
    if _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)

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
    'finanzas.middleware.ActividadMiddleware',
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
                'finanzas.context_processors.entorno',
                'finanzas.middleware.nonce_contexto',
                'finanzas.legal.datos_legales',
                'finanzas.google_login.google_disponible',
            ],
        },
    },
]
WSGI_APPLICATION = 'core.wsgi.application'

database_url = os.environ.get("DATABASE_URL")

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

if not database_url:
    from django.db.backends.signals import connection_created

    def _activar_wal(sender, connection, **kwargs):
        if connection.vendor == 'sqlite':
            cursor = connection.cursor()
            cursor.execute('PRAGMA journal_mode=WAL;')
            cursor.execute('PRAGMA synchronous=NORMAL;')
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

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}

LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
LOGIN_URL = 'login'

ADMIN_URL = os.environ.get('ADMIN_URL', '').strip().strip('/')
WEBAUTHN_RP_ID = os.environ.get('WEBAUTHN_RP_ID', '').strip()

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    SECURE_REDIRECT_EXEMPT = [r'^salud/$']
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

    if DOMINIO_RAILWAY:
        origen = f'https://{DOMINIO_RAILWAY}'
        if origen not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origen)

PROXIES_CONFIABLES = int(os.environ.get('PROXIES_CONFIABLES', '0' if DEBUG else '1'))

ENTORNO = os.environ.get('ENTORNO', 'produccion').strip().lower()
ES_STAGING = ENTORNO in ('staging', 'pruebas', 'preproduccion')

CORREO_EN_STAGING = os.environ.get('CORREO_EN_STAGING', '').lower() in ('1', 'true', 'si')

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')

SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

DATA_UPLOAD_MAX_NUMBER_FIELDS = 3000

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

PASSWORD_RESET_TIMEOUT = 60 * 60

DEFAULT_FROM_EMAIL = os.environ.get(
    'CORREO_FROM', os.environ.get('MAILGUN_FROM', 'Rekon <no-responder@localhost>'))

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
        'django.security': {'handlers': _DESTINOS_LOG, 'level': 'WARNING'},
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

SENTRY_DSN = os.environ.get('SENTRY_DSN', '').strip()
if SENTRY_DSN and not _SOLO_ESTATICOS:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            send_default_pii=False,
            traces_sample_rate=0.0,
            environment=os.environ.get('ENTORNO', 'produccion'),
            release=os.environ.get('RAILWAY_GIT_COMMIT_SHA', '')[:12] or None,
        )
    except ImportError:
        pass
