from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import Transaccion


class PendientesInicioTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.hoy = date.today()

    def _pendiente(self, descripcion, dia):
        return Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('31400'),
                                          categoria='Otros', fecha=self.hoy.replace(day=dia),
                                          descripcion=descripcion, pagado=False)

    def _html(self):
        return self.client.get(reverse('dashboard')).content.decode()

    def test_cada_pago_sale_una_sola_vez(self):
        self._pendiente('Luz', self.hoy.day)
        html = self._html()
        self.assertEqual(html.count('aria-label="Marcar Luz como pagado"'), 1)
        self.assertNotIn('ini-fila', html)
        self.assertNotIn('data-lista-pagar>', html)

    def test_lleva_los_dos_textos_de_la_fecha(self):
        self._pendiente('Agua', self.hoy.day)
        html = self._html()
        inicio = html.index('aria-label="Marcar Agua como pagado"')
        tarjeta = html[html.rindex('<div class="ini-pago', 0, inicio):inicio]
        self.assertIn('class="ini-pago-cuando"', tarjeta)
        self.assertIn('class="ini-pago-vence"', tarjeta)
        self.assertIn('class="ini-pago-monto"', tarjeta)

    def test_los_atrasados_no_se_repiten_en_el_modal(self):
        if self.hoy.day < 3:
            return
        self._pendiente('Gas', 1)
        self._pendiente('Internet', 2)
        html = self._html()
        for nombre in ('Gas', 'Internet'):
            self.assertEqual(html.count(f'aria-label="Marcar {nombre} como pagado"'), 1)
        self.assertIn('<div class="ini-lista-modal" data-lista-atrasados></div>', html)

    def test_sin_pendientes_queda_el_aviso_de_vacio(self):
        self.assertIn('data-lista-pagar-vacia hidden', self._html())
