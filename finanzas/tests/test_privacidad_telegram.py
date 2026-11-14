from django.test import TestCase
from django.urls import reverse

from finanzas import legal


class PrivacidadTelegramTests(TestCase):

    def test_la_version_nueva_cuenta_el_cambio(self):
        self.assertEqual(legal.VERSION, '1.10')
        self.assertIn('Anotar desde Telegram', [titulo for titulo, _ in legal.CAMBIOS])

    def test_la_politica_declara_telegram(self):
        cuerpo = self.client.get(reverse('privacidad')).content.decode('utf-8')
        self.assertIn('<h3>Anotar desde Telegram</h3>', cuerpo)
        self.assertIn('<b>Telegram</b>', cuerpo)
        self.assertIn('Audio que le mandas al bot de Telegram', cuerpo)
        self.assertIn('conexión con Telegram', cuerpo)
        self.assertIn('/desconectar', cuerpo)
