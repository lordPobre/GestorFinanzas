from io import BytesIO
from unittest import mock

import PIL
from django import forms
from django.test import SimpleTestCase
from PIL import EpsImagePlugin, Image, TiffImagePlugin

from ..fotos import recodificar

EPS = b'%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\nshowpage\n%%EOF\n'


class FormatosFotoTests(SimpleTestCase):
    def test_pillow_parchado(self):
        self.assertGreaterEqual(int(PIL.__version__.split('.')[0]), 13, PIL.__version__)

    def test_no_abre_eps(self):
        with mock.patch.object(EpsImagePlugin.EpsImageFile, '_open', side_effect=AssertionError('se abrió un EPS')):
            with self.assertRaises(forms.ValidationError):
                recodificar(BytesIO(EPS))

    def test_no_abre_tiff(self):
        archivo = BytesIO()
        Image.new('RGB', (10, 10)).save(archivo, 'TIFF')
        archivo.seek(0)
        with mock.patch.object(TiffImagePlugin.TiffImageFile, '_open', side_effect=AssertionError('se abrió un TIFF')):
            with self.assertRaises(forms.ValidationError):
                recodificar(archivo)

    def test_sigue_aceptando_png_y_gif(self):
        for formato in ('PNG', 'GIF'):
            with self.subTest(formato=formato):
                archivo = BytesIO()
                Image.new('RGB', (20, 20), (10, 20, 30)).save(archivo, formato)
                archivo.seek(0)
                salida = recodificar(archivo)
                with Image.open(BytesIO(salida.read())) as imagen:
                    self.assertEqual(imagen.format, 'JPEG')
