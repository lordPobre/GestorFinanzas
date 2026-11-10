from decimal import Decimal

from django.test import SimpleTestCase

from finanzas.templatetags import f2c


class Colores2cTests(SimpleTestCase):
    def test_los_colores_base_caen_en_la_paleta_del_prototipo(self):
        self.assertEqual(f2c.tono_suave('#60a5fa'), 'verde')
        self.assertEqual(f2c.tono_suave('#53d258'), 'azul')
        self.assertEqual(f2c.fondo_suave('#8b8b96'), '#E7E3DC')
        self.assertEqual(f2c.tinta_suave('#2dd4bf'), '#5B3F7A')

    def test_un_color_propio_se_ubica_por_su_tono(self):
        self.assertEqual(f2c.tono_suave('#ffaa2c'), 'ambar')
        self.assertEqual(f2c.tono_suave('#3366ff'), 'azul')
        self.assertEqual(f2c.tono_suave('#e11d48'), 'coral')
        self.assertEqual(f2c.tono_suave('no-es-color'), 'gris')

    def test_la_paleta_no_repite_tonos(self):
        paleta = [('#60a5fa', 'Azul'), ('#4ade80', 'Verde'), ('#a3e635', 'Lima'), ('#8b8b96', 'Gris')]
        tonos = [fila[3] for fila in f2c.paleta_suave(paleta)]
        self.assertEqual(len(tonos), len(set(tonos)))
        self.assertEqual(f2c.paleta_suave(paleta)[0][0], '#60a5fa')

    def test_el_icono_sale_de_las_categorias_base(self):
        self.assertEqual(f2c.icono_cat('Transporte'), 'fa-car')
        self.assertEqual(f2c.icono_cat('propia'), 'fa-tag')

    def test_el_tope_dice_cuanto_va(self):
        topes = {'Comida': ['Comida', 100000.0, 0.0]}
        self.assertEqual(f2c.tope_de(topes, 'Comida', Decimal('85000'))['tono'], 'amarillo')
        pasado = f2c.tope_de(topes, 'Comida', Decimal('120000'))
        self.assertEqual((pasado['tono'], pasado['ancho'], pasado['exceso']), ('rojo', 100, Decimal('20000')))
        self.assertIsNone(f2c.tope_de(topes, 'Ocio', Decimal('5000')))
        self.assertIsNone(f2c.tope_de('', 'Comida', Decimal('5000')))
