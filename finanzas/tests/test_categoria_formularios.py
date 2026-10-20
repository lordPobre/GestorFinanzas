from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..forms import DeudaForm, TransaccionForm
from ..models import Categoria, Deuda
from ..servicios import vinculo_categoria


class OpcionesDesdeLaTabla(TestCase):

    def setUp(self):
        vinculo_categoria.asegurar_base()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.mascotas = Categoria.objects.create(usuario=self.ana, nombre='Mascotas')
        self.client.force_login(self.ana)

    def slugs(self, tipo):
        return [s for s, _ in Categoria.opciones(self.ana, tipo)]

    def test_las_base_salen_de_su_fila(self):
        Categoria.objects.filter(usuario=None, slug='Comida').update(nombre='Súper')
        self.assertIn(('Comida', 'Súper'), Categoria.opciones(self.ana, 'EGRESO'))

    def test_orden_y_lo_que_no_se_ofrece(self):
        Categoria.objects.create(usuario=self.ana, nombre='Vieja', activa=False)
        egreso = self.slugs('EGRESO')
        self.assertEqual(egreso[0], 'Comida')
        self.assertEqual(egreso[-1], self.mascotas.slug)
        self.assertFalse({'Suscripciones', 'Cuentas', 'vieja', 'Sueldo'} & set(egreso))
        self.assertEqual(self.slugs('INGRESO')[0], 'Sueldo')

    def test_una_base_desactivada_deja_de_ofrecerse(self):
        Categoria.objects.filter(usuario=None, slug='Viajes').update(activa=False)
        self.assertNotIn('Viajes', self.slugs('EGRESO'))

    def test_si_faltan_las_base_las_repone(self):
        Categoria.objects.filter(usuario=None).delete()
        self.assertIn('Comida', self.slugs('EGRESO'))
        self.assertTrue(Categoria.objects.filter(usuario=None, slug='Cuentas').exists())

    def test_por_tipo_es_lo_mismo_en_una_consulta(self):
        with self.assertNumQueries(1):
            por_tipo = Categoria.opciones_por_tipo(self.ana)
        self.assertEqual(por_tipo['EGRESO'], Categoria.opciones(self.ana, 'EGRESO'))
        self.assertEqual(por_tipo['INGRESO'], Categoria.opciones(self.ana, 'INGRESO'))


class Formularios(OpcionesDesdeLaTabla):

    def datos(self, tipo, categoria):
        return {'tipo': tipo, 'monto': '1000', 'categoria': categoria,
                'descripcion': '', 'fecha': date.today().isoformat()}

    def test_un_ingreso_no_acepta_una_base_de_gasto(self):
        form = TransaccionForm(self.datos('INGRESO', 'Comida'), usuario=self.ana)
        self.assertFalse(form.is_valid())
        self.assertIn('Esa categoría es de gastos', form.errors['categoria'][0])

    def test_un_ingreso_no_acepta_una_propia_de_gasto(self):
        form = TransaccionForm(self.datos('INGRESO', self.mascotas.slug), usuario=self.ana)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['categoria'], ['Esa categoría es de gastos.'])

    def test_un_gasto_con_su_propia_pasa(self):
        form = TransaccionForm(self.datos('EGRESO', self.mascotas.slug), usuario=self.ana)
        self.assertTrue(form.is_valid(), form.errors)

    def test_una_compra_en_cuotas_acepta_una_propia(self):
        form = DeudaForm({'acreedor': 'Veterinaria', 'valor_cuota': '10000', 'cuotas_totales': '3',
                          'fecha_inicio': date.today().isoformat(), 'categoria': self.mascotas.slug},
                         usuario=self.ana)
        self.assertTrue(form.is_valid(), form.errors)

    def test_una_compra_en_cuotas_no_acepta_una_de_ingreso(self):
        form = DeudaForm({'acreedor': 'X', 'valor_cuota': '10000', 'cuotas_totales': '3',
                          'fecha_inicio': date.today().isoformat(), 'categoria': 'Sueldo'},
                         usuario=self.ana)
        self.assertFalse(form.is_valid())

    def test_la_pantalla_de_cuotas_ofrece_las_propias(self):
        r = self.client.get(reverse('deudas'))
        slugs = [s for s, _ in r.context['form'].fields['categoria'].choices]
        self.assertIn(self.mascotas.slug, slugs)
        self.assertIn('Comida', slugs)

    def test_la_cuota_muestra_el_nombre_de_la_tabla(self):
        d = Deuda.objects.create(usuario=self.ana, acreedor='Cine', monto_total=Decimal('30000'),
                                 cuotas_totales=3, fecha_inicio=date.today(), categoria='Ocio')
        self.assertEqual(d.nombre_categoria, 'Entretenimiento y Salidas')
