import logging

from django.core import signing
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from . import correo

log = logging.getLogger('finanzas')

SAL = 'finanzas.correo.verificacion'
HORAS_VALIDEZ = 48
MAX_EDAD = HORAS_VALIDEZ * 3600


def token(usuario):
    return signing.dumps(
        {'uid': usuario.pk, 'correo': (usuario.email or '').strip().lower()},
        salt=SAL)


def usuario_de(cadena):
    try:
        datos = signing.loads(cadena, salt=SAL, max_age=MAX_EDAD)
    except signing.BadSignature:
        return None

    usuario = User.objects.filter(pk=datos.get('uid'), is_active=True).first()
    if not usuario:
        return None
    if (usuario.email or '').strip().lower() != datos.get('correo'):
        return None
    return usuario


def enlace(request, usuario):
    return correo.url_absoluta(
        request, reverse('verificar_correo', kwargs={'token': token(usuario)}))


def enviar(request, usuario):
    destino = (usuario.email or '').strip()
    if not destino:
        return False

    contexto = {
        'usuario': usuario,
        'enlace': enlace(request, usuario),
        'horas': HORAS_VALIDEZ,
    }
    ok = correo.enviar(
        destino,
        'Confirma tu correo en Rekon',
        render_to_string('registration/correo_verificar.txt', contexto),
        render_to_string('registration/correo_verificar.html', contexto),
    )
    if not ok:
        log.error('No salió el correo de verificación del usuario %s', usuario.pk)
    return ok


def marcar(perfil):
    perfil.correo_verificado = True
    perfil.correo_verificado_en = timezone.now()
    perfil.save(update_fields=['correo_verificado', 'correo_verificado_en'])
