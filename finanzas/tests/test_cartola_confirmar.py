from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import Deuda, Persona, Prestamo, Suscripcion, Transaccion
from ..views.cartola import SESION


def _movimiento(fecha, descripcion, monto, tipo='EGRESO', categoria='Otros', ya_existe=False):
    return {
        'fecha': fecha, 'descripcion': descripcion, 'monto': monto, 'tipo': tipo,
        'categoria': categoria, 'cuota_actual': 0, 'cuota_total': 0,
        'es_suscripcion': False, 'ya_existe': ya_existe, 'aviso': '',
    }


class ConfirmarCartolaTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        sesion = self.client.session
        sesion[SESION] = {
            'banco': 'Banco de Chile', 'periodo': 'Septiembre 2026', 'cuenta': '', 'cuadra': True,
            'descuadre': '0', 'nota_cuadre': '', 'saldo_inicial': '', 'saldo_final': '',
            'movimientos': [
                _movimiento('2026-09-01', 'REMUNERACION EMPRESA', '795000', 'INGRESO', 'Sueldo'),
                _movimiento('2026-09-15', 'SUPERMERCADO', '54990', categoria='Comida'),
                _movimiento('2026-09-30', 'SPOTIFY', '5990', categoria='Suscripciones'),
                _movimiento('2026-09-25', 'TRASPASO A CAMILA', '20000'),
                _movimiento('2026-09-20', 'YA ANOTADO', '1000', ya_existe=True),
            ],
        }
        sesion.save()

    def test_guarda_lo_marcado_con_sus_extras_y_vuelve_al_inicio(self):
        respuesta = self.client.post(reverse('confirmar_cartola'), {
            'sel_0': '1', 'sel_1': '1', 'desc_1': 'Supermercado de septiembre',
            'sel_2': '1', 'sub_2': '1',
            'sel_3': '1', 'deben_3': '1', 'deben_nombre_3': 'Camila',
        })
        self.assertRedirects(respuesta, reverse('dashboard'), fetch_redirect_response=False)

        movs = Transaccion.objects.filter(usuario=self.ana)
        self.assertEqual(movs.count(), 4)
        self.assertFalse(movs.filter(descripcion='YA ANOTADO').exists())
        self.assertTrue(all(t.pagado and t.fecha_pago == t.fecha for t in movs))
        sueldo = movs.get(descripcion='REMUNERACION EMPRESA')
        self.assertEqual((sueldo.tipo, sueldo.categoria, sueldo.monto), ('INGRESO', 'Sueldo', Decimal('795000')))
        self.assertTrue(movs.filter(descripcion='Supermercado de septiembre', categoria='Comida').exists())

        sub = Suscripcion.objects.get(usuario=self.ana)
        self.assertEqual((sub.nombre, sub.monto, sub.dia_cobro), ('SPOTIFY', Decimal('5990'), 28))
        self.assertEqual(sub.fecha_inicio, date(2026, 9, 30))

        prestamo = Prestamo.objects.get(persona__usuario=self.ana)
        self.assertEqual(prestamo.persona.nombre, 'Camila')
        self.assertEqual(prestamo.persona.lado, 'ME_DEBE')
        self.assertEqual((prestamo.monto, prestamo.tipo, prestamo.cuotas_totales), (Decimal('20000'), 'UNICO', 1))

        self.assertFalse(Deuda.objects.filter(usuario=self.ana).exists())
        self.assertNotIn(SESION, self.client.session)

    def test_una_persona_que_ya_existe_no_se_duplica(self):
        camila = Persona.objects.create(usuario=self.ana, nombre='Camila', lado='ME_DEBE')
        self.client.post(reverse('confirmar_cartola'), {
            'sel_3': '1', 'deben_3': '1', 'deben_persona_3': str(camila.pk)})
        self.assertEqual(Persona.objects.filter(usuario=self.ana).count(), 1)
        self.assertEqual(Prestamo.objects.get().persona, camila)

    def test_sin_nada_marcado_no_guarda_y_vuelve_a_importar(self):
        respuesta = self.client.post(reverse('confirmar_cartola'), {})
        self.assertRedirects(respuesta, reverse('importar_cartola'), fetch_redirect_response=False)
        self.assertFalse(Transaccion.objects.filter(usuario=self.ana).exists())
        self.assertNotIn(SESION, self.client.session)

    def test_sin_revision_pendiente_manda_a_subirla_otra_vez(self):
        sesion = self.client.session
        del sesion[SESION]
        sesion.save()
        respuesta = self.client.post(reverse('confirmar_cartola'), {'sel_0': '1'})
        self.assertRedirects(respuesta, reverse('importar_cartola'), fetch_redirect_response=False)
        self.assertFalse(Transaccion.objects.filter(usuario=self.ana).exists())
