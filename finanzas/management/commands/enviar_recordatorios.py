import logging
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import connection, connections
from django.utils import timezone

from finanzas import push
from finanzas.models import UserProfile
from finanzas.servicios.recordatorios import avisos_del_dia
from finanzas.views.comun import simbolo_de

logger = logging.getLogger('finanzas')


class Command(BaseCommand):
    help = 'Manda los recordatorios del día a los aparatos que los activaron.'

    def add_arguments(self, parser):
        parser.add_argument('--forzar', action='store_true',
                            help='Manda aunque ya se haya enviado hoy.')
        parser.add_argument('--hilos', type=int, default=1,
                            help='Cuentas que se atienden a la vez (por defecto 1).')

    def handle(self, *args, **opciones):
        if not push.disponible():
            self.stdout.write(self.style.WARNING('Falta VAPID_PRIVADA: no se manda nada.'))
            return
        hoy = timezone.localdate()
        forzar = opciones['forzar']
        hilos = max(1, opciones['hilos'])
        if connection.vendor == 'sqlite':
            hilos = 1
        usuarios = list(User.objects.filter(suscripciones_push__isnull=False, is_active=True).distinct())

        def atender(usuario):
            try:
                return self._atender(usuario, hoy, forzar)
            finally:
                if hilos > 1:
                    connections.close_all()

        if hilos > 1:
            with ThreadPoolExecutor(max_workers=hilos) as grupo:
                resultados = list(grupo.map(atender, usuarios))
        else:
            resultados = [atender(u) for u in usuarios]

        hechos = [r for r in resultados if r]
        personas = sum(1 for con_avisos, _ in hechos if con_avisos)
        enviados = sum(n for _, n in hechos)
        self.stdout.write(self.style.SUCCESS(
            f'Recordatorios: {enviados} avisos a {personas} persona{"s" if personas != 1 else ""}.'))

    def _atender(self, usuario, hoy, forzar):
        perfil, _ = UserProfile.objects.get_or_create(usuario=usuario)
        if perfil.push_ultimo_dia == hoy and not forzar:
            return None
        try:
            avisos = avisos_del_dia(usuario, perfil, hoy, simbolo_de(usuario))
            enviados = sum(push.enviar_a_usuario(usuario, aviso) for aviso in avisos)
        except Exception:
            logger.exception('No se pudieron armar los recordatorios del usuario %s', usuario.pk)
            return None
        perfil.push_ultimo_dia = hoy
        perfil.save(update_fields=['push_ultimo_dia'])
        return bool(avisos), enviados
