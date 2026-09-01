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
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-solo-desarrollo-local'
    else:
        raise RuntimeError(
            'Falta SECRET_KEY. En producción no hay valor por defecto: '
            'con la clave del repositorio se pueden forjar sesiones.'
        )


ALLOWED_HOSTS = os.environ.get(
    'ALLOWED_HOSTS',
    'localhost,127.0.0.1,finanzas.pythonanywhere.com,www.finanzas.pythonanywhere.com'
).split(',')


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
            ],
        },
    },
]
WSGI_APPLICATION = 'core.wsgi.application'

database_url = os.environ.get("DATABASE_URL")

if database_url:
    DATABASES = {
        'default': dj_database_url.parse(
            database_url,
            conn_max_age=600,
            ssl_require=not DEBUG,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }

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

SESSION_COOKIE_AGE = 60 * 60 * 8         
SESSION_SAVE_EVERY_REQUEST = True        
SESSION_EXPIRE_AT_BROWSER_CLOSE = False 

DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024   
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

DATA_UPLOAD_MAX_NUMBER_FIELDS = 500

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'finapp',
        'TIMEOUT': 300,
        'OPTIONS': {'MAX_ENTRIES': 5000},
    }
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '{asctime} {levelname} {name} {message}', 'style': '{'},
    },
    'handlers': {
        'consola': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
        'archivo': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'seguridad.log'),
            'maxBytes': 2 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'simple',
        },
    },
    'loggers': {
        # Intentos de acceso fallidos y peticiones sospechosas
        'django.security': {'handlers': ['consola', 'archivo'], 'level': 'WARNING'},
        # Peticiones con Host inválido, CSRF rechazado, 404 masivos
        'django.request': {'handlers': ['consola', 'archivo'], 'level': 'ERROR'},
        'finanzas': {'handlers': ['consola', 'archivo'], 'level': 'INFO'},
    },
}

if not DEBUG and 'runserver' not in sys.argv:
    if SECRET_KEY.startswith('django-insecure'):
        raise RuntimeError('SECRET_KEY de desarrollo en producción.')
