from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('finanzas.urls')),
]

# Servir los archivos subidos en desarrollo. static() se anula solo cuando
# DEBUG es False, así que en producción no expone nada: ahí las fotos las
# sirve R2 (o el mapeo de /media/ del hosting).
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
