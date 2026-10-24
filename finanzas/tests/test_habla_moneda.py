import os
from unittest import mock

from django.contrib.auth.models import User
from django.core import signing
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .. import legal
from ..habla import para_voz
from ..models import UserProfile
from ..templatetags.voz import SAL


class MontosHabladosTests(SimpleTestCase):

    def test_pesos(self):
        self.assertEqual(para_voz('Te quedan $16.900 este mes.'), 'Te quedan dieciséis mil novecientos pesos este mes.')
        self.assertEqual(para_voz('Son $ 60.000 en 3 cuotas'), 'Son sesenta mil pesos en tres cuotas')
        self.assertEqual(para_voz('Debes $2.000.000'), 'Debes dos millones de pesos')
        self.assertEqual(para_voz('CLP 16.900'), 'dieciséis mil novecientos pesos')
        self.assertEqual(para_voz('Te pasaste por -$5.000'), 'Te pasaste por menos cinco mil pesos')

    def test_otras_monedas(self):
        self.assertEqual(para_voz('Pagas US$12,45'), 'Pagas doce dólares con cuarenta y cinco centavos')
        self.assertEqual(para_voz('Cuesta US$1'), 'Cuesta un dólar')
        self.assertEqual(para_voz('€1.200 al mes'), 'mil doscientos euros al mes')
        self.assertEqual(para_voz('S/ 45,50'), 'cuarenta y cinco soles con cincuenta centavos')
        self.assertEqual(para_voz('R$21'), 'veintiún reales')

    def test_el_signo_solo_usa_la_moneda_del_usuario(self):
        self.assertEqual(para_voz('Te quedan $50', 'dólares'), 'Te quedan cincuenta dólares')

    def test_no_repite_la_moneda(self):
        self.assertEqual(para_voz('Te quedan $16.900 pesos'), 'Te quedan dieciséis mil novecientos pesos')
        self.assertEqual(para_voz('$2.000.000 de pesos'), 'dos millones de pesos')

    def test_lo_demas_queda_igual(self):
        self.assertEqual(para_voz('Te quedan 412.300 pesos.'), 'Te quedan cuatrocientos doce mil trescientos pesos.')
        self.assertEqual(para_voz('$16.900, y el 86%'), 'dieciséis mil novecientos pesos, y el ochenta y seis por ciento')
        self.assertEqual(para_voz('Sube 2.5 veces'), 'Sube 2.5 veces')


class VozConMonedaTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        UserProfile.objects.update_or_create(
            usuario=self.ana, defaults={'onboarding_completado': True, 'analisis_ia': True,
                                        'politica_version': legal.VERSION, 'moneda': 'USD'})
        self.client.force_login(self.ana)

    def test_hablar_usa_la_moneda_del_perfil(self):
        frase = signing.dumps({'u': self.ana.pk, 't': 'Te quedan $50'}, salt=SAL, compress=True)
        with mock.patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'k', 'ELEVENLABS_VOZ': 'v'}), \
                mock.patch('finanzas.views.voz.sintetizar', return_value=b'mp3') as sintetizar:
            r = self.client.post(reverse('voz_esfera'), {'frase': frase}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200)
        sintetizar.assert_called_once_with('Te quedan $50', 'dólares')
