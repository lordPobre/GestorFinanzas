from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class PlanOrdenTests(SimpleTestCase):
    def setUp(self):
        ruta = Path(settings.BASE_DIR) / 'finanzas' / 'templates' / 'finanzas' / 'plan.html'
        self.html = ruta.read_text(encoding='utf-8')

    def test_bloques_en_orden(self):
        claves = ['class="pl-reparto"', 'id="planAhorro"', 'id="planExtra"', 'pl-dap', 'data-simulador',
                  'plan.suscripciones', '_plan_ia.html', 'pl-aprender-caja']
        posiciones = [self.html.index(c) for c in claves]
        self.assertEqual(posiciones, sorted(posiciones))

    def test_el_reparto_va_en_la_cabecera(self):
        self.assertLess(self.html.index('class="pl-reparto"'), self.html.index('class="sec-hoja pl-hoja"'))

    def test_colores_de_los_sliders(self):
        self.assertIn('class="pl-slider chico verde"', self.html)
        self.assertIn('class="pl-slider chico ambar"', self.html)
        self.assertIn('id="planExtraTope"', self.html)
