import hashlib
import logging
import secrets
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from . import correo, legal
from .models import AltaPendiente

logger = logging.getLogger('finanzas')

HORAS_VALIDEZ = 48
ASUNTO = 'Confirma tu correo para crear tu cuenta en Fintora'


def _huella(secreto):
    return hashlib.sha256(secreto.encode('utf-8')).hexdigest()


def purgar(ahora=None):
    limite = (ahora or timezone.now()) - timedelta(hours=HORAS_VALIDEZ)
    return AltaPendiente.objects.filter(creada__lt=limite).delete()[0]


def pedir(request, username, clave, destino, nombre=''):
    purgar()
    AltaPendiente.objects.filter(correo__iexact=destino).delete()
    secreto = secrets.token_urlsafe(32)
    AltaPendiente.objects.create(
        correo=destino, username=username, password=make_password(clave),
        nombre_completo=(nombre or '')[:100], politica_version=legal.VERSION,
        token=_huella(secreto),
    )
    contexto = {
        'username': username,
        'enlace': correo.url_absoluta(request, reverse('confirmar_alta', kwargs={'token': secreto})),
        'horas': HORAS_VALIDEZ,
    }
    ok = correo.enviar(destino, ASUNTO,
                       render_to_string('registration/correo_alta.txt', contexto),
                       render_to_string('registration/correo_alta.html', contexto))
    if not ok:
        logger.error('No salió el correo para confirmar un registro')
    return ok


def buscar(secreto):
    if not secreto or len(secreto) > 100:
        return None
    alta = AltaPendiente.objects.filter(token=_huella(secreto)).first()
    if alta is None:
        return None
    if alta.creada < timezone.now() - timedelta(hours=HORAS_VALIDEZ):
        alta.delete()
        return None
    return alta
