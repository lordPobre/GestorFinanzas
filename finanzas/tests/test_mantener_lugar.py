from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ..models import Categoria, Transaccion


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

    def test_eliminar_desde_la_hoja_no_recarga(self):
        r = self.client.post(reverse('eliminar_transaccion', args=[self.t.pk]),
                             HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'ok': True})
        self.assertFalse(Transaccion.objects.filter(pk=self.t.pk).exists())

    def test_un_next_de_otro_sitio_no_se_sigue(self):
        r = self.client.post(reverse('eliminar_transaccion', args=[self.t.pk]),
                             {'next': 'https://otro.example/'})
        self.assertRedirects(r, reverse('dashboard'), fetch_redirect_response=False)

    def test_la_hoja_de_movimientos_borra_sin_recargar_y_lleva_a_repetidos(self):
        r = self.client.get(reverse('dashboard'), {'year': 2026, 'month': 8})
        self.assertContains(r, 'data-sin-recargar="eliminar"')
        self.assertContains(r, 'js/pantallas/movimientos-hoja.js')
        self.assertContains(r, reverse('movimientos_repetidos'))
        self.assertContains(r, 'name="next" value="/?year=2026&amp;month=8"')

    def test_categorias_vuelve_al_mes_elegido(self):
        cat = Categoria.objects.create(usuario=self.ana, nombre='Mascotas')
        r = self.client.post(reverse('eliminar_categoria', args=[cat.pk]),
                             {'next': '/categorias/?mes=2026-08'})
        self.assertRedirects(r, '/categorias/?mes=2026-08', fetch_redirect_response=False)

    def test_la_base_carga_el_script(self):
        r = self.client.get(reverse('categorias'))
        self.assertContains(r, 'js/mantener-lugar.js')


class ScriptTests(SimpleTestCase):

    def test_no_vuelve_a_paginas_de_entrada_ni_a_formularios(self):
        js = (Path(settings.BASE_DIR) / 'static' / 'js' / 'mantener-lugar.js').read_text(encoding='utf-8')
        self.assertIn('logout|login|registro|verificar|recuperar|entrar', js)
        self.assertIn('editar|nuevo|nueva', js)
        self.assertIn("form.querySelector('[name=\"next\"]')", js)
