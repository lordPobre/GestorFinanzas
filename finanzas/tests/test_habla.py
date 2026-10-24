from django.test import SimpleTestCase

from ..habla import en_palabras, para_voz


class EnPalabrasTests(SimpleTestCase):

    def test_numeros_sueltos(self):
        casos = {
            0: 'cero', 1: 'uno', 15: 'quince', 21: 'veintiuno', 30: 'treinta', 48: 'cuarenta y ocho',
            100: 'cien', 101: 'ciento uno', 112: 'ciento doce', 500: 'quinientos', 1000: 'mil',
            2027: 'dos mil veintisiete', 21000: 'veintiún mil', 96000: 'noventa y seis mil',
            412300: 'cuatrocientos doce mil trescientos', 1_000_000: 'un millón',
            1_500_000: 'un millón quinientos mil', 21_000_000: 'veintiún millones',
            1_000_000_000: 'mil millones',
        }
        for n, esperado in casos.items():
            with self.subTest(n=n):
                self.assertEqual(en_palabras(n), esperado)


class ParaVozTests(SimpleTestCase):

    def test_montos_con_punto_de_miles(self):
        self.assertEqual(para_voz('Te quedan 412.300 pesos.'),
                         'Te quedan cuatrocientos doce mil trescientos pesos.')
        self.assertEqual(para_voz('Te pasaste por 96.000 pesos.'),
                         'Te pasaste por noventa y seis mil pesos.')

    def test_uno_concuerda_con_lo_que_sigue(self):
        self.assertEqual(para_voz('Pagas 1 pesos'), 'Pagas un peso')
        self.assertEqual(para_voz('Pagas 21 pesos'), 'Pagas veintiún pesos')
        self.assertEqual(para_voz('en 1 compra'), 'en una compra')
        self.assertEqual(para_voz('Tienes 21 cuotas atrasadas'), 'Tienes veintiuna cuotas atrasadas')
        self.assertEqual(para_voz('Estás suscrito a 1 servicio'), 'Estás suscrito a un servicio')
        self.assertEqual(para_voz('Y 1 más.'), 'Y uno más.')
        self.assertEqual(para_voz('el 1 por ciento'), 'el uno por ciento')

    def test_millones_redondos_llevan_de(self):
        self.assertEqual(para_voz('Debes 2.000.000 pesos'), 'Debes dos millones de pesos')
        self.assertEqual(para_voz('Debes 2.500.000 pesos'), 'Debes dos millones quinientos mil pesos')

    def test_porcentajes(self):
        self.assertEqual(para_voz('Llevas el 48 por ciento'), 'Llevas el cuarenta y ocho por ciento')
        self.assertEqual(para_voz('Usaste el 86%'), 'Usaste el ochenta y seis por ciento')

    def test_deja_lo_demas_igual(self):
        self.assertEqual(para_voz('Vas bien.'), 'Vas bien.')
        self.assertEqual(para_voz('Sube 2.5 veces'), 'Sube 2.5 veces')
        self.assertEqual(para_voz(''), '')
