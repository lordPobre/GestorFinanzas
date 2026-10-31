from io import BytesIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader, PdfWriter

from ..cartolas.base import ClaveCartola, abrir_pdf, paginas_de_pdf

XHR = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


def _pdf(usuario=None, dueno=None):
    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    if usuario is not None:
        escritor.encrypt(user_password=usuario, owner_password=dueno or usuario, algorithm='AES-128')
    salida = BytesIO()
    escritor.write(salida)
    return salida.getvalue()


class AbrirPdf(TestCase):

    def test_sin_clave_queda_igual(self):
        plano = _pdf()
        self.assertEqual(abrir_pdf(plano), plano)

    def test_lo_que_no_es_pdf_queda_igual(self):
        self.assertEqual(abrir_pdf(b'Fecha;Monto\n'), b'Fecha;Monto\n')

    def test_protegido_pide_la_clave(self):
        with self.assertRaises(ClaveCartola) as error:
            abrir_pdf(_pdf('1234'))
        self.assertFalse(error.exception.incorrecta)

    def test_clave_equivocada(self):
        with self.assertRaises(ClaveCartola) as error:
            abrir_pdf(_pdf('1234'), '9999')
        self.assertTrue(error.exception.incorrecta)

    def test_clave_correcta_entrega_el_pdf_abierto(self):
        abierto = abrir_pdf(_pdf('1234'), '1234')
        lector = PdfReader(BytesIO(abierto))
        self.assertFalse(lector.is_encrypted)
        self.assertEqual(len(lector.pages), 1)

    def test_solo_con_clave_de_dueno_se_abre_sin_pedirla(self):
        abierto = abrir_pdf(_pdf('', 'del-banco'))
        self.assertFalse(PdfReader(BytesIO(abierto)).is_encrypted)

    def test_leer_paginas_de_un_protegido_pide_la_clave(self):
        with self.assertRaises(ClaveCartola):
            paginas_de_pdf(BytesIO(_pdf('1234')))


class PantallaPideClave(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _subir(self, contenido, **extra):
        archivo = SimpleUploadedFile('cartola.pdf', contenido, content_type='application/pdf')
        return self.client.post(reverse('importar_cartola'), {'cartola': archivo, **extra}, **XHR)

    def test_sin_clave_responde_que_la_pide(self):
        with mock.patch('finanzas.views.cartola.lectura_cartola.lanzar') as lanzar:
            datos = self._subir(_pdf('1234')).json()
        self.assertTrue(datos['pide_clave'])
        self.assertFalse(datos['incorrecta'])
        lanzar.assert_not_called()

    def test_clave_equivocada_lo_avisa(self):
        with mock.patch('finanzas.views.cartola.lectura_cartola.lanzar') as lanzar:
            datos = self._subir(_pdf('1234'), clave_pdf='0000').json()
        self.assertTrue(datos['incorrecta'])
        lanzar.assert_not_called()

    def test_con_la_clave_la_lectura_recibe_el_pdf_abierto(self):
        with mock.patch('finanzas.views.cartola.lectura_cartola.lanzar', return_value='t') as lanzar:
            datos = self._subir(_pdf('1234'), clave_pdf='1234').json()
        self.assertEqual(datos, {'ok': True, 'tarea': 't'})
        contenido = lanzar.call_args.args[1]
        self.assertFalse(PdfReader(BytesIO(contenido)).is_encrypted)

    def test_sin_fetch_vuelve_con_el_campo_de_clave(self):
        archivo = SimpleUploadedFile('cartola.pdf', _pdf('1234'), content_type='application/pdf')
        self.client.post(reverse('importar_cartola'), {'cartola': archivo})
        cuerpo = self.client.get(reverse('importar_cartola')).content.decode('utf-8')
        self.assertIn('id="clavePdf"', cuerpo)
        self.assertNotIn('id="cajaClave" hidden', cuerpo)
