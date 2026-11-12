from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from finanzas import diseno
from finanzas.servicios import vida_2c
from finanzas.templatetags import f2c


class SaludoTests(SimpleTestCase):
    def test_el_saludo_cambia_con_la_hora(self):
        self.assertEqual(f2c.saludo_de(6)['texto'], 'Buenos días')
        self.assertEqual(f2c.saludo_de(15)['texto'], 'Buenas tardes')
        self.assertEqual(f2c.saludo_de(21)['texto'], 'Buenas noches')
        self.assertEqual(f2c.saludo_de(3)['tono'], 'noche')

    def test_el_nombre_corto_es_la_primera_palabra(self):
        self.assertEqual(f2c.nombre_corto('Camila Rojas'), 'Camila')
        self.assertEqual(f2c.nombre_corto(''), '')


class MetasTests(SimpleTestCase):
    def _dato(self, actual, meta, aportes, limite=None, quieta=0):
        m = SimpleNamespace(esta_completa=False, monto_faltante=Decimal(meta - actual), fecha_limite=limite,
                            monto_meta=Decimal(meta), monto_actual=Decimal(actual), nombre='Viaje')
        return {'meta': m, 'aportado_6m': sum(aportes), 'meses_quieta': quieta,
                'ultimo_aporte': SimpleNamespace(fecha=date(2026, 7, 1)),
                'serie': [{'monto': a, 'alto': 50, 'label': 'junio'} for a in aportes]}

    def test_dice_cuando_llegas_al_ritmo_de_hoy(self):
        eta = vida_2c.eta_meta(self._dato(380000, 900000, [40000, 60000, 80000, 0, 100000, 50000],
                                          date(2027, 6, 1)), date(2026, 11, 12))
        self.assertEqual(eta['llega'], 'septiembre 2027')
        self.assertEqual(eta['tono'], 'ambar')
        self.assertEqual(eta['etiqueta'], '3 meses después de tu fecha')

    def test_una_meta_quieta_lo_dice(self):
        eta = vida_2c.eta_meta(self._dato(120000, 650000, [60000, 60000, 0, 0, 0, 0], quieta=4),
                               date(2026, 11, 12))
        self.assertEqual(eta['tono'], 'gris')
        self.assertEqual(eta['etiqueta'], 'Sin aportes desde julio')

    def test_el_resumen_suma_el_mes_y_elige_la_proxima(self):
        datos = [self._dato(1150000, 1500000, [150000, 150000, 100000, 150000, 0, 150000]),
                 self._dato(380000, 900000, [40000, 60000, 80000, 0, 100000, 50000])]
        r = vida_2c.metas_2c(datos, date(2026, 11, 12))
        self.assertEqual(r['este_mes'], Decimal('200000'))
        self.assertEqual(r['proxima']['llega'], 'febrero 2027')
        self.assertEqual([m['tono'] for m in r['metas']], ['verde', 'azul'])


class BarrasDoblesTests(SimpleTestCase):
    def test_compara_lo_que_entro_con_lo_que_salio(self):
        meses = ['agosto 2026', 'septiembre 2026', 'octubre 2026', 'noviembre 2026']
        r = vida_2c.barras_dobles(meses, [100, 100, 100, 100], [80, 120, 90, 40], 6, 'noviembre 2026',
                                  date(2026, 11, 12))
        self.assertEqual(r['titulo'], 'Septiembre fue el único mes en que salió más de lo que entró')
        self.assertTrue(r['meses'][-1]['en_curso'])
        self.assertTrue(r['meses'][1]['rojo'])


class InicioVidaTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.client.cookies[diseno.COOKIE] = diseno.VALOR

    def test_inicio_trae_el_saludo_y_el_mes_dia_a_dia(self):
        cuerpo = self.client.get(reverse('dashboard')).content.decode('utf-8')
        self.assertIn('class="i2c-saludo"', cuerpo)
        self.assertIn('data-saludo-caja', cuerpo)
        self.assertIn('Tu mes día a día', cuerpo)
        self.assertIn('js/pantallas/vida-2c.js', cuerpo)
        self.assertIn('css/vida-2c.css', cuerpo)

    def test_las_pantallas_del_plan_y_tu_cargan(self):
        for nombre in ('metas', 'estadisticas', 'analisis_predictivo', 'perfil'):
            with self.subTest(nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)
