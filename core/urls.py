from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin, messages
from django.contrib.auth.views import redirect_to_login
from django.http import Http404
from django.shortcuts import redirect
from django.urls import include, path, reverse
from django.utils.http import url_has_allowed_host_and_scheme

RUTA_ADMIN = settings.ADMIN_URL


def tiene_2fa(usuario):
    from finanzas.models import SegundoFactor
    return SegundoFactor.objects.filter(usuario=usuario, activo=True).exists()


_permiso_base = admin.site.has_permission


def permiso_admin(request):
    return _permiso_base(request) and tiene_2fa(request.user)


def entrada_admin(request, extra_context=None):
    destino = request.GET.get('next') or reverse('admin:index')
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        destino = reverse('admin:index')

    usuario = request.user
    if usuario.is_authenticated and usuario.is_active and usuario.is_staff:
        if not tiene_2fa(usuario):
            from finanzas import auditoria
            auditoria.registrar('admin_denegado', request, detalle='sin verificación en dos pasos')
            messages.warning(request, 'Para entrar a la administración activa antes '
                                      'la verificación en dos pasos.')
            return redirect('configurar_2fa')
        return redirect(destino)
    if usuario.is_authenticated:
        from finanzas import auditoria
        auditoria.registrar('admin_denegado', request)
        raise Http404
    return redirect_to_login(destino, settings.LOGIN_URL)


admin.site.login = entrada_admin
admin.site.has_permission = permiso_admin

urlpatterns = []
if RUTA_ADMIN:
    urlpatterns.append(path(f'{RUTA_ADMIN}/', admin.site.urls))

urlpatterns.append(path('', include('finanzas.urls')))

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
