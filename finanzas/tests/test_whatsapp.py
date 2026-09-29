from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import AbonoPrestamo, Persona, Prestamo
from ..models.prestamos import normalizar_telefono


class NormalizarTelefono(TestCase):
    def test_formatos(self):
        casos = {
            '+56 9 1234 5678': '56912345678',
            '912345678': '56912345678',
            '9 1234 5678': '56912345678',
            '(+56) 9-1234-5678': '56912345678',
            '0056912345678': '56912345678',
            '+54 9 11 2345 6789': '5491123456789',
            'camila@correo.cl': None,
            'vive en calle 123': None,
            '123': None,
            '': None,
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(normalizar_telefono(texto), esperado)


class EnlaceWhatsapp(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-segura-123')
        self.persona = Persona.objects.create(usuario=self.ana, nombre='Beto', contacto='+56 9 1234 5678')

    def _mensaje(self):
        enlace = Persona.objects.get(pk=self.persona.pk).enlace_whatsapp
        partes = urlparse(enlace)
        self.assertEqual(partes.netloc, 'wa.me')
        self.assertEqual(partes.path, '/56912345678')
        return parse_qs(partes.query)['text'][0]

    def test_el_mensaje_trae_cada_prestamo_y_el_total(self):
        Prestamo.objects.create(persona=self.persona, descripcion='Viaje', monto=Decimal('90000'),
                                tipo='CUOTAS', cuotas_totales=3)
        unico = Prestamo.objects.create(persona=self.persona, descripcion='Almuerzo', monto=Decimal('15000'))
        AbonoPrestamo.objects.create(prestamo=unico, monto=Decimal('5000'))
        texto = self._mensaje()
        self.assertIn('Hola Beto', texto)
        self.assertIn('- Viaje: $90.000 (cuota de $30.000, van 0 de 3)', texto)
        self.assertIn('- Almuerzo: $10.000', texto)
        self.assertIn('Total pendiente: $100.000', texto)
        self.assertIn('Para este mes: $40.000', texto)

    def test_no_hay_enlace_sin_deuda_o_sin_telefono(self):
        self.assertEqual(self.persona.enlace_whatsapp, '')
        Prestamo.objects.create(persona=self.persona, descripcion='Viaje', monto=Decimal('1000'))
        self.persona.contacto = 'beto@correo.cl'
        self.assertEqual(self.persona.enlace_whatsapp, '')

    def test_el_boton_aparece_en_la_pantalla(self):
        Prestamo.objects.create(persona=self.persona, descripcion='Viaje', monto=Decimal('1000'))
        self.client.force_login(self.ana)
        respuesta = self.client.get(reverse('detalle_persona', args=[self.persona.pk]))
        self.assertContains(respuesta, 'https://wa.me/56912345678?text=')
        self.assertContains(respuesta, 'Cobrar')

    def test_editar_el_contacto(self):
        self.client.force_login(self.ana)
        self.client.post(reverse('editar_contacto', args=[self.persona.pk]), {'contacto': '987654321'})
        self.persona.refresh_from_db()
        self.assertEqual(self.persona.telefono_whatsapp, '56987654321')

    def test_no_se_edita_el_contacto_de_otra_cuenta(self):
        beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-segura-123')
        self.client.force_login(beto)
        respuesta = self.client.post(reverse('editar_contacto', args=[self.persona.pk]), {'contacto': '911111111'})
        self.assertEqual(respuesta.status_code, 404)
        self.persona.refresh_from_db()
        self.assertEqual(self.persona.contacto, '+56 9 1234 5678')
