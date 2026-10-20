from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .. import fechas
from ..models import GastoPendiente, Suscripcion, Transaccion
from ..servicios.pendientes import pendientes_del_mes
from ..servicios.suscripciones import generar_cobros_suscripciones
from ..views.panel import textos_movimiento


class Base(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.hoy = fechas.hoy()
        self.periodo = self.hoy.year * 100 + self.hoy.month

    def sub(self, meses_atras=0, nombre='Spotify'):
        inicio = self.hoy.replace(day=1) - relativedelta(months=meses_atras)
        return Suscripcion.objects.create(usuario=self.ana, nombre=nombre, monto=Decimal('5990'),
                                          dia_cobro=1, fecha_inicio=inicio)

    def gasto(self, descripcion, **datos):
        return Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('1000'),
                                          fecha=self.hoy, descripcion=descripcion, pagado=False, **datos)

    def pendientes(self):
        return pendientes_del_mes(self.ana, self.hoy.year, self.hoy.month)


class CobrosUnicosTests(Base):

    def test_generar_otra_vez_no_duplica(self):
        s = self.sub(meses_atras=2)
        generar_cobros_suscripciones(self.ana)
        Suscripcion.objects.filter(pk=s.pk).update(ultimo_mes_generado=0)
        generar_cobros_suscripciones(self.ana)
        inicio = self.hoy.replace(day=1) - relativedelta(months=2)
        esperado = []
        for i in range(3):
            f = inicio + relativedelta(months=i)
            esperado.append(f.year * 100 + f.month)
        self.assertEqual(sorted(s.cobros.values_list('periodo_cobro', flat=True)), esperado)

    def test_reactivar_en_el_mismo_mes_no_duplica(self):
        s = self.sub()
        generar_cobros_suscripciones(self.ana)
        self.client.force_login(self.ana)
        self.client.post(reverse('cancelar_suscripcion', args=[s.pk]))
        self.client.post(reverse('cancelar_suscripcion', args=[s.pk]))
        s.refresh_from_db()
        self.assertTrue(s.activa)
        self.assertEqual(s.cobros.count(), 1)

    def test_la_base_rechaza_un_cobro_repetido(self):
        s = self.sub()
        generar_cobros_suscripciones(self.ana)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.gasto('Suscripción: Spotify', suscripcion=s, periodo_cobro=self.periodo)

    def test_los_cobros_quedan_marcados(self):
        s = self.sub()
        generar_cobros_suscripciones(self.ana)
        cobro = s.cobros.get()
        self.assertEqual(cobro.origen, Transaccion.SUSCRIPCION)
        self.assertEqual(cobro.periodo_cobro, self.periodo)


class VinculosTests(Base):

    def test_un_gasto_con_texto_parecido_sigue_en_por_pagar(self):
        t = self.gasto('Suscripción: revista del barrio')
        filas = [i for i in self.pendientes() if i['tipo'] == 'gasto']
        self.assertEqual([i['nombre'] for i in filas], ['Suscripción: revista del barrio'])
        self.assertEqual(t.clase_tono, 'gasto')
        self.assertIsNone(t.marca_suscripcion)

    def test_cambiar_la_descripcion_no_cambia_el_tipo(self):
        s = self.sub()
        generar_cobros_suscripciones(self.ana)
        cobro = s.cobros.get()
        cobro.descripcion = 'Pago mensual'
        cobro.save()
        cobro.refresh_from_db()
        self.assertEqual(cobro.clase_tono, 'suscripcion')
        self.assertEqual([i['tipo'] for i in self.pendientes()], ['servicio'])

    def test_la_cuenta_por_pagar_se_reconoce_por_su_vinculo(self):
        t = self.gasto('Luz')
        GastoPendiente.objects.create(usuario=self.ana, nombre='Luz', monto=Decimal('1000'),
                                      fecha_vencimiento=self.hoy, transaccion=t)
        self.assertEqual([i['tipo'] for i in self.pendientes()], ['cuenta'])

    def test_crear_una_cuenta_por_pagar_la_marca(self):
        self.client.force_login(self.ana)
        self.client.post(reverse('crear_gasto_pendiente'), {
            'nombre': 'Agua', 'monto': '12000', 'fecha_vencimiento': self.hoy.isoformat()})
        t = Transaccion.objects.get(usuario=self.ana)
        self.assertEqual(t.origen, Transaccion.PENDIENTE)
        self.assertEqual(textos_movimiento(t), ('Agua', 'Cuenta por pagar'))

    def test_el_prefijo_solo_se_quita_si_corresponde(self):
        cobro = self.gasto('Suscripción: Netflix', origen=Transaccion.SUSCRIPCION)
        suelto = self.gasto('Pendiente: arreglar la bici')
        self.assertEqual(textos_movimiento(cobro), ('Netflix', 'Suscripción'))
        self.assertEqual(textos_movimiento(suelto)[0], 'Pendiente: arreglar la bici')
