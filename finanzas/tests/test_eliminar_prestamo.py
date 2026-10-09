from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import AbonoPrestamo, Persona, Prestamo


class EliminarPrestamoTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.camila = Persona.objects.create(usuario=self.ana, nombre='Camila', lado='ME_DEBE')
        self.arriendo = Prestamo.objects.create(persona=self.camila, descripcion='Arriendo',
                                                monto=Decimal('180000'), tipo='UNICO', cuotas_totales=1)
        self.pasaje = Prestamo.objects.create(persona=self.camila, descripcion='Pasaje',
                                              monto=Decimal('20000'), tipo='UNICO', cuotas_totales=1)

    def test_cada_prestamo_tiene_su_boton_de_eliminar(self):
        r = self.client.get(reverse('detalle_persona', args=[self.camila.pk]))
        self.assertContains(r, reverse('eliminar_prestamo', args=[self.arriendo.pk]))
        self.assertContains(r, reverse('eliminar_prestamo', args=[self.pasaje.pk]))

    def test_borra_solo_ese_prestamo_y_sus_abonos(self):
        AbonoPrestamo.objects.create(prestamo=self.arriendo, monto=Decimal('50000'))
        detalle = reverse('detalle_persona', args=[self.camila.pk])
        r = self.client.post(reverse('eliminar_prestamo', args=[self.arriendo.pk]), {'next': detalle})
        self.assertRedirects(r, detalle, fetch_redirect_response=False)
        self.assertFalse(Prestamo.objects.filter(pk=self.arriendo.pk).exists())
        self.assertFalse(AbonoPrestamo.objects.filter(prestamo_id=self.arriendo.pk).exists())
        self.assertTrue(Prestamo.objects.filter(pk=self.pasaje.pk).exists())
        self.assertTrue(Persona.objects.filter(pk=self.camila.pk).exists())

    def test_sin_next_vuelve_al_detalle_de_la_persona(self):
        r = self.client.post(reverse('eliminar_prestamo', args=[self.pasaje.pk]))
        self.assertRedirects(r, reverse('detalle_persona', args=[self.camila.pk]),
                             fetch_redirect_response=False)

    def test_no_borra_prestamos_de_otra_persona(self):
        bruno = User.objects.create_user('bruno', 'bruno@ejemplo.cl', 'clave-larga-2')
        self.client.force_login(bruno)
        r = self.client.post(reverse('eliminar_prestamo', args=[self.arriendo.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(Prestamo.objects.filter(pk=self.arriendo.pk).exists())
