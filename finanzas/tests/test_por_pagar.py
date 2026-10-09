from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import Deuda, Persona, Prestamo, Suscripcion, Transaccion


class PorPagarTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.hoy = date.today()
        self.inicio = self.hoy.replace(day=1)

    def test_junta_cuotas_suscripciones_gastos_y_personas(self):
        Deuda.objects.create(usuario=self.ana, acreedor='Notebook', monto_total=Decimal('120000'),
                             cuotas_totales=12, fecha_inicio=self.inicio)
        Suscripcion.objects.create(usuario=self.ana, nombre='Spotify', monto=Decimal('5990'),
                                   dia_cobro=28, fecha_inicio=self.inicio)
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('38450'),
                                   categoria='Servicios', fecha=self.hoy, descripcion='Luz', pagado=False)
        carla = Persona.objects.create(usuario=self.ana, nombre='Carla', lado='LE_DEBO')
        Prestamo.objects.create(persona=carla, descripcion='Pasaje', monto=Decimal('20000'),
                                tipo='UNICO', cuotas_totales=1)
        r = self.client.get(reverse('por_pagar'))
        self.assertEqual(r.status_code, 200)
        for nombre in ('Notebook', 'Spotify', 'Luz', 'Carla'):
            self.assertContains(r, nombre)
        filtros = {f['clave']: f['cuantos'] for f in r.context['filtros']}
        self.assertEqual(filtros['cuota'], 1)
        self.assertEqual(filtros['servicio'], 1)
        self.assertEqual(filtros['cuenta'], 1)
        self.assertEqual(filtros['debo'], 1)

    def test_lo_atrasado_va_primero_y_lo_pagado_al_final(self):
        if self.hoy.day == 1:
            return
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('9000'),
                                   categoria='Otros', fecha=self.inicio, descripcion='Atrasado', pagado=False)
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('1000'),
                                   categoria='Otros', fecha=self.hoy, descripcion='Hoy', pagado=False)
        r = self.client.get(reverse('por_pagar'))
        claves = [s[0] for s in r.context['secciones']]
        self.assertEqual(claves[0], 'atrasado')
        self.assertEqual(r.context['falta'], Decimal('10000'))

    def test_pagar_desde_aqui_vuelve_a_la_misma_pantalla(self):
        t = Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('5000'),
                                       categoria='Otros', fecha=self.hoy, descripcion='Pan', pagado=False)
        destino = reverse('por_pagar')
        r = self.client.post(reverse('pagar_gasto', args=[t.pk]), {'next': destino})
        self.assertRedirects(r, destino, fetch_redirect_response=False)
        t.refresh_from_db()
        self.assertTrue(t.pagado)

    def test_sin_nada_muestra_el_vacio(self):
        r = self.client.get(reverse('por_pagar'))
        self.assertContains(r, 'Nada por pagar')

    def test_la_barra_inferior_lleva_a_por_pagar(self):
        html = self.client.get(reverse('metas')).content.decode()
        barra = html[html.index('class="bottomnav"'):]
        barra = barra[:barra.index('</nav>')]
        self.assertIn(reverse('por_pagar'), barra)
        self.assertNotIn(f'href="{reverse("deudas")}"', barra)

    def test_no_muestra_lo_de_otra_persona(self):
        bruno = User.objects.create_user('bruno', 'bruno@ejemplo.cl', 'clave-larga-2')
        Transaccion.objects.create(usuario=bruno, tipo='EGRESO', monto=Decimal('777'),
                                   categoria='Otros', fecha=self.hoy, descripcion='Ajeno', pagado=False)
        self.assertNotContains(self.client.get(reverse('por_pagar')), 'Ajeno')
