import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

# El admin de Django en /admin/ recibe escaneo automatizado desde el primer
# día que el dominio es público: es la ruta que prueban todos los bots. No es
# que sea insegura, es que regala un formulario de acceso contra el que
# probar contraseñas, y además el middleware de política de contenido lo deja
# fuera de la CSP. Moverlo a una ruta que solo tú sabes no es seguridad de
# verdad, pero saca la app del barrido indiscriminado.
#
# ADMIN_URL en el entorno, sin barras: por ejemplo 'panel-9f3a2c'.
# ADMIN_URL vacío lo desactiva por completo, que es lo correcto si no lo usas.
RUTA_ADMIN = os.environ.get('ADMIN_URL', 'admin').strip('/')

urlpatterns = []
if RUTA_ADMIN:
    urlpatterns.append(path(f'{RUTA_ADMIN}/', admin.site.urls))

urlpatterns.append(path('', include('finanzas.urls')))

# Servir los archivos subidos en desarrollo. static() se anula solo cuando
# DEBUG es False, así que en producción no expone nada: ahí las fotos las
# sirve R2 (o el mapeo de /media/ del hosting).
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
