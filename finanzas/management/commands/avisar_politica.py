import logging
import time

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from finanzas import correo, legal
from finanzas.models import UserProfile

logger = logging.getLogger('finanzas')

ASUNTO = 'Actualizamos la política de privacidad de Fintora'


def destinatario(usuario, perfil):
    return usuario.email or perfil.email or ''


class Command(BaseCommand):
    help = 'Avisa por correo a cada cuenta que cambia la política de privacidad.'

    def add_arguments(self, parser):
        parser.add_argument('--seco', action='store_true', help='Muestra a cuántos avisaría, sin enviar.')
        parser.add_argument('--usuario', help='Solo a esta cuenta, para probar.')
        parser.add_argument('--limite', type=int, default=0, help='Como máximo esta cantidad de correos.')
        parser.add_argument('--pausa', type=float, default=0.6, help='Segundos entre correos.')

    def handle(self, *args, **opciones):
        version = legal.VERSION
        cuentas = User.objects.filter(is_active=True).order_by('pk')
        if opciones['usuario']:
            cuentas = cuentas.filter(username=opciones['usuario'])

        pendientes, sin_correo = [], 0
        for usuario in cuentas:
            perfil, _ = UserProfile.objects.get_or_create(usuario=usuario)
            if perfil.politica_avisada == version:
                continue
            destino = destinatario(usuario, perfil)
            if not destino:
                sin_correo += 1
                continue
            pendientes.append((usuario, perfil, destino))
        if opciones['limite'] > 0:
            pendientes = pendientes[:opciones['limite']]

        if opciones['seco']:
            self.stdout.write(f'{len(pendientes)} cuentas por avisar de la versión {version} '
                              f'({sin_correo} sin correo). No se envió nada.')
            return

        contexto = {
            'version': version,
            'vigente_desde': legal.VIGENTE_DESDE,
            'cambios': legal.CAMBIOS,
            'correo_contacto': legal.CORREO_CONTACTO,
            'enlace': correo.url_absoluta_sin_request('/privacidad/'),
            'enlace_perfil': correo.url_absoluta_sin_request('/perfil/'),
        }
        enviados = fallidos = 0
        for n, (usuario, perfil, destino) in enumerate(pendientes):
            if n and opciones['pausa'] > 0:
                time.sleep(opciones['pausa'])
            datos = {**contexto, 'usuario': usuario}
            ok = correo.enviar(destino, ASUNTO,
                               render_to_string('finanzas/correo_politica.txt', datos),
                               render_to_string('finanzas/correo_politica.html', datos))
            if not ok:
                fallidos += 1
                logger.warning('No salió el aviso de la política a la cuenta %s', usuario.pk)
                continue
            perfil.politica_avisada = version
            perfil.save(update_fields=['politica_avisada'])
            enviados += 1

        estilo = self.style.SUCCESS if not fallidos else self.style.WARNING
        self.stdout.write(estilo(f'Política {version}: {enviados} enviados, {fallidos} no salieron, '
                                 f'{sin_correo} sin correo.'))
