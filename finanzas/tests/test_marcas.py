from django.template import Context, Template
from django.test import SimpleTestCase

from finanzas.marcas import buscar_marca


class MarcasTests(SimpleTestCase):
    def test_reconoce_con_glifo(self):
        m = buscar_marca('Netflix Premium')
        self.assertEqual(m['nombre'], 'Netflix')
        self.assertTrue(m['d'])

    def test_reconoce_suscripcion_generada(self):
        self.assertEqual(buscar_marca('Suscripción: Disney+')['nombre'], 'Disney+')

    def test_banco_sin_glifo_usa_letras(self):
        m = buscar_marca('BancoEstado CuentaRUT')
        self.assertEqual(m['nombre'], 'BancoEstado')
        self.assertIsNone(m['d'])
        self.assertEqual(m['letra'], 'BE')

    def test_ignora_tildes_y_mayusculas(self):
        self.assertEqual(buscar_marca('LÍDER EXPRESS')['nombre'], 'Líder')

    def test_no_confunde_palabras_parecidas(self):
        self.assertIsNone(buscar_marca('Maxi K'))
        self.assertIsNone(buscar_marca('Café'))
        self.assertIsNone(buscar_marca(''))

    def test_el_orden_elige_la_marca_mas_precisa(self):
        self.assertEqual(buscar_marca('Uber Eats')['nombre'], 'Uber Eats')
        self.assertEqual(buscar_marca('YouTube Music')['nombre'], 'YouTube Music')
        self.assertEqual(buscar_marca('HBO Max')['nombre'], 'Max')

    def test_la_plantilla_dibuja_el_logo(self):
        html = Template(
            "{% load marcas %}{% marca_de 'Spotify' as m %}"
            "{% include 'finanzas/_marca.html' with clase='sec-ficha' %}"
        ).render(Context({}))
        self.assertIn('marca-app', html)
        self.assertIn('<svg', html)
        self.assertIn('#1ed760', html)
