"""Manda el aviso mensual de pagos pendientes.

Pensado para una tarea diaria del hosting (en PythonAnywhere, "Tasks" →
diaria a las 13:00 UTC, que en Chile son las 9 o 10 de la mañana):

    python manage.py avisar_pagos

Corre todos los días y no hace nada salvo cuando es el día que el usuario
eligió — 20 por defecto. Así un solo horario sirve para todos y no hay que
tocar el hosting cuando alguien cambia su día.

El registro del último mes enviado (perfil.aviso_ultimo_periodo) es lo que
evita el correo repetido si la tarea se ejecuta dos veces el mismo día.

    --forzar            ignora el día y el registro; manda ahora
    --seco              no envía: solo dice a quién le tocaría y con qué
    --usuario <nombre>  solo esa cuenta
"""
from datetime import date

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from finanzas import avisos
from finanzas.models import UserProfile


class Command(BaseCommand):
    help = 'Envía el aviso mensual de pagos pendientes a quien le corresponda hoy.'

    def add_arguments(self, parser):
        parser.add_argument('--forzar', action='store_true',
                            help='Ignora el día configurado y el registro de envío.')
        parser.add_argument('--seco', action='store_true',
                            help='No envía nada: solo informa qué haría.')
        parser.add_argument('--usuario', default=None,
                            help='Limitar a un username.')

    def handle(self, *args, **opciones):
        hoy = date.today()
        periodo = avisos.periodo_de(hoy)
        forzar = opciones['forzar']
        seco = opciones['seco']

        cuentas = User.objects.filter(is_active=True).select_related('profile')
        if opciones['usuario']:
            cuentas = cuentas.filter(username=opciones['usuario'])

        enviados = omitidos = fallidos = 0

        for usuario in cuentas:
            perfil = getattr(usuario, 'profile', None)
            if perfil is None:
                perfil = UserProfile.objects.create(usuario=usuario)

            if not perfil.aviso_mensual:
                omitidos += 1
                continue

            if not forzar:
                if hoy.day != perfil.dia_aviso_efectivo:
                    omitidos += 1
                    continue
                if perfil.aviso_ultimo_periodo == periodo:
                    omitidos += 1
                    continue

            destino = avisos.destinatario(usuario)
            if not destino:
                self.stdout.write(f'  {usuario.username}: sin email guardado')
                omitidos += 1
                continue

            # Los cobros de suscripciones se generan al abrir el dashboard.
            # Si el usuario no entró este mes, el cobro de septiembre todavía
            # no existe y el aviso saldría incompleto.
            from finanzas.views import generar_cobros_suscripciones
            generar_cobros_suscripciones(usuario)

            datos = avisos.resumen(usuario, hoy)
            if not datos['hay_algo']:
                self.stdout.write(f'  {usuario.username}: nada por pagar, no se envía')
                omitidos += 1
                continue

            if seco:
                self.stdout.write(
                    f"  {usuario.username} → {destino}: {datos['cantidad']} pagos, "
                    f"{datos['total']}")
                continue

            if avisos.enviar_a(usuario, hoy):
                perfil.aviso_ultimo_periodo = periodo
                perfil.save(update_fields=['aviso_ultimo_periodo'])
                enviados += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  {usuario.username} → {destino}: {datos['cantidad']} pagos, "
                    f"{datos['total']}"))
            else:
                # Sin marcar el periodo: así el próximo intento reintenta en
                # vez de dar el mes por avisado.
                fallidos += 1
                self.stdout.write(self.style.ERROR(
                    f'  {usuario.username}: el envío falló (ver el log de finanzas)'))

        resumen = f'{enviados} enviado(s), {omitidos} omitido(s)'
        if fallidos:
            resumen += f', {fallidos} con error'
        self.stdout.write(self.style.WARNING(resumen))
