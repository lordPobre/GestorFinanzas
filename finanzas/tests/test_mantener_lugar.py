from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ..models import Transaccion


class VueltaAlMismoLugarTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.t = Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('1000'),
                                            fecha=date(2026, 8, 10), descripcion='Pan')

    def test_eliminar_vuelve_al_mes_que_estabas_mirando(self):
        r = self.client.post(reverse('eliminar_transaccion', args=[self.t.pk]),
                             {'next': '/?year=2026&month=8'})
        self.assertRedirects(r, '/?year=2026&month=8', fetch_redirect_response=False)
        self.assertFalse(Transaccion.objects.filter(pk=self.t.pk).exists())

    def test_un_next_de_otro_sitio_no_se_sigue(self):
        r = self.client.post(reverse('eliminar_transaccion', args=[self.t.pk]),
                             {'next': 'https://otro.example/'})
        self.assertRedirects(r, reverse('dashboard'), fetch_redirect_response=False)

    def test_la_base_carga_el_script(self):
        r = self.client.get(reverse('categorias'))
        self.assertContains(r, 'js/mantener-lugar.js')


class ScriptTests(SimpleTestCase):

    def test_no_vuelve_a_paginas_de_entrada_ni_a_formularios(self):
        js = (Path(settings.BASE_DIR) / 'static' / 'js' / 'mantener-lugar.js').read_text(encoding='utf-8')
        self.assertIn('logout|login|registro|verificar|recuperar|entrar', js)
        self.assertIn('editar|nuevo|nueva', js)
        self.assertIn("form.querySelector('[name=\"next\"]')", js)
