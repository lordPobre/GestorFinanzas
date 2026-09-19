"""Verificación del correo al registrarse (doble opt-in).

El correo es lo único que permite recuperar una cuenta. Si está mal escrito
—una letra de menos en el dominio— nadie se enteraba hasta el día en que la
persona olvidaba su contraseña y descubría que el enlace de recuperación se
fue a una dirección que no existe. Peor: alguien podía registrarse con el
correo de otro y dejarle avisos de pago en la bandeja.

El enlace se firma, no se guarda. Un token de django.core.signing lleva
dentro el id y el correo, y viaja firmado con SECRET_KEY: no hace falta una
tabla de tokens pendientes ni limpiarla después. Si la persona cambia su
correo antes de confirmar, el token viejo deja de calzar y no sirve.

No bloquea el acceso. Se puede usar la app sin confirmar — exigirlo dejaría
fuera a quien se registra en un computador donde no tiene su correo abierto.
Lo que hace es avisar en el perfil, y antes que eso, que el correo exista de
verdad se compruebe cuando importa.
"""
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
    """El usuario de un token válido, o None.

    Se comprueba que el correo del token siga siendo el de la cuenta: así un
    enlace enviado a la dirección anterior no confirma la nueva.
    """
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
    """Manda el correo de confirmación. True si el proveedor lo aceptó."""
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
    """Deja registrado que el correo quedó confirmado."""
    perfil.correo_verificado = True
    perfil.correo_verificado_en = timezone.now()
    perfil.save(update_fields=['correo_verificado', 'correo_verificado_en'])
