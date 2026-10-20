from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from ..forms import DeudaForm, TransaccionForm
from ..models import Categoria, Deuda, Suscripcion, TopeCategoria, Transaccion
from ..servicios import vinculo_categoria


class CategoriaSinTexto(TestCase):

    def setUp(self):
        vinculo_categoria.asegurar_base()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.hoy = date.today()

    def base(self, slug):
        return Categoria.objects.get(usuario=None, slug=slug)

    def test_no_queda_la_columna_de_texto(self):
        for modelo in (Transaccion, TopeCategoria, Suscripcion, Deuda):
            nombres = {c.name for c in modelo._meta.concrete_fields}
            self.assertNotIn('categoria', nombres, modelo.__name__)
            self.assertIn('categoria_ref', nombres, modelo.__name__)

    def test_la_propiedad_lee_y_escribe_el_slug(self):
        t = Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('1000'),
                                       categoria='Comida', fecha=self.hoy)
        self.assertEqual(Transaccion.objects.get(pk=t.pk).categoria, 'Comida')
        t.categoria = 'Ocio'
        t.save(update_fields=['categoria'])
        self.assertEqual(Transaccion.objects.get(pk=t.pk).categoria_ref, self.base('Ocio'))

    def test_sin_categoria_toma_la_de_siempre(self):
        d = Deuda.objects.create(usuario=self.ana, acreedor='Tienda', monto_total=Decimal('60000'),
                                 cuotas_totales=6, fecha_inicio=self.hoy)
        s = Suscripcion.objects.create(usuario=self.ana, nombre='Radio', monto=Decimal('1000'),
                                       fecha_inicio=self.hoy)
        self.assertEqual((d.categoria, s.categoria), ('Tecnologia', 'Suscripciones'))

    def test_filtrar_por_slug(self):
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('1000'),
                                   categoria='Comida', fecha=self.hoy)
        self.assertEqual(Transaccion.objects.filter(categoria_ref__slug='Comida').count(), 1)

    def test_un_tope_por_categoria(self):
        TopeCategoria.objects.create(usuario=self.ana, categoria='Comida', monto=Decimal('1000'))
        with self.assertRaises(IntegrityError), transaction.atomic():
            TopeCategoria.objects.create(usuario=self.ana, categoria='Comida', monto=Decimal('2000'))

    def test_editar_un_movimiento_trae_su_categoria(self):
        t = Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('1000'),
                                       categoria='Salud', fecha=self.hoy)
        form = TransaccionForm(instance=Transaccion.objects.get(pk=t.pk), usuario=self.ana)
        self.assertEqual(form.initial['categoria'], 'Salud')

    def test_el_formulario_guarda_la_categoria(self):
        form = TransaccionForm({'tipo': 'EGRESO', 'monto': '1000', 'categoria': 'Hogar',
                                'descripcion': '', 'fecha': self.hoy.isoformat()}, usuario=self.ana)
        self.assertTrue(form.is_valid(), form.errors)
        t = form.save(commit=False)
        t.usuario = self.ana
        t.save()
        self.assertEqual(Transaccion.objects.get(pk=t.pk).categoria_ref, self.base('Hogar'))

    def test_una_compra_nueva_parte_en_tecnologia(self):
        self.assertEqual(DeudaForm(usuario=self.ana).initial['categoria'], 'Tecnologia')

    def test_editar_una_suscripcion_cambia_la_categoria_del_cobro_del_mes(self):
        from ..servicios.suscripciones import generar_cobros_suscripciones
        s = Suscripcion.objects.create(usuario=self.ana, nombre='Radio', monto=Decimal('1000'),
                                       fecha_inicio=self.hoy.replace(day=1), dia_cobro=1)
        generar_cobros_suscripciones(self.ana)
        self.client.force_login(self.ana)
        self.client.post(reverse('editar_suscripcion', args=[s.pk]),
                         {'nombre': 'Radio', 'monto': '1000', 'categoria': 'Ocio', 'dia_cobro': '1'})
        self.assertEqual(Suscripcion.objects.get(pk=s.pk).categoria, 'Ocio')
        self.assertEqual(s.cobros.get().categoria_ref, self.base('Ocio'))

    def test_la_descarga_de_datos_incluye_la_categoria(self):
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('1000'),
                                   categoria='Comida', fecha=self.hoy)
        self.client.force_login(self.ana)
        datos = self.client.get(reverse('mis_datos')).json()
        self.assertEqual(datos['movimientos'][0]['categoria'], 'Comida')
