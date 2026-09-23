from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import redirect_to_login
from django.http import Http404
from django.shortcuts import redirect
from django.urls import include, path, reverse
from django.utils.http import url_has_allowed_host_and_scheme

RUTA_ADMIN = settings.ADMIN_URL


def entrada_admin(request, extra_context=None):
    destino = request.GET.get('next') or reverse('admin:index')
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        destino = reverse('admin:index')

    usuario = request.user
    if usuario.is_authenticated and usuario.is_active and usuario.is_staff:
        return redirect(destino)
    if usuario.is_authenticated:
        from finanzas import auditoria
        auditoria.registrar('admin_denegado', request)
        raise Http404
    return redirect_to_login(destino, settings.LOGIN_URL)


admin.site.login = entrada_admin

urlpatterns = []
if RUTA_ADMIN:
    urlpatterns.append(path(f'{RUTA_ADMIN}/', admin.site.urls))

urlpatterns.append(path('', include('finanzas.urls')))

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
