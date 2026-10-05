import json
import os
from decimal import Decimal
from io import BytesIO
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import URLPattern, reverse
from django.urls.converters import IntConverter

from .. import google_login, urls
from ..fotos import recodificar
from ..models import AporteMeta, Categoria, GastoPendiente, PagoCuota, PagoServicio, Transaccion
from ..views.comun import monto_post
from .test_vistas import BaseDosUsuarios


def _pedido(**datos):
    return RequestFactory().post('/', datos)


class MontoPostTests(SimpleTestCase):

    def test_valores_raros_quedan_en_cero(self):
        for valor in ('NaN', 'Infinity', '-5000', '0', 'abc', '1e30', '999999999999'):
            with self.subTest(valor=valor):
                self.assertEqual(monto_post(_pedido(monto=valor)), Decimal('0'))

    def test_formato_chileno(self):
        self.assertEqual(monto_post(_pedido(monto='15.990')), Decimal('15990.00'))
        self.assertEqual(monto_post(_pedido(monto='1.500,5')), Decimal('1500.50'))


class AislamientoAutomaticoTests(BaseDosUsuarios):

    DATOS = {
        'deuda_id': 'deuda', 'transaccion_id': 'transaccion', 'persona_id': 'persona',
        'prestamo_id': 'prestamo', 'meta_id': 'meta', 'sub_id': 'sub', 'gasto_id': 'gasto',
        'cat_id': 'categoria',
    }

    def _rutas(self):
        for patron in urls.urlpatterns:
            if not isinstance(patron, URLPattern) or not patron.name:
                continue
            enteros = [k for k, v in patron.pattern.converters.items()
                       if isinstance(v, IntConverter)]
            if enteros:
                yield patron, enteros

    def test_cada_ruta_con_id_rechaza_los_datos_de_otro(self):
        self.de_ana['categoria'] = Categoria.objects.create(usuario=self.ana, nombre='Mascotas')
        self.client.force_login(self.beto)
        revisadas = 0
        for patron, claves in self._rutas():
            sin_datos = [k for k in claves if k not in self.DATOS]
            self.assertFalse(sin_datos, f'La ruta {patron.name} usa {sin_datos}. '
                                        'Agrégalo a DATOS para probar su aislamiento.')
            url = reverse(patron.name, kwargs={k: self.de_ana[self.DATOS[k]].pk for k in claves})
            for metodo in ('get', 'post'):
                with self.subTest(ruta=patron.name, metodo=metodo):
                    respuesta = getattr(self.client, metodo)(url, {'monto': '1000', 'nombre': 'x'})
                    self.assertNotEqual(respuesta.status_code, 200)
            revisadas += 1
        self.assertGreaterEqual(revisadas, 20)

        for clave, obj in self.de_ana.items():
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists(), clave)
        self.de_ana['meta'].refresh_from_db()
        self.assertEqual(self.de_ana['meta'].monto_actual, 0)
        self.assertFalse(PagoCuota.objects.filter(deuda=self.de_ana['deuda']).exists())
        self.assertFalse(PagoServicio.objects.filter(suscripcion=self.de_ana['sub']).exists())
        self.assertFalse(Transaccion.objects.get(pk=self.de_ana['transaccion'].pk).pagado)
        self.assertFalse(GastoPendiente.objects.get(pk=self.de_ana['gasto'].pk).pagado)


class PagosYAportesTests(BaseDosUsuarios):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.ana)

    def test_pagar_dos_veces_la_misma_cuota_deja_un_pago(self):
        deuda = self.de_ana['deuda']
        periodo = deuda.periodos_programados[0]
        for _ in range(2):
            self.client.post(reverse('pagar_cuota', args=[deuda.pk]), {'periodo': periodo})
        self.assertEqual(PagoCuota.objects.filter(deuda=deuda, periodo=periodo).count(), 1)

    def test_nota_larga_se_corta(self):
        meta = self.de_ana['meta']
        self.client.post(reverse('aportar_meta', args=[meta.pk]), {'monto': '1000', 'nota': 'x' * 500})
        self.assertEqual(len(AporteMeta.objects.get(meta=meta).nota), 120)

    def test_aporte_nan_no_rompe(self):
        meta = self.de_ana['meta']
        respuesta = self.client.post(reverse('aportar_meta', args=[meta.pk]), {'monto': 'NaN'})
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(AporteMeta.objects.filter(meta=meta).exists())


class FotoTests(SimpleTestCase):

    def _foto(self, ancho=3000, alto=2000, formato='JPEG'):
        from PIL import Image
        imagen = Image.new('RGB', (ancho, alto), (200, 100, 50))
        exif = Image.Exif()
        exif[0x0110] = 'Telefono secreto'
        datos = BytesIO()
        imagen.save(datos, formato, exif=exif)
        return SimpleUploadedFile('yo.jpg', datos.getvalue(), content_type='image/jpeg')

    def test_quita_exif_y_achica(self):
        from PIL import Image
        salida = recodificar(self._foto())
        with Image.open(BytesIO(salida.read())) as imagen:
            self.assertEqual(imagen.format, 'JPEG')
            self.assertLessEqual(max(imagen.size), 1024)
            self.assertEqual(len(imagen.getexif()), 0)

    def test_rechaza_lo_que_no_es_imagen(self):
        from django import forms
        with self.assertRaises(forms.ValidationError):
            recodificar(SimpleUploadedFile('x.jpg', b'no soy una foto'))


class RegistroYRecuperacionTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def test_registro_con_correo_ocupado_no_lo_revela_en_la_pagina(self):
        with mock.patch('finanzas.correo.enviar', return_value=True) as enviar:
            respuesta = self.client.post(reverse('registro'), {
                'username': 'intruso', 'password1': 'Otra-clave-987', 'password2': 'Otra-clave-987',
                'email_perfil': 'ana@ejemplo.cl', 'acepta_politica': '1'})
        self.assertEqual(respuesta.status_code, 302)
        self.assertNotContains(self.client.get(respuesta['Location']), 'Ya hay una cuenta')
        self.assertFalse(User.objects.filter(username='intruso').exists())
        self.assertEqual(enviar.call_args[0][0], 'ana@ejemplo.cl')

    def test_recuperacion_tiene_tope_por_correo(self):
        with mock.patch('finanzas.correo.enviar', return_value=True) as enviar:
            for n in range(6):
                self.client.post(reverse('recuperar'), {'email': 'ana@ejemplo.cl'},
                                 REMOTE_ADDR=f'10.0.0.{n + 1}')
        self.assertEqual(enviar.call_count, 3)


class GoogleTests(TestCase):

    @override_settings(GOOGLE_CLIENT_ID='cliente')
    def test_pide_pkce_y_nonce(self):
        respuesta = self.client.get(reverse('google_entrar'))
        consulta = parse_qs(urlparse(respuesta['Location']).query)
        self.assertEqual(consulta['code_challenge_method'], ['S256'])
        self.assertEqual(consulta['nonce'], [self.client.session['google_nonce']])
        self.assertIn('google_verificador', self.client.session)

    def test_nonce_distinto_se_rechaza(self):
        datos = {'nonce': 'otro'}
        with self.assertRaises(ValueError):
            google_login._validar(datos, 'esperado')
        with self.assertRaises(ValueError):
            google_login._validar(datos, '')


class ChatPorIpTests(TestCase):

    @mock.patch.dict(os.environ, {'CHAT_AYUDA_TOPE_IP': '2'})
    @mock.patch('finanzas.chat_ayuda.responder', return_value='Hola')
    def test_cada_ip_tiene_su_cupo(self, _responder):
        cuerpo = json.dumps({'mensajes': [{'rol': 'user', 'texto': '¿Es gratis?'}]})
        respuestas = [self.client.post(reverse('ayuda_chat'), cuerpo, content_type='application/json',
                                       REMOTE_ADDR='10.1.1.1').json() for _ in range(3)]
        self.assertEqual(respuestas[0].get('texto'), 'Hola')
        self.assertTrue(respuestas[2].get('sin_respuesta'))
        otra = self.client.post(reverse('ayuda_chat'), cuerpo, content_type='application/json',
                                REMOTE_ADDR='10.2.2.2').json()
        self.assertEqual(otra.get('texto'), 'Hola')
