from django.core.management.base import BaseCommand
from django.utils import timezone

from finanzas import auditoria, inactividad


class Command(BaseCommand):
    help = 'Avisa a las cuentas inactivas y borra las que no volvieron.'

    def add_arguments(self, parser):
        parser.add_argument('--seco', action='store_true',
                            help='No envía ni borra: solo informa.')
        parser.add_argument('--usuario', default=None, help='Limitar a un username.')
        parser.add_argument('--solo-avisos', action='store_true',
                            help='Manda avisos pero no borra ninguna cuenta.')

    def handle(self, *args, **opciones):
        ahora = timezone.now()
        seco = opciones['seco']
        uno = opciones['usuario']

        self.stdout.write(
            f'Plazo: {inactividad.MESES} meses sin usar la app, '
            f'{inactividad.DIAS_GRACIA} días de gracia tras el aviso.')

        avisados = fallidos = 0
        for cuenta, perfil in inactividad.por_avisar(ahora, uno):
            dias = inactividad.dias_inactivo(cuenta, perfil, ahora)
            destino = inactividad.destinatario(cuenta, perfil) or 'sin correo'
            if seco:
                self.stdout.write(f'  avisaría a {cuenta.username} → {destino} ({dias} días)')
                continue
            if inactividad.avisar(cuenta, perfil, ahora):
                avisados += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  aviso a {cuenta.username} → {destino} ({dias} días)'))
            else:
                fallidos += 1
                self.stdout.write(self.style.ERROR(
                    f'  {cuenta.username}: el aviso no salió (ver el log de finanzas)'))

        borrados = 0
        if not opciones['solo_avisos']:
            for cuenta, perfil in inactividad.por_borrar(ahora, uno):
                dias = inactividad.dias_inactivo(cuenta, perfil, ahora)
                if seco:
                    self.stdout.write(
                        f'  borraría a {cuenta.username} ({dias} días sin entrar)')
                    continue
                self.stdout.write(self.style.WARNING(
                    f'  borrando {cuenta.username} ({dias} días sin entrar)'))
                inactividad.borrar(cuenta, perfil)
                borrados += 1

        resumen = f'{avisados} aviso(s), {borrados} cuenta(s) borrada(s)'
        if fallidos:
            resumen += f', {fallidos} aviso(s) con error'
        if seco:
            resumen = 'Simulación: no se envió ni se borró nada.'
        else:
            eventos = auditoria.purgar(ahora)
            resumen += f', {eventos} evento(s) de seguridad de más de {auditoria.DIAS_CONSERVACION} días borrado(s)'
        self.stdout.write(self.style.WARNING(resumen))
