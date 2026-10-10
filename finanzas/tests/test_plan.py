from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ..ia_plan import _nombrar, _prompt
from ..plan import _calza, etiqueta_mes, meses_sin_extra, promedio_tipico, simular
from ..views.comun import get_or_create_profile
from ..views.plan import _entero

DEUDAS = [
    {'nombre': 'Tarjeta Ripley', 'saldo': 124000, 'cuota': 31000},
    {'nombre': 'Notebook', 'saldo': 239970, 'cuota': 39995},
    {'nombre': 'Crédito de consumo', 'saldo': 1440000, 'cuota': 120000},
]


class SimulacionTests(SimpleTestCase):

    def test_sin_extra_cada_deuda_termina_a_su_ritmo(self):
        filas = simular(DEUDAS, 0)
        for f in filas:
            self.assertEqual(f['fin'], meses_sin_extra(f))

    def test_con_extra_termina_antes(self):
        base = max(f['fin'] for f in simular(DEUDAS, 0))
        con_extra = max(f['fin'] for f in simular(DEUDAS, 50000))
        self.assertLess(con_extra, base)

    def test_menor_saldo_primero(self):
        self.assertEqual(simular(DEUDAS, 50000, 'saldo')[0]['nombre'], 'Tarjeta Ripley')

    def test_mayor_cuota_primero(self):
        self.assertEqual(simular(DEUDAS, 50000, 'cuota')[0]['nombre'], 'Crédito de consumo')

    def test_nunca_paga_de_mas(self):
        for f in simular(DEUDAS, 90000):
            self.assertEqual(f['resta'], 0)

    def test_etiqueta_de_mes_cruza_el_año(self):
        self.assertEqual(etiqueta_mes(1, 2026, 9), 'septiembre 2026')
        self.assertEqual(etiqueta_mes(5, 2026, 9), 'enero 2027')


class AyudasTests(SimpleTestCase):

    def test_suscripcion_calza_por_palabra(self):
        self.assertTrue(_calza('netflix premium', 'netflix'))
        self.assertTrue(_calza('max', 'max'))
        self.assertFalse(_calza('maxi ahorro', 'max'))

    def test_montos_fuera_de_rango(self):
        self.assertEqual(_entero('abc', 100000), 0)
        self.assertEqual(_entero('-5', 100000), 0)
        self.assertEqual(_entero('999999', 100000), 100000)

    def test_la_ia_no_recibe_nombres(self):
        resumen = {
            'sobra': 142300, 'ahorro': 60000, 'extra': 50000, 'libre': 32300,
            'estrategia': 'saldo', 'termina_todo': 'julio 2027', 'termina_sin_extra': 'agosto 2027',
            'deudas': [{'clave': 'D1', 'saldo': 124000, 'cuota': 31000,
                        'termina': 'noviembre 2026', 'meses_antes': 2}],
            'meta_fondo': 1260000, 'llevas_fondo': 310000, 'porcentaje_fondo': 25,
            'fondo_completo_en': 'agosto 2027',
        }
        prompt = _prompt(resumen, '$')
        self.assertIn('[D1]', prompt)
        self.assertNotIn('Ripley', prompt)

    def test_las_claves_se_cambian_por_el_nombre(self):
        texto = _nombrar('Empieza por [D1] y sigue con [D9].', {'D1': 'Tarjeta Ripley'})
        self.assertEqual(texto, 'Empieza por «Tarjeta Ripley» y sigue con una de tus deudas.')


class MesTipicoTests(SimpleTestCase):

    def test_meses_vacios_no_bajan_el_ingreso(self):
        cerrados = [{'INGRESO': 2900000, 'EGRESO': 900000}, {}, {}]
        ingreso, gasto, base = promedio_tipico(cerrados, {}, 9, 31)
        self.assertEqual(ingreso, 2900000)
        self.assertEqual(gasto, 900000)
        self.assertEqual(base, 1)

    def test_cuenta_el_ingreso_del_mes_actual(self):
        cerrados = [{'EGRESO': 800000}, {'EGRESO': 600000}, {}]
        ingreso, gasto, base = promedio_tipico(cerrados, {'INGRESO': 2900000, 'EGRESO': 100000}, 9, 31)
        self.assertEqual(ingreso, 2900000)
        self.assertEqual(gasto, 700000)
        self.assertEqual(base, 2)

    def test_el_gasto_a_medias_del_mes_no_cuenta_si_hay_historial(self):
        _, gasto, _ = promedio_tipico([{'EGRESO': 500000}], {'EGRESO': 50000}, 9, 30)
        self.assertEqual(gasto, 500000)

    def test_sin_historial_proyecta_el_gasto_del_mes(self):
        _, gasto, base = promedio_tipico([{}, {}, {}], {'INGRESO': 1000000, 'EGRESO': 90000}, 9, 30)
        self.assertEqual(gasto, 300000)
        self.assertEqual(base, 0)


class VistasTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def test_la_pantalla_carga_sin_datos(self):
        r = self.client.get(reverse('plan_plata'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Plan para tu plata')

    def test_sin_sesion_manda_al_acceso(self):
        self.client.logout()
        r = self.client.get(reverse('plan_plata'))
        self.assertEqual(r.status_code, 302)

    def test_ia_apagada_no_explica(self):
        perfil = get_or_create_profile(self.ana)
        perfil.analisis_ia = False
        perfil.save(update_fields=['analisis_ia'])
        r = self.client.post(reverse('plan_ia'))
        self.assertTrue(r.json()['desactivado'])

    def test_sin_datos_no_llama_a_la_ia(self):
        r = self.client.post(reverse('plan_ia'))
        self.assertFalse(r.json()['ok'])
