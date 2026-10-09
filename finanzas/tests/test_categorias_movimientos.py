from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import Transaccion


class MovimientosPorCategoriaTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        hoy = date.today()
        self.este = hoy.replace(day=1)
        self.antes = date(hoy.year - 1, 12, 1) if hoy.month == 1 else date(hoy.year, hoy.month - 1, 1)

    def gasto(self, fecha, desc, monto, categoria='Comida'):
        return Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal(monto),
                                          categoria=categoria, fecha=fecha, descripcion=desc)

    def test_cada_categoria_trae_sus_movimientos_del_mes(self):
        pan = self.gasto(self.este, 'Pan amasado', '2500')
        self.gasto(self.antes, 'Super del mes pasado', '40000')
        self.gasto(self.este, 'Bencina', '30000', 'Transporte')
        r = self.client.get(reverse('categorias'))
        comida = next(c for c in r.context['de_gasto'] if c['slug'] == 'Comida')
        self.assertEqual(comida['movs'], [pan])
        self.assertContains(r, 'id="movs-Comida"')
        self.assertContains(r, reverse('editar_transaccion', args=[pan.pk]))
        self.assertContains(r, 'Ver 1 movimiento de este mes')
        self.assertNotContains(r, 'Super del mes pasado')

    def test_en_otro_mes_muestra_los_de_ese_mes(self):
        self.gasto(self.antes, 'Super del mes pasado', '40000')
        r = self.client.get(reverse('categorias'), {'mes': f'{self.antes.year}-{self.antes.month:02d}'})
        self.assertContains(r, 'Super del mes pasado')
        self.assertContains(r, 'Ver 1 movimiento de ')

    def test_no_muestra_movimientos_de_otra_persona(self):
        bruno = User.objects.create_user('bruno', 'bruno@ejemplo.cl', 'clave-larga-2')
        Transaccion.objects.create(usuario=bruno, tipo='EGRESO', monto=Decimal('999'),
                                   categoria='Comida', fecha=self.este, descripcion='Ajeno')
        self.gasto(self.este, 'Mío', '1000')
        r = self.client.get(reverse('categorias'))
        self.assertNotContains(r, 'Ajeno')
