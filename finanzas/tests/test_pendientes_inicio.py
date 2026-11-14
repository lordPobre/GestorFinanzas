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

    def _veces(self, html, nombre):
        return [html.count(f'class="{clase}" aria-label="Marcar {nombre} como pagado"')
                for clase in ('i2c-pagar', 'i2c-linea-pagar')]

    def test_cada_pago_sale_una_vez_en_cada_lista(self):
        self._pendiente('Luz', self.hoy.day)
        html = self._html()
        self.assertEqual(self._veces(html, 'Luz'), [1, 1])
        self.assertNotIn('ini-fila', html)
        self.assertNotIn('data-lista-pagar>', html)

    def test_lleva_la_fecha_y_el_monto(self):
        self._pendiente('Agua', self.hoy.day)
        html = self._html()
        boton = html.index('class="i2c-pagar" aria-label="Marcar Agua como pagado"')
        fila = html[html.rindex('<div class="i2c-fila', 0, boton):boton]
        self.assertIn(f'vence el {self.hoy.day} ', fila)
        self.assertIn('class="i2c-fila-monto"', fila)
        boton = html.index('class="i2c-linea-pagar" aria-label="Marcar Agua como pagado"')
        fila = html[html.rindex('<div class="i2c-linea-fila', 0, boton):boton]
        self.assertIn(f'class="i2c-linea-fecha">{self.hoy.day} ', fila)

    def test_los_atrasados_no_se_repiten(self):
        if self.hoy.day < 3:
            return
        self._pendiente('Gas', 1)
        self._pendiente('Internet', 2)
        html = self._html()
        for nombre in ('Gas', 'Internet'):
            self.assertEqual(self._veces(html, nombre), [1, 1], nombre)

    def test_sin_pendientes_queda_el_aviso_de_vacio(self):
        html = self._html()
        self.assertIn('Estás al día.</p>', html)
        self.assertIn('class="i2c-aldia"', html)
