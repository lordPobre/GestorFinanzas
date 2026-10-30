import os
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .. import ia_cliente
from ..cartolas import leer_cartola
from ..cartolas.base import ErrorCartola
from ..cartolas.lector_ia import INVENTADO, MAS_ANTIGUO, TOPE_MES, cifra, tapar
from ..models import Contador

CUENTA = ('Titular;CARLOS LOPEZ FIGUEROA;12.345.678-9;\n'
          'Fecha;Detalle;Monto;Saldo\n'
          '03/10/2026;SUPERMERCADO LIDER;45.900;954.100\n'
          '05/10/2026;SUELDO EMPRESA;1.200.000;2.154.100\n'
          '07/10/2026;FARMACIA CRUZ VERDE;12.990;2.141.110\n')

RARA = CUENTA.replace('Fecha;Detalle;Monto;Saldo', 'Cuando;Que;Plata;Queda')

TARJETA = ('Fecha;Descripcion;Cuotas;Valor cuota\n'
           '12/08/2026;ZAPATILLAS;3/6;45.900\n'
           '20/10/2026;FARMACIA AHUMADA;;14.990\n'
           '05/10/2026;PAGO TARJETA;;-200.000\n'
           'Monto total facturado;;;60.890\n')

PNG = b'\x89PNG\r\n\x1a\n' + b'0' * 200


def _fila(fecha, descripcion, monto, sentido='cargo', saldo='', a=0, t=0, pago=False):
    return {'fecha': fecha, 'descripcion': descripcion, 'monto': monto, 'sentido': sentido,
            'saldo': saldo, 'cuota_actual': a, 'cuota_total': t, 'es_pago_tarjeta': pago}


def _respuesta(movimientos, **cabeza):
    datos = {'tipo_documento': 'cuenta', 'institucion': 'Banco Prueba', 'fecha_facturacion': '',
             'saldo_inicial': '', 'saldo_final': '', 'total_facturado': '',
             'movimientos': movimientos, **cabeza}
    return SimpleNamespace(content=[SimpleNamespace(type='tool_use', name='entregar_cartola', input=datos)],
                           usage=None, stop_reason='tool_use')


SUPER = _fila('2026-10-03', 'SUPERMERCADO LIDER', '45.900', saldo='954.100')
SUELDO = _fila('2026-10-05', 'SUELDO EMPRESA', '1.200.000', 'abono', '2.154.100')
FARMACIA = _fila('2026-10-07', 'FARMACIA CRUZ VERDE', '12.990', saldo='2.141.110')


class LecturaConIA(TestCase):

    def setUp(self):
        self.carlos = User.objects.create_user('carlos', 'carlos@correo.cl', 'clave-larga-1',
                                               first_name='Carlos', last_name='López Figueroa')

    def _leer(self, contenido, nombre, *respuestas, clave='k'):
        with mock.patch.dict(os.environ, {'ANTHROPIC_API_KEY': clave}), \
                mock.patch('anthropic.Anthropic') as cliente:
            crear = cliente.return_value.messages.create
            crear.side_effect = list(respuestas)
            if isinstance(contenido, str):
                contenido = contenido.encode()
            cartola = leer_cartola(BytesIO(contenido), '', nombre, self.carlos)
        return cartola, crear

    def _usadas(self):
        return Contador.objects.filter(clave__startswith=f'cartola-ia:{self.carlos.pk}:') \
            .values_list('cuenta', flat=True).first()

    def test_lee_con_el_modelo_rapido_y_comprueba_la_cadena_de_saldos(self):
        cartola, crear = self._leer(CUENTA, 'c.csv', _respuesta([SUPER, SUELDO, FARMACIA]))
        self.assertEqual(crear.call_count, 1)
        self.assertEqual(crear.call_args.kwargs['model'], ia_cliente.modelo('cartola'))
        self.assertTrue(cartola.cuadra)
        self.assertEqual(cartola.banco, 'Banco Prueba')
        self.assertEqual([m.tipo for m in cartola.movimientos], ['EGRESO', 'INGRESO', 'EGRESO'])
        self.assertEqual(cartola.movimientos[-1].aviso, MAS_ANTIGUO)
        self.assertEqual(self._usadas(), 1)

    def test_lo_que_se_envia_va_sin_rut_ni_nombre(self):
        _, crear = self._leer(CUENTA, 'c.csv', _respuesta([SUPER, SUELDO, FARMACIA]))
        enviado = crear.call_args.kwargs['messages'][0]['content'][0]['text']
        self.assertNotIn('12.345.678-9', enviado)
        self.assertNotIn('LOPEZ', enviado)
        self.assertIn('FARMACIA CRUZ VERDE', enviado)

    def test_la_cadena_corrige_un_signo_mal_leido(self):
        sueldo_al_reves = dict(SUELDO, sentido='cargo')
        cartola, _ = self._leer(CUENTA, 'c.csv', _respuesta([SUPER, sueldo_al_reves, FARMACIA]))
        self.assertTrue(cartola.cuadra)
        sueldo = next(m for m in cartola.movimientos if 'SUELDO' in m.descripcion)
        self.assertEqual(sueldo.tipo, 'INGRESO')

    def test_si_la_cadena_no_cierra_lo_lee_el_modelo_grande(self):
        cartola, crear = self._leer(CUENTA, 'c.csv', _respuesta([SUPER, FARMACIA]),
                                    _respuesta([SUPER, SUELDO, FARMACIA]))
        self.assertEqual(crear.call_count, 2)
        self.assertEqual(crear.call_args.kwargs['model'], ia_cliente.modelo('cartola_revision'))
        self.assertTrue(cartola.cuadra)
        self.assertEqual(len(cartola.movimientos), 3)
        self.assertEqual(self._usadas(), 1)

    def test_si_la_ia_no_pasa_las_pruebas_usa_el_lector_propio(self):
        inventada = dict(FARMACIA, monto='99.999')
        cartola, crear = self._leer(CUENTA, 'c.csv', _respuesta([SUPER, SUELDO, inventada]),
                                    _respuesta([SUPER, SUELDO, inventada]))
        self.assertEqual(crear.call_count, 2)
        self.assertEqual(cartola.banco, 'Cartola exportada')
        self.assertTrue(cartola.cuadra)

    def test_sin_lector_propio_entrega_la_lectura_con_el_monto_marcado(self):
        inventada = dict(FARMACIA, monto='99.999')
        cartola, _ = self._leer(RARA, 'c.csv', _respuesta([SUPER, SUELDO, inventada]),
                                _respuesta([SUPER, SUELDO, inventada]))
        self.assertFalse(cartola.cuadra)
        marcada = next(m for m in cartola.movimientos if 'FARMACIA' in m.descripcion)
        self.assertEqual(marcada.aviso, INVENTADO)

    def test_sin_clave_usa_el_lector_propio(self):
        cartola, _ = self._leer(CUENTA, 'c.csv', clave='')
        self.assertEqual(cartola.banco, 'Cartola exportada')
        self.assertIsNone(self._usadas())

    def test_con_el_tope_del_mes_usa_el_lector_propio(self):
        Contador.objects.create(clave=f'cartola-ia:{self.carlos.pk}:{timezone.localdate():%Y-%m}',
                                cuenta=TOPE_MES, vence=timezone.now() + timedelta(days=30))
        cartola, crear = self._leer(CUENTA, 'c.csv')
        self.assertEqual(crear.call_count, 0)
        self.assertEqual(cartola.banco, 'Cartola exportada')

    def test_la_tarjeta_cuadra_con_el_total_y_anota_la_cuota_en_el_mes_facturado(self):
        respuesta = _respuesta([
            _fila('2026-08-12', 'ZAPATILLAS', '45.900', a=3, t=6),
            _fila('2026-10-20', 'FARMACIA AHUMADA', '14.990'),
            _fila('2026-10-05', 'PAGO TARJETA', '200.000', 'abono', pago=True),
        ], tipo_documento='tarjeta', institucion='Tarjeta Prueba', fecha_facturacion='2026-10-25',
            total_facturado='60.890')
        cartola, crear = self._leer(TARJETA, 't.csv', respuesta)
        self.assertEqual(crear.call_count, 1)
        self.assertTrue(cartola.cuadra)
        cuota = next(m for m in cartola.movimientos if m.cuota_total)
        self.assertEqual((cuota.fecha, cuota.cuota_actual, cuota.cuota_total), (date(2026, 10, 25), 3, 6))
        self.assertTrue(cuota.descripcion.endswith('cuota 3 de 6'))
        pago = next(m for m in cartola.movimientos if 'PAGO' in m.descripcion)
        self.assertTrue(pago.aviso.startswith('No es un gasto'))

    def test_una_foto_va_como_imagen(self):
        respuesta = _respuesta([_fila('2026-10-03', 'SUPERMERCADO', '45.900'),
                                _fila('2026-10-05', 'SUELDO', '1.200.000', 'abono')])
        cartola, crear = self._leer(PNG, 'foto.png', respuesta)
        self.assertEqual(crear.call_count, 1)
        self.assertEqual(crear.call_args.kwargs['messages'][0]['content'][0]['type'], 'image')
        self.assertFalse(cartola.cuadra)
        self.assertEqual(len(cartola.movimientos), 2)

    def test_una_foto_sin_ia_avisa(self):
        with self.assertRaises(ErrorCartola) as caja:
            self._leer(PNG, 'foto.png', clave='')
        self.assertIn('fotos', str(caja.exception))


class DatosTapados(TestCase):

    def test_tapa_rut_nombre_cuenta_correo_y_direccion(self):
        usuario = SimpleNamespace(first_name='Carlos', last_name='López Figueroa', email='carlos@correo.cl')
        texto = tapar('Titular: CARLOS LOPEZ FIGUEROA RUT 12.345.678-9 carlos@correo.cl\n'
                      'Cuenta Corriente N° 00-123-45678-09\n'
                      'Dirección: Av. Siempre Viva 742\n'
                      '03/10/2026 FARMACIA CRUZ VERDE 12.990 2.141.110', usuario)
        for dato in ('LOPEZ', '12.345.678-9', '45678', 'carlos@correo.cl', 'Siempre Viva'):
            self.assertNotIn(dato, texto)
        self.assertIn('FARMACIA CRUZ VERDE 12.990 2.141.110', texto)

    def test_no_confunde_montos_con_un_rut(self):
        self.assertIn('1.234.567 -9.990', tapar('1.234.567 -9.990'))


class Cifras(TestCase):

    def test_lee_los_formatos_de_monto(self):
        self.assertEqual(cifra('45.900'), Decimal('45900'))
        self.assertEqual(cifra('$ 1.200.000'), Decimal('1200000'))
        self.assertEqual(cifra('-1.234,50'), Decimal('-1234.50'))
        self.assertEqual(cifra('(12.990)'), Decimal('-12990'))
        self.assertEqual(cifra('1,234.56'), Decimal('1234.56'))
        self.assertIsNone(cifra(''))
