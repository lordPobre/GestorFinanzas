from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from ..categorias_base import SLUGS_BASE
from ..models import Categoria, Deuda, GastoPendiente, Suscripcion, TopeCategoria, Transaccion
from ..servicios import vinculo_categoria


class Base(TestCase):
    def setUp(self):
        vinculo_categoria.asegurar_base()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        self.client.force_login(self.ana)

    def base(self, slug):
        return Categoria.objects.get(usuario=None, slug=slug)

    def gasto(self, categoria, usuario=None, **extra):
        return Transaccion.objects.create(usuario=usuario or self.ana, tipo='EGRESO', monto=Decimal('1000'),
                                          categoria=categoria, fecha=date.today(), **extra)


class FilasBase(Base):
    def test_estan_todas_las_categorias_de_siempre(self):
        slugs = set(Categoria.objects.filter(usuario=None).values_list('slug', flat=True))
        self.assertTrue(SLUGS_BASE <= slugs)
        self.assertEqual(len(SLUGS_BASE), 21)

    def test_asegurar_base_no_duplica(self):
        self.assertEqual(vinculo_categoria.asegurar_base(), 0)

    def test_no_aparecen_como_propias(self):
        self.assertFalse(Categoria.objects.filter(usuario=self.ana).exists())
        r = self.client.get(reverse('categorias'))
        self.assertEqual(r.context['total_propias'], 0)


class AlGuardar(Base):
    def test_un_gasto_queda_vinculado_a_la_base(self):
        t = self.gasto('Comida')
        self.assertEqual(t.categoria_ref, self.base('Comida'))

    def test_una_propia_gana_y_no_se_cruza_con_la_de_otro(self):
        de_beto = Categoria.objects.create(usuario=self.beto, nombre='Mascotas')
        mia = Categoria.objects.create(usuario=self.ana, nombre='Mascotas')
        self.assertEqual(mia.slug, de_beto.slug)
        self.assertEqual(self.gasto(mia.slug).categoria_ref, mia)
        self.assertEqual(self.gasto(de_beto.slug, usuario=self.beto).categoria_ref, de_beto)

    def test_cambiar_la_categoria_cambia_el_vinculo(self):
        t = self.gasto('Comida')
        t = Transaccion.objects.get(pk=t.pk)
        t.categoria = 'Ocio'
        t.save(update_fields=['categoria'])
        self.assertEqual(Transaccion.objects.get(pk=t.pk).categoria_ref, self.base('Ocio'))

    def test_guardar_otro_campo_no_consulta_categorias(self):
        t = Transaccion.objects.get(pk=self.gasto('Comida').pk)
        with CaptureQueriesContext(connection) as consultas:
            t.pagado = False
            t.save(update_fields=['pagado'])
            t.monto = Decimal('2000')
            t.save()
        tabla = Categoria._meta.db_table
        self.assertFalse([c['sql'] for c in consultas.captured_queries if tabla in c['sql']])

    def test_un_texto_desconocido_pasa_a_otros(self):
        t = self.gasto('NoExiste')
        self.assertEqual((t.categoria, t.categoria_ref), ('Otros', self.base('Otros')))

    def test_las_otras_tablas_tambien_se_vinculan(self):
        hoy = date.today()
        tope = TopeCategoria.objects.create(usuario=self.ana, categoria='Comida', monto=Decimal('50000'))
        pendiente = GastoPendiente.objects.create(usuario=self.ana, nombre='Luz', monto=Decimal('30000'),
                                                  fecha_vencimiento=hoy)
        sub = Suscripcion.objects.create(usuario=self.ana, nombre='Spotify', monto=Decimal('5990'),
                                         fecha_inicio=hoy)
        deuda = Deuda.objects.create(usuario=self.ana, acreedor='Tienda', monto_total=Decimal('60000'),
                                     cuotas_totales=6, fecha_inicio=hoy)
        self.assertEqual(tope.categoria_ref, self.base('Comida'))
        self.assertEqual(pendiente.categoria_ref, self.base('Cuentas'))
        self.assertEqual(sub.categoria_ref, self.base('Suscripciones'))
        self.assertEqual(deuda.categoria_ref, self.base('Tecnologia'))

    def test_el_tope_actualizado_desde_la_pantalla_queda_vinculado(self):
        self.client.post(reverse('guardar_tope'), {'categoria': 'Comida', 'monto': '50000', 'avisar': '1'})
        self.client.post(reverse('guardar_tope'), {'categoria': 'Comida', 'monto': '80000', 'avisar': '1'})
        tope = TopeCategoria.objects.get(usuario=self.ana)
        self.assertEqual((tope.monto, tope.categoria_ref), (Decimal('80000'), self.base('Comida')))


class AlBorrar(Base):
    def test_borrar_una_propia_mueve_todo_a_otros(self):
        cat = Categoria.objects.create(usuario=self.ana, nombre='Mascotas')
        t = self.gasto(cat.slug)
        TopeCategoria.objects.create(usuario=self.ana, categoria=cat.slug, monto=Decimal('10000'))
        p = GastoPendiente.objects.create(usuario=self.ana, nombre='Vacuna', monto=Decimal('20000'),
                                          fecha_vencimiento=date.today(), categoria=cat.slug)
        s = Suscripcion.objects.create(usuario=self.ana, nombre='Comida gato', monto=Decimal('9000'),
                                       fecha_inicio=date.today(), categoria=cat.slug)
        self.client.post(reverse('eliminar_categoria', args=[cat.pk]))
        self.assertFalse(Categoria.objects.filter(pk=cat.pk).exists())
        self.assertFalse(TopeCategoria.objects.filter(usuario=self.ana).exists())
        otros = self.base('Otros')
        for modelo, pk in ((Transaccion, t.pk), (GastoPendiente, p.pk), (Suscripcion, s.pk)):
            fila = modelo.objects.get(pk=pk)
            self.assertEqual((fila.categoria, fila.categoria_ref), ('Otros', otros), modelo.__name__)

    def test_borrar_la_cuenta_con_categorias_en_uso_no_falla(self):
        cat = Categoria.objects.create(usuario=self.ana, nombre='Mascotas')
        self.gasto(cat.slug)
        self.ana.delete()
        self.assertFalse(Transaccion.objects.filter(categoria_ref=cat.pk).exists())


class Revision(Base):
    def test_arreglar_vincula_filas_viejas_y_corrige_las_que_no_calzan(self):
        a = self.gasto('Comida')
        b = self.gasto('Ocio')
        Transaccion.objects.filter(pk=a.pk).update(categoria='NoExiste')
        Transaccion.objects.filter(pk=b.pk).update(categoria_ref=self.base('Comida'))
        self.assertEqual(vinculo_categoria.desalineados(Transaccion).count(), 2)
        vinculo_categoria.arreglar()
        a = Transaccion.objects.get(pk=a.pk)
        self.assertEqual((a.categoria, a.categoria_ref), ('Otros', self.base('Otros')))
        self.assertEqual(Transaccion.objects.get(pk=b.pk).categoria_ref, self.base('Ocio'))

    def test_un_vinculo_a_la_propia_de_otro_no_calza(self):
        de_beto = Categoria.objects.create(usuario=self.beto, nombre='Mascotas')
        t = self.gasto(de_beto.slug)
        Transaccion.objects.filter(pk=t.pk).update(categoria_ref=de_beto)
        self.assertEqual(vinculo_categoria.desalineados(Transaccion).count(), 1)

    def test_el_comando_avisa_los_textos_sueltos(self):
        t = self.gasto('Comida')
        Transaccion.objects.filter(pk=t.pk).update(categoria='NoExiste')
        salida = StringIO()
        call_command('revisar_categorias', stdout=salida)
        self.assertIn('NoExiste', salida.getvalue())
        self.assertIn('Quedan 1 filas por revisar', salida.getvalue())

    def test_el_comando_dice_cuando_esta_todo_bien(self):
        self.gasto('Comida')
        salida = StringIO()
        call_command('revisar_categorias', '--arreglar', stdout=salida)
        self.assertIn('Todo vinculado', salida.getvalue())
