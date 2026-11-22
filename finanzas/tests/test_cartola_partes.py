from unittest import mock

from django.test import SimpleTestCase

from ..cartolas import lector_ia


class PartesDeLaCartolaTests(SimpleTestCase):

    def _cuerpos(self, fuente):
        return [p[0]['text'].split('\n', 1)[1].rsplit('\n</documento>', 1)[0] for p in fuente['partes']]

    def test_una_pagina_larga_se_parte_por_lineas_sin_perder_ninguna(self):
        filas = [f'{i % 28 + 1:02d}/10/2026 COMPRA SUPERMERCADO {i:03d} 12.345 1.234.567' for i in range(300)]
        with mock.patch.object(lector_ia, 'paginas_de_pdf', return_value=['\n'.join(filas)]):
            fuente = lector_ia._fuente(b'%PDF-1.4', 'c.pdf', '', None)
        cuerpos = self._cuerpos(fuente)
        self.assertGreater(len(cuerpos), 1)
        self.assertTrue(all(len(c) <= lector_ia.CARACTERES_POR_PARTE for c in cuerpos))
        self.assertEqual([linea for c in cuerpos for linea in c.splitlines()], filas)

    def test_una_cartola_corta_va_en_una_sola_parte(self):
        filas = [f'0{i}/10/2026 FARMACIA {i} 5.990 120.000' for i in range(1, 9)]
        with mock.patch.object(lector_ia, 'paginas_de_pdf', return_value=['\n'.join(filas[:4]), '\n'.join(filas[4:])]):
            fuente = lector_ia._fuente(b'%PDF-1.4', 'c.pdf', '', None)
        self.assertEqual(self._cuerpos(fuente), ['\n'.join(filas)])
