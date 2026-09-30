from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from ..models import Transaccion
from ..servicios.ritmo import ritmo_del_mes

HOY = date(2026, 9, 15)


class RitmoTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def gasto(self, monto, fecha, categoria='Comida', descripcion=''):
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=monto, categoria=categoria,
                                   fecha=fecha, descripcion=descripcion, pagado=True, fecha_pago=fecha)

    def historial(self, meses=(6, 7, 8)):
        for m in meses:
            self.gasto(50000, date(2026, m, 5))
            self.gasto(50000, date(2026, m, 25))

    def test_avisa_cuando_la_categoria_va_rapido(self):
        self.historial()
        self.gasto(120000, date(2026, 9, 10))
        avisos = ritmo_del_mes(self.ana, HOY)
        self.assertEqual(len(avisos), 1)
        self.assertIn('$170.000', avisos[0]['texto'])
        self.assertIn('70% más', avisos[0]['texto'])
        self.assertIn('Ya pasaste tu promedio', avisos[0]['texto'])

    def test_da_un_monto_por_dia_si_aun_hay_margen(self):
        self.historial()
        self.gasto(80000, date(2026, 9, 10))
        avisos = ritmo_del_mes(self.ana, HOY)
        self.assertEqual(len(avisos), 1)
        self.assertIn('te quedan $20.000', avisos[0]['texto'])
        self.assertIn('$1.333 por día', avisos[0]['texto'])

    def test_no_avisa_antes_del_dia_7(self):
        self.historial()
        self.gasto(120000, date(2026, 9, 3))
        self.assertEqual(ritmo_del_mes(self.ana, date(2026, 9, 6)), [])

    def test_necesita_dos_meses_de_historial(self):
        self.historial(meses=(8,))
        self.gasto(120000, date(2026, 9, 10))
        self.assertEqual(ritmo_del_mes(self.ana, HOY), [])

    def test_no_avisa_si_va_normal(self):
        self.historial()
        self.gasto(50000, date(2026, 9, 5))
        self.assertEqual(ritmo_del_mes(self.ana, HOY), [])

    def test_suscripciones_y_pendientes_no_cuentan(self):
        self.historial()
        self.gasto(300000, date(2026, 9, 1), descripcion='Suscripción: Gimnasio')
        self.gasto(300000, date(2026, 9, 2), descripcion='Pendiente: Dentista')
        self.assertEqual(ritmo_del_mes(self.ana, HOY), [])

    def test_felicita_si_gasta_menos(self):
        self.historial()
        self.gasto(10000, date(2026, 9, 10))
        avisos = ritmo_del_mes(self.ana, HOY)
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]['tipo'], 'exito')
