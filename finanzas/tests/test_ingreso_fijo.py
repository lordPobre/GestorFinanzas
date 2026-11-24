from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from ..models import IngresoFijo, IngresoMes, Transaccion
from ..servicios import ingreso_fijo
from ..views.cartola import SESION

HOY = date(2026, 11, 24)


def _hoy(fecha=HOY):
    return mock.patch('finanzas.fechas.hoy', return_value=fecha)


class IngresoFijoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _crear(self, monto='1250000', dia='30', fecha=HOY):
        with _hoy(fecha):
            return self.client.post(reverse('guardar_ingreso'), {
                'nombre': 'Constructora Valpo', 'monto': monto, 'dia_pago': dia})

    def test_pestana_vacia(self):
        with _hoy():
            respuesta = self.client.get(reverse('ingresos'))
        self.assertTemplateUsed(respuesta, 'finanzas/ingresos_2c.html')
        self.assertContains(respuesta, 'aria-current="page">Ingresos</a>')
        self.assertContains(respuesta, 'Todavía no tienes un ingreso fijo')
        self.assertContains(respuesta, 'css/ingresos-2c.css')

    def test_guardar_deja_el_mes_por_recibir(self):
        self._crear()
        ingreso = IngresoFijo.objects.get(usuario=self.ana)
        self.assertEqual((ingreso.monto, ingreso.dia_pago, ingreso.inicio), (Decimal('1250000'), 30, 202611))
        with _hoy():
            respuesta = self.client.get(reverse('ingresos'))
        self.assertContains(respuesta, 'Noviembre · por recibir')
        self.assertContains(respuesta, 'Llega el 30')
        self.assertContains(respuesta, 'data-pct=')

    def test_otro_dia_gana_a_los_botones(self):
        with _hoy():
            self.client.post(reverse('guardar_ingreso'), {'monto': '900000', 'dia_pago': '30', 'dia_otro': '10'})
        self.assertEqual(IngresoFijo.objects.get(usuario=self.ana).dia_pago, 10)

    def test_ya_llego_anota_el_ingreso_y_deshacer_lo_borra(self):
        self._crear()
        with _hoy():
            self.client.post(reverse('ingreso_llego'), {'periodo': '202611'})
        tx = Transaccion.objects.get(usuario=self.ana)
        self.assertEqual((tx.tipo, tx.monto, tx.categoria, tx.fecha), ('INGRESO', Decimal('1250000'), 'Sueldo', HOY))
        fila = IngresoMes.objects.get(periodo=202611)
        self.assertTrue(fila.llego and fila.anotado_aqui)
        with _hoy():
            self.client.post(reverse('ingreso_deshacer'), {'periodo': '202611'})
        self.assertFalse(Transaccion.objects.filter(usuario=self.ana).exists())
        self.assertFalse(IngresoMes.objects.get(periodo=202611).llego)

    def test_un_mes_futuro_no_se_marca(self):
        self._crear()
        with _hoy():
            self.client.post(reverse('ingreso_llego'), {'periodo': '202612'})
        self.assertFalse(Transaccion.objects.filter(usuario=self.ana).exists())

    def test_otra_persona_no_toca_tu_sueldo(self):
        self._crear()
        beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(beto)
        with _hoy():
            self.client.post(reverse('ingreso_llego'), {'periodo': '202611'})
            self.client.post(reverse('ajustar_ingreso'), {'periodo': '202611', 'modo': 'extra', 'extra': '1000'})
            self.client.post(reverse('quitar_ingreso'))
        self.assertTrue(IngresoFijo.objects.filter(usuario=self.ana).exists())
        self.assertFalse(IngresoMes.objects.exists())
        self.assertFalse(Transaccion.objects.exists())

    def test_horas_extra_solo_ese_mes(self):
        self._crear()
        with _hoy():
            self.client.post(reverse('ajustar_ingreso'),
                             {'periodo': '202611', 'modo': 'extra', 'extra': '86400', 'nota': '12 horas'})
            datos = ingreso_fijo.pantalla(self.ana, 202611, HOY)
        self.assertEqual(datos['detalle']['total'], Decimal('1336400'))
        self.assertEqual(datos['detalle']['nota'], '12 horas')
        self.assertEqual(IngresoFijo.objects.get(usuario=self.ana).monto, Decimal('1250000'))

    def test_horas_extra_despues_de_ya_llego_suben_el_ingreso(self):
        self._crear()
        with _hoy():
            self.client.post(reverse('ingreso_llego'), {'periodo': '202611'})
            self.client.post(reverse('ajustar_ingreso'), {'periodo': '202611', 'modo': 'extra', 'extra': '50000'})
        self.assertEqual(Transaccion.objects.get(usuario=self.ana).monto, Decimal('1300000'))

    def test_cambiar_monto_de_aqui_en_adelante_deja_los_meses_anteriores(self):
        self._crear(fecha=date(2026, 9, 10))
        with _hoy():
            self.client.post(reverse('ajustar_ingreso'),
                             {'periodo': '202611', 'modo': 'monto', 'nuevo': '1400000', 'alcance': 'adelante'})
            datos = ingreso_fijo.pantalla(self.ana, 202611, HOY)
        self.assertEqual(IngresoFijo.objects.get(usuario=self.ana).monto, Decimal('1400000'))
        por_mes = {m['periodo']: m['sueldo'] for m in datos['meses']}
        self.assertEqual(por_mes[202609], Decimal('1250000'))
        self.assertEqual(por_mes[202610], Decimal('1250000'))
        self.assertEqual(por_mes[202611], Decimal('1400000'))
        self.assertEqual(datos['meses'][9]['estado'], 'sin_confirmar')

    def test_cambiar_monto_solo_ese_mes(self):
        self._crear()
        with _hoy():
            self.client.post(reverse('ajustar_ingreso'),
                             {'periodo': '202611', 'modo': 'monto', 'nuevo': '1336400', 'alcance': 'mes'})
            datos = ingreso_fijo.pantalla(self.ana, 202611, HOY)
        self.assertEqual(datos['detalle']['sueldo'], Decimal('1336400'))
        self.assertTrue(datos['detalle']['cambiado'])
        self.assertEqual(IngresoFijo.objects.get(usuario=self.ana).monto, Decimal('1250000'))

    def test_al_crear_usa_el_sueldo_que_ya_estaba_anotado(self):
        Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal('1250000'), categoria='Sueldo',
                                   fecha=date(2026, 11, 3), origen=Transaccion.CARTOLA)
        self._crear()
        fila = IngresoMes.objects.get(periodo=202611)
        self.assertTrue(fila.llego and fila.por_cartola)
        self.assertEqual(Transaccion.objects.filter(usuario=self.ana).count(), 1)


def _mov(fecha, descripcion, monto, tipo='INGRESO', categoria='Sueldo'):
    return {'fecha': fecha, 'descripcion': descripcion, 'monto': monto, 'tipo': tipo, 'categoria': categoria,
            'cuota_actual': 0, 'cuota_total': 0, 'es_suscripcion': False, 'ya_existe': False, 'aviso': ''}


class SueldoEnCartolaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        with _hoy():
            ingreso_fijo.guardar(self.ana, 'Constructora Valpo', Decimal('1250000'), 30, HOY)

    def _sesion(self, monto):
        sesion = self.client.session
        sesion[SESION] = {
            'banco': 'Banco de Chile', 'periodo': 'Noviembre 2026', 'cuenta': '', 'cuadra': True,
            'descuadre': '0', 'nota_cuadre': '', 'saldo_inicial': '', 'saldo_final': '',
            'movimientos': [
                _mov('2026-11-21', 'REMUNERACION CONSTRUCTORA VALPO', monto),
                _mov('2026-11-15', 'SUPERMERCADO', '54990', 'EGRESO', 'Comida'),
            ],
        }
        sesion.save()

    def test_revisar_ofrece_el_sueldo_marcado_y_la_diferencia_sin_marcar(self):
        self._sesion('1336400')
        with _hoy():
            cuerpo = self.client.get(reverse('revisar_cartola')).content.decode('utf-8')
        self.assertIn('name="sueldo_0" data-vinculo checked', cuerpo)
        self.assertIn('Es tu sueldo de noviembre', cuerpo)
        self.assertIn('name="extra_0">', cuerpo)
        self.assertIn('como horas extra', cuerpo)

    def test_confirmar_lo_deja_recibido_sin_sumar_la_diferencia(self):
        self._sesion('1336400')
        with _hoy():
            self.client.post(reverse('confirmar_cartola'), {'sel_0': '1', 'sueldo_0': '1'})
        fila = IngresoMes.objects.get(periodo=202611)
        self.assertTrue(fila.llego and fila.por_cartola)
        self.assertEqual((fila.monto_recibido, fila.extra), (Decimal('1336400'), Decimal('0')))

    def test_confirmar_con_horas_extra(self):
        self._sesion('1336400')
        with _hoy():
            self.client.post(reverse('confirmar_cartola'), {'sel_0': '1', 'sueldo_0': '1', 'extra_0': '1'})
        self.assertEqual(IngresoMes.objects.get(periodo=202611).extra, Decimal('86400'))

    def test_reemplaza_el_que_marcaste_a_mano(self):
        with _hoy(date(2026, 11, 20)):
            ingreso_fijo.llego(IngresoFijo.objects.get(usuario=self.ana), 202611, date(2026, 11, 20))
        self._sesion('1250000')
        with _hoy():
            self.client.post(reverse('confirmar_cartola'), {'sel_0': '1', 'sueldo_0': '1'})
        sueldos = Transaccion.objects.filter(usuario=self.ana, tipo='INGRESO')
        self.assertEqual(sueldos.count(), 1)
        self.assertEqual(sueldos.get().fecha, date(2026, 11, 21))
        self.assertTrue(IngresoMes.objects.get(periodo=202611).por_cartola)

    def test_un_ingreso_que_no_se_parece_no_se_ofrece(self):
        movs = [_mov('2026-11-10', 'TRANSFERENCIA DE JUAN', '30000', categoria='Transferencia')]
        self.assertEqual(ingreso_fijo.en_cartola(self.ana, movs, HOY), {})
