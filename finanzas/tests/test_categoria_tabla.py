from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from ..models import Categoria, Deuda, GastoPendiente, Transaccion
from ..servicios import vinculo_categoria
from ..servicios.cuotas import mis_cuotas_detalle
from ..servicios.pendientes import pendientes_del_mes
from ..views.panel import textos_movimiento


class CategoriaDesdeLaTabla(TestCase):
    def setUp(self):
        vinculo_categoria.asegurar_base()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        self.client.force_login(self.ana)
        self.hoy = date.today()
        self.propia = Categoria.objects.create(usuario=self.ana, nombre='Peluquería',
                                               color='#f4626c', icono='fa-paw')

    def gasto(self, categoria, **extra):
        t = Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('1000'),
                                       categoria=categoria, fecha=self.hoy, **extra)
        return Transaccion.objects.get(pk=t.pk)

    def test_una_propia_muestra_su_nombre_color_e_icono(self):
        t = self.gasto(self.propia.slug)
        self.assertEqual((t.nombre_categoria, t.color_categoria, t.icono),
                         ('Peluquería', '#f4626c', 'fa-paw'))
        self.assertEqual(textos_movimiento(t), ('Peluquería', 'Gasto'))

    def test_una_base_sale_de_su_fila(self):
        Categoria.objects.filter(usuario=None, slug='Comida').update(
            nombre='Súper', color='#123456', icono='fa-utensils')
        t = self.gasto('Comida')
        self.assertEqual((t.nombre_categoria, t.color_categoria, t.icono),
                         ('Súper', '#123456', 'fa-utensils'))
        self.assertEqual(Categoria.mapa(self.ana)['Comida']['label'], 'Súper')

    def test_un_texto_desconocido_se_muestra_como_otros(self):
        t = self.gasto('NoExiste')
        self.assertEqual((t.categoria, t.nombre_categoria, t.icono), ('Otros', 'Otros Gastos', 'fa-ellipsis'))

    def test_leer_movimientos_no_consulta_la_categoria_de_cada_uno(self):
        for _ in range(5):
            self.gasto('Comida')
        with CaptureQueriesContext(connection) as consultas:
            iconos = [t.icono for t in Transaccion.objects.filter(usuario=self.ana)]
        self.assertEqual((len(iconos), len(consultas.captured_queries)), (5, 1))

    def test_el_mapa_marca_las_propias_y_no_trae_las_de_otro(self):
        Categoria.objects.create(usuario=self.beto, nombre='Gimnasio')
        mapa = Categoria.mapa(self.ana)
        self.assertTrue(mapa[self.propia.slug]['propia'])
        self.assertFalse(mapa['Comida']['propia'])
        self.assertNotIn('gimnasio', mapa)

    def test_lo_por_pagar_muestra_el_nombre_y_no_el_texto_interno(self):
        self.gasto(self.propia.slug, pagado=False)
        GastoPendiente.objects.create(usuario=self.ana, nombre='Luz', monto=Decimal('30000'),
                                      fecha_vencimiento=self.hoy, categoria='Servicios')
        detalles = {i['tipo']: i['detalle']
                    for i in pendientes_del_mes(self.ana, self.hoy.year, self.hoy.month)}
        self.assertEqual(detalles['gasto'], 'Peluquería')
        self.assertEqual(detalles['cuenta'], 'Luz, Agua, Internet')

    def test_las_cuotas_toman_color_e_icono_de_la_tabla(self):
        Deuda.objects.create(usuario=self.ana, acreedor='Tienda', monto_total=Decimal('60000'),
                             cuotas_totales=6, fecha_inicio=self.hoy, categoria='Ropa')
        fila = mis_cuotas_detalle(self.ana, self.hoy)[0][0]
        self.assertEqual((fila['color'], fila['icono']), ('#f472b6', 'fa-shirt'))

    def test_la_pantalla_de_categorias_no_suma_suscripciones_ni_cuentas(self):
        r = self.client.get(reverse('categorias'))
        slugs = {c['slug'] for c in r.context['de_gasto']}
        self.assertIn('Comida', slugs)
        self.assertIn(self.propia.slug, slugs)
        self.assertFalse(slugs & {'Suscripciones', 'Cuentas'})
