from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from ..models import Categoria, GastoPendiente, Suscripcion, Transaccion
from ..servicios import vinculo_categoria
from ..servicios.panel import desglose_categorias
from ..servicios.ritmo import _dia_a_dia
from ..servicios.topes import gastado_por_categoria


class CategoriaObligatoria(TestCase):

    def setUp(self):
        vinculo_categoria.asegurar_base()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.hoy = date.today()

    def base(self, slug):
        return Categoria.objects.get(usuario=None, slug=slug)

    def mov(self, categoria, tipo='EGRESO'):
        return Transaccion.objects.create(usuario=self.ana, tipo=tipo, monto=Decimal('1000'),
                                          categoria=categoria, fecha=self.hoy)

    def test_un_ingreso_desconocido_pasa_a_otros_ingresos(self):
        t = self.mov('NoExiste', tipo='INGRESO')
        self.assertEqual((t.categoria, t.categoria_ref), ('Otros_Ingresos', self.base('Otros_Ingresos')))

    def test_cada_tabla_tiene_su_respaldo(self):
        g = GastoPendiente.objects.create(usuario=self.ana, nombre='Luz', monto=Decimal('1000'),
                                          fecha_vencimiento=self.hoy, categoria='')
        s = Suscripcion.objects.create(usuario=self.ana, nombre='Radio', monto=Decimal('1000'),
                                       fecha_inicio=self.hoy, categoria='NoExiste')
        self.assertEqual(g.categoria_ref, self.base('Cuentas'))
        self.assertEqual(s.categoria_ref, self.base('Suscripciones'))

    def test_si_faltan_las_base_se_reponen_al_guardar(self):
        Categoria.objects.filter(usuario=None).delete()
        self.assertEqual(self.mov('Comida').categoria_ref.slug, 'Comida')

    def test_la_base_no_acepta_una_fila_sin_vinculo(self):
        t = self.mov('Comida')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Transaccion.objects.filter(pk=t.pk).update(categoria_ref=None)

    def test_las_sumas_agrupan_por_el_vinculo(self):
        t = self.mov('Comida')
        Transaccion.objects.filter(pk=t.pk).update(categoria='Ocio')
        inicio = self.hoy.replace(day=1)
        filas = desglose_categorias(self.ana, {'fecha_inicio': inicio, 'fecha_fin': self.hoy})
        self.assertEqual([f['nombre'] for f in filas], ['Comida'])
        self.assertEqual(list(gastado_por_categoria(self.ana, self.hoy.year, self.hoy.month)), ['Comida'])
        self.assertEqual(list(_dia_a_dia(self.ana, inicio, self.hoy)), ['Comida'])

    def test_la_pantalla_de_categorias_usa_el_vinculo(self):
        t = self.mov('Comida')
        Transaccion.objects.filter(pk=t.pk).update(categoria='Ocio')
        self.client.force_login(self.ana)
        r = self.client.get(reverse('categorias'))
        fila = next(c for c in r.context['de_gasto'] if c['slug'] == 'Comida')
        self.assertEqual((fila['gastado'], fila['usos'], len(fila['movs'])), (1000, 1, 1))
