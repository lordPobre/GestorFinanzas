import json
import os
import struct
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock
from urllib.error import HTTPError, URLError

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from finanzas import push
from finanzas.models import GastoPendiente, Persona, Prestamo, SuscripcionPush, UserProfile
from finanzas.servicios.recordatorios import avisos_del_dia
from finanzas.templatetags.moneda import money
from finanzas.views.recordatorios import MAX_APARATOS, opciones_de

PRIVADA, PUBLICA = push.generar_claves()
CON_CLAVE = override_settings(VAPID_PRIVADA=PRIVADA)
SIN_CLAVE = override_settings(VAPID_PRIVADA='')
FCM = 'https://fcm.googleapis.com/fcm/send/'


def _cruda(privada):
    return privada.public_key().public_bytes(serialization.Encoding.X962,
                                            serialization.PublicFormat.UncompressedPoint)


def aparato():
    privada = ec.generate_private_key(ec.SECP256R1())
    secreto = os.urandom(16)
    return privada, secreto, push.b64(_cruda(privada)), push.b64(secreto)


def descifrar(cuerpo, privada, secreto):
    sal = cuerpo[:16]
    tamano, largo = struct.unpack('!IB', cuerpo[16:21])
    publica_as = cuerpo[21:21 + largo]
    clave_as = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), publica_as)
    compartido = privada.exchange(ec.ECDH(), clave_as)
    ikm = HKDF(hashes.SHA256(), 32, secreto,
               b'WebPush: info\x00' + _cruda(privada) + publica_as).derive(compartido)
    cek = HKDF(hashes.SHA256(), 16, sal, b'Content-Encoding: aes128gcm\x00').derive(ikm)
    nonce = HKDF(hashes.SHA256(), 12, sal, b'Content-Encoding: nonce\x00').derive(ikm)
    return tamano, AESGCM(cek).decrypt(nonce, cuerpo[21 + largo:], None)


def respuesta(estado):
    r = mock.MagicMock()
    r.__enter__.return_value.status = estado
    return r


def error_http(estado):
    return HTTPError(FCM, estado, 'respuesta', {}, None)


def suscripcion(usuario, nombre='a', **extra):
    _, secreto, p256dh, auth = aparato()
    return SuscripcionPush.objects.create(usuario=usuario, endpoint=FCM + nombre,
                                          p256dh=p256dh, auth=auth, **extra)


class CifradoTests(SimpleTestCase):

    def test_el_aparato_descifra_lo_que_se_le_manda(self):
        privada, secreto, p256dh, auth = aparato()
        tamano, claro = descifrar(push.cifrar(b'Hoy vence la luz', p256dh, auth), privada, secreto)
        self.assertEqual(tamano, 4096)
        self.assertEqual(claro, b'Hoy vence la luz\x02')

    def test_cada_envio_usa_sal_y_clave_nuevas(self):
        _, _, p256dh, auth = aparato()
        uno, dos = push.cifrar(b'hola', p256dh, auth), push.cifrar(b'hola', p256dh, auth)
        self.assertNotEqual(uno[:16], dos[:16])
        self.assertNotEqual(uno[21:86], dos[21:86])

    def test_otro_aparato_no_puede_leerlo(self):
        _, _, p256dh, auth = aparato()
        ajeno, secreto_ajeno, _, _ = aparato()
        with self.assertRaises(InvalidTag):
            descifrar(push.cifrar(b'hola', p256dh, auth), ajeno, secreto_ajeno)

    @CON_CLAVE
    def test_la_firma_vapid_es_valida_y_apunta_al_servicio(self):
        cabecera = push.cabecera_vapid(FCM + 'abc', ahora=1_000_000)
        self.assertTrue(cabecera.startswith('vapid t='))
        token, publica = cabecera[len('vapid t='):].split(', k=')
        self.assertEqual(publica, PUBLICA)
        cabeza, reclamos, firma = token.split('.')
        crudo = push.d64(firma)
        self.assertEqual(len(crudo), 64)
        clave = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), push.d64(publica))
        clave.verify(encode_dss_signature(int.from_bytes(crudo[:32], 'big'),
                                          int.from_bytes(crudo[32:], 'big')),
                     f'{cabeza}.{reclamos}'.encode(), ec.ECDSA(hashes.SHA256()))
        self.assertEqual(json.loads(push.d64(cabeza)), {'typ': 'JWT', 'alg': 'ES256'})
        self.assertEqual(json.loads(push.d64(reclamos)), {
            'aud': 'https://fcm.googleapis.com',
            'exp': 1_000_000 + 12 * 60 * 60,
            'sub': settings.VAPID_CONTACTO,
        })


class ClavesTests(SimpleTestCase):

    def test_el_par_generado_calza(self):
        privada, publica = push.generar_claves()
        self.assertEqual(len(push.d64(privada)), 32)
        self.assertEqual(push.d64(publica)[:1], b'\x04')
        with override_settings(VAPID_PRIVADA=privada):
            self.assertTrue(push.disponible())
            self.assertEqual(push.clave_publica(), publica)

    @SIN_CLAVE
    def test_sin_clave_no_hay_recordatorios(self):
        self.assertFalse(push.disponible())
        self.assertEqual(push.clave_publica(), '')

    def test_una_clave_rota_se_anota_y_no_se_usa(self):
        with override_settings(VAPID_PRIVADA='AAAA'), self.assertLogs('finanzas', 'ERROR'):
            self.assertFalse(push.disponible())

    def test_el_comando_entrega_la_variable_lista_para_pegar(self):
        salida = StringIO()
        call_command('generar_vapid', stdout=salida)
        linea = next(x for x in salida.getvalue().splitlines() if x.startswith('VAPID_PRIVADA='))
        valor = linea.split('=', 1)[1]
        self.assertEqual(valor, valor.strip())
        self.assertEqual(len(push.d64(valor)), 32)


class DireccionesTests(SimpleTestCase):

    def test_acepta_los_servicios_de_avisos_conocidos(self):
        for url in (FCM + 'abc',
                    'https://updates.push.services.mozilla.com/wpush/v2/abc',
                    'https://web.push.apple.com/QGx',
                    'https://wns2-par02p.notify.windows.com/w/?token=abc'):
            with self.subTest(url=url):
                self.assertTrue(push.endpoint_valido(url))

    def test_rechaza_cualquier_otra_direccion(self):
        for url in (None, 123, '', 'http://fcm.googleapis.com/fcm/send/abc',
                    'https://ejemplo.cl/fcm.googleapis.com',
                    'https://fcm.googleapis.com.ejemplo.cl/abc',
                    'https://otrofcm.googleapis.com/abc',
                    'https://persona@fcm.googleapis.com/abc',
                    'https://fcm.googleapis.com:8443/abc',
                    'https://127.0.0.1/abc',
                    FCM + 'x' * 500):
            with self.subTest(url=url):
                self.assertFalse(push.endpoint_valido(url))

    def test_revisa_las_claves_del_aparato(self):
        privada, _, p256dh, auth = aparato()
        comprimida = push.b64(privada.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint))
        self.assertTrue(push.claves_validas(p256dh, auth))
        self.assertFalse(push.claves_validas(p256dh, push.b64(os.urandom(15))))
        self.assertFalse(push.claves_validas('no-es-una-clave', auth))
        self.assertFalse(push.claves_validas(comprimida, auth))

    def test_el_aviso_no_pasa_del_tope_y_omite_lo_vacio(self):
        cuerpo = push._carga({'titulo': 'Hola', 'cuerpo': 'x' * 5000, 'url': ''})
        self.assertLessEqual(len(cuerpo), push.MAX_CARGA)
        datos = json.loads(cuerpo)
        self.assertEqual(datos['titulo'], 'Hola')
        self.assertNotIn('url', datos)


class EnvioTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.privada, self.secreto, p256dh, auth = aparato()
        self.sus = SuscripcionPush.objects.create(usuario=self.ana, endpoint=FCM + 'ana',
                                                  p256dh=p256dh, auth=auth)

    @CON_CLAVE
    def test_un_envio_aceptado_va_cifrado_y_firmado(self):
        with mock.patch('finanzas.push.urlopen', return_value=respuesta(201)) as abrir:
            resultado = push.enviar(self.sus, {'titulo': 'Hoy vence Luz', 'cuerpo': 'Toca'})
        self.assertEqual(resultado, 'ok')
        pedido = abrir.call_args[0][0]
        self.assertEqual(pedido.full_url, FCM + 'ana')
        self.assertEqual(pedido.get_method(), 'POST')
        self.assertEqual(pedido.get_header('Content-encoding'), 'aes128gcm')
        self.assertEqual(pedido.get_header('Ttl'), '43200')
        self.assertTrue(pedido.get_header('Authorization').startswith('vapid t='))
        self.assertEqual(abrir.call_args.kwargs['timeout'], 10)
        _, claro = descifrar(pedido.data, self.privada, self.secreto)
        self.assertEqual(json.loads(claro[:-1])['titulo'], 'Hoy vence Luz')
        self.sus.refresh_from_db()
        self.assertIsNotNone(self.sus.ultima_vez)

    @CON_CLAVE
    def test_si_el_aparato_ya_no_existe_se_borra(self):
        for estado in (404, 410):
            with self.subTest(estado=estado):
                sus = suscripcion(self.ana, f'vencida-{estado}')
                with mock.patch('finanzas.push.urlopen', side_effect=error_http(estado)):
                    self.assertEqual(push.enviar(sus, {'titulo': 'x'}), 'vencida')
                self.assertFalse(SuscripcionPush.objects.filter(pk=sus.pk).exists())

    @CON_CLAVE
    def test_una_falla_del_servicio_no_borra_el_aparato(self):
        for falla in (error_http(500), URLError('sin red'), TimeoutError()):
            with self.subTest(falla=type(falla).__name__):
                with mock.patch('finanzas.push.urlopen', side_effect=falla), \
                        self.assertLogs('finanzas', 'WARNING'):
                    self.assertEqual(push.enviar(self.sus, {'titulo': 'x'}), 'error')
                self.assertTrue(SuscripcionPush.objects.filter(pk=self.sus.pk).exists())

    @SIN_CLAVE
    def test_sin_clave_no_sale_nada(self):
        with mock.patch('finanzas.push.urlopen') as abrir:
            self.assertEqual(push.enviar(self.sus, {'titulo': 'x'}), 'error')
        abrir.assert_not_called()
        self.assertTrue(SuscripcionPush.objects.filter(pk=self.sus.pk).exists())

    @CON_CLAVE
    def test_una_direccion_que_no_es_de_un_servicio_se_borra_sin_conectarse(self):
        SuscripcionPush.objects.filter(pk=self.sus.pk).update(endpoint='https://ejemplo.cl/x')
        self.sus.refresh_from_db()
        with mock.patch('finanzas.push.urlopen') as abrir:
            self.assertEqual(push.enviar(self.sus, {'titulo': 'x'}), 'vencida')
        abrir.assert_not_called()
        self.assertFalse(SuscripcionPush.objects.filter(pk=self.sus.pk).exists())

    @CON_CLAVE
    def test_enviar_a_la_cuenta_cuenta_los_que_llegaron(self):
        suscripcion(self.ana, 'otro')
        with mock.patch('finanzas.push.urlopen', side_effect=[respuesta(201), error_http(500)]), \
                self.assertLogs('finanzas', 'WARNING'):
            self.assertEqual(push.enviar_a_usuario(self.ana, {'titulo': 'x'}), 1)


class VistasTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        self.client.force_login(self.ana)
        _, _, self.p256dh, self.auth = aparato()

    def _json(self, nombre, datos):
        cuerpo = datos if isinstance(datos, str) else json.dumps(datos)
        return self.client.post(reverse(nombre), data=cuerpo, content_type='application/json',
                                HTTP_USER_AGENT='Mozilla/5.0 (iPhone)')

    def _suscribir(self, endpoint=FCM + 'uno', p256dh=None, auth=None):
        return self._json('push_suscribir', {'endpoint': endpoint, 'keys': {
            'p256dh': p256dh or self.p256dh, 'auth': auth or self.auth}})

    @CON_CLAVE
    def test_suscribir_guarda_el_aparato(self):
        r = self._suscribir()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
        sus = SuscripcionPush.objects.get()
        self.assertEqual((sus.usuario, sus.endpoint, sus.agente),
                         (self.ana, FCM + 'uno', 'Mozilla/5.0 (iPhone)'))

    @SIN_CLAVE
    def test_sin_clave_suscribir_responde_404(self):
        self.assertEqual(self._suscribir().status_code, 404)
        self.assertFalse(SuscripcionPush.objects.exists())

    @CON_CLAVE
    def test_suscribir_rechaza_datos_malos(self):
        casos = {
            'no es json': 'esto no es json',
            'lista': '[]',
            'sin https': {'endpoint': 'http://fcm.googleapis.com/x',
                          'keys': {'p256dh': self.p256dh, 'auth': self.auth}},
            'otro servidor': {'endpoint': 'https://ejemplo.cl/x',
                              'keys': {'p256dh': self.p256dh, 'auth': self.auth}},
            'sin claves': {'endpoint': FCM + 'x'},
            'auth corta': {'endpoint': FCM + 'x',
                           'keys': {'p256dh': self.p256dh, 'auth': push.b64(b'corta')}},
        }
        for nombre, datos in casos.items():
            with self.subTest(caso=nombre):
                self.assertEqual(self._json('push_suscribir', datos).status_code, 400)
        self.assertFalse(SuscripcionPush.objects.exists())

    @CON_CLAVE
    def test_el_mismo_aparato_no_se_duplica_y_queda_con_quien_entro(self):
        self._suscribir()
        self.client.force_login(self.beto)
        self._suscribir()
        sus = SuscripcionPush.objects.get()
        self.assertEqual(sus.usuario, self.beto)

    @CON_CLAVE
    def test_cada_cuenta_guarda_hasta_diez_aparatos(self):
        ahora = timezone.now()
        for n in range(MAX_APARATOS):
            suscripcion(self.ana, f'viejo-{n}', creada=ahora - timedelta(days=n + 1))
        self._suscribir(FCM + 'nuevo')
        self.assertEqual(SuscripcionPush.objects.filter(usuario=self.ana).count(), MAX_APARATOS)
        self.assertTrue(SuscripcionPush.objects.filter(endpoint=FCM + 'nuevo').exists())
        self.assertFalse(SuscripcionPush.objects.filter(endpoint=FCM + f'viejo-{MAX_APARATOS - 1}').exists())

    def test_quitar_solo_borra_lo_propio(self):
        de_beto = suscripcion(self.beto, 'beto')
        propia = suscripcion(self.ana, 'ana')
        self.assertEqual(self._json('push_quitar', {'endpoint': de_beto.endpoint}).json()['borradas'], 0)
        self.assertTrue(SuscripcionPush.objects.filter(pk=de_beto.pk).exists())
        self.assertEqual(self._json('push_quitar', {'endpoint': propia.endpoint}).json()['borradas'], 1)
        self.assertFalse(SuscripcionPush.objects.filter(pk=propia.pk).exists())

    @CON_CLAVE
    def test_probar_manda_a_la_cuenta_y_espera_entre_pruebas(self):
        with mock.patch.object(push, 'enviar_a_usuario', return_value=2) as enviar:
            primera = self._json('push_probar', {})
            segunda = self._json('push_probar', {})
        self.assertEqual(primera.json(), {'ok': True, 'enviados': 2})
        self.assertEqual(segunda.status_code, 429)
        self.assertEqual(enviar.call_count, 1)
        self.assertEqual(enviar.call_args[0][0], self.ana)

    @SIN_CLAVE
    def test_sin_clave_probar_responde_404(self):
        self.assertEqual(self._json('push_probar', {}).status_code, 404)

    def test_las_rutas_piden_sesion_y_post(self):
        for nombre in ('push_suscribir', 'push_quitar', 'push_probar'):
            with self.subTest(ruta=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 405)
        self.client.logout()
        for nombre in ('push_suscribir', 'push_quitar', 'push_probar'):
            with self.subTest(ruta=nombre, sesion=False):
                self.assertEqual(self._json(nombre, {}).status_code, 302)

    def test_perfil_guarda_solo_las_opciones_de_recordatorios(self):
        url = reverse('perfil')
        self.client.post(url, {'accion': 'recordatorios', 'campo': 'push_montos', 'activar': '1'})
        self.client.post(url, {'accion': 'recordatorios', 'campo': 'push_vence', 'activar': '0'})
        self.client.post(url, {'accion': 'recordatorios', 'campo': 'analisis_ia', 'activar': '0'})
        perfil = UserProfile.objects.get(usuario=self.ana)
        self.assertTrue(perfil.push_montos)
        self.assertFalse(perfil.push_vence)
        self.assertTrue(perfil.analisis_ia)

    def test_las_opciones_por_defecto_no_muestran_montos(self):
        perfil, _ = UserProfile.objects.get_or_create(usuario=self.ana)
        filas = {f['campo']: f for f in opciones_de(perfil)}
        self.assertEqual({c: f['activo'] for c, f in filas.items()}, {
            'push_vence': True, 'push_dia_antes': True, 'push_topes': False,
            'push_resumen': False, 'push_montos': False,
        })
        self.assertTrue(filas['push_montos']['nota'].startswith('Apagado'))

    @CON_CLAVE
    def test_perfil_ofrece_los_recordatorios_con_clave(self):
        r = self.client.get(reverse('perfil'))
        self.assertContains(r, 'data-push')
        self.assertEqual(r.context['push_clave'], PUBLICA)
        self.assertEqual(len(r.context['opciones_push']), 5)

    @SIN_CLAVE
    def test_perfil_explica_si_no_hay_clave(self):
        r = self.client.get(reverse('perfil'))
        self.assertContains(r, 'Todavía no están disponibles')
        self.assertNotContains(r, 'data-suscribir')

    def test_la_descarga_de_datos_trae_aparatos_y_topes(self):
        suscripcion(self.ana, 'ana')
        suscripcion(self.beto, 'beto')
        datos = self.client.get(reverse('mis_datos')).json()
        self.assertEqual(len(datos['aparatos_con_recordatorios']), 1)
        self.assertIn('topes_por_categoria', datos)


class InvitacionTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        GastoPendiente.objects.create(usuario=self.ana, nombre='Luz', monto=Decimal('25990'),
                                      fecha_vencimiento=date.today())

    @CON_CLAVE
    def test_invita_si_algo_vence_pronto(self):
        r = self.client.get(reverse('dashboard'))
        self.assertTrue(r.context['push_invitacion'].startswith('Hoy vence Luz'))
        self.assertContains(r, 'data-push-invitacion')

    @CON_CLAVE
    def test_no_invita_si_la_cuenta_ya_tiene_avisos(self):
        suscripcion(self.ana)
        r = self.client.get(reverse('dashboard'))
        self.assertNotContains(r, 'data-push-invitacion')

    @SIN_CLAVE
    def test_no_invita_sin_clave(self):
        r = self.client.get(reverse('dashboard'))
        self.assertNotContains(r, 'data-push-invitacion')


class AvisosDelDiaTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil, _ = UserProfile.objects.get_or_create(usuario=self.ana)
        self.hoy = date.today()

    def _cuenta(self, nombre, cuando, monto='25990'):
        return GastoPendiente.objects.create(usuario=self.ana, nombre=nombre, monto=Decimal(monto),
                                             fecha_vencimiento=cuando)

    def test_lo_que_vence_hoy_sale_sin_montos(self):
        self._cuenta('Luz', self.hoy)
        avisos = avisos_del_dia(self.ana, self.perfil, self.hoy)
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]['titulo'], 'Hoy vence Luz')
        self.assertEqual(avisos[0]['cuerpo'], 'Toca para verlo en Fintora.')
        self.assertEqual((avisos[0]['url'], avisos[0]['etiqueta']), ('/', 'cobros-hoy'))

    def test_con_montos_dice_cuanto_es(self):
        self._cuenta('Luz', self.hoy)
        self.perfil.push_montos = True
        aviso = avisos_del_dia(self.ana, self.perfil, self.hoy)[0]
        self.assertIn(money(Decimal('25990.00'), '$'), aviso['cuerpo'])

    def test_avisa_el_dia_antes(self):
        self._cuenta('Agua', self.hoy + timedelta(days=1))
        avisos = avisos_del_dia(self.ana, self.perfil, self.hoy)
        self.assertEqual([a['titulo'] for a in avisos], ['Mañana se cobra Agua'])

    def test_varios_cobros_van_en_un_solo_aviso(self):
        for nombre in ('Luz', 'Agua', 'Gas'):
            self._cuenta(nombre, self.hoy)
        avisos = avisos_del_dia(self.ana, self.perfil, self.hoy)
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]['titulo'], 'Hoy vencen 3 pagos')
        for nombre in ('Luz', 'Agua', 'Gas'):
            self.assertIn(nombre, avisos[0]['cuerpo'])

    def test_con_las_opciones_apagadas_no_avisa(self):
        self._cuenta('Luz', self.hoy)
        self._cuenta('Agua', self.hoy + timedelta(days=1))
        self.perfil.push_vence = self.perfil.push_dia_antes = False
        self.assertEqual(avisos_del_dia(self.ana, self.perfil, self.hoy), [])

    def test_lo_que_debes_avisa_y_lo_que_te_deben_no(self):
        carla = Persona.objects.create(usuario=self.ana, nombre='Carla', lado='LE_DEBO')
        diego = Persona.objects.create(usuario=self.ana, nombre='Diego', lado='ME_DEBE')
        for persona in (carla, diego):
            Prestamo.objects.create(persona=persona, descripcion='Préstamo', monto=Decimal('300000'),
                                    tipo='CUOTAS', cuotas_totales=3, fecha=self.hoy)
        avisos = avisos_del_dia(self.ana, self.perfil, self.hoy)
        self.assertEqual([a['titulo'] for a in avisos], ['Hoy vence Carla'])
        self.assertTrue(avisos[0]['cuerpo'].startswith('Le debes · cuota 1 de 3'))

    def test_el_resumen_sale_solo_el_domingo(self):
        self.perfil.push_vence = self.perfil.push_dia_antes = False
        self.perfil.push_resumen = True
        domingo = self.hoy + timedelta(days=(6 - self.hoy.weekday()) % 7)
        avisos = avisos_del_dia(self.ana, self.perfil, domingo)
        self.assertEqual([a['titulo'] for a in avisos], ['Cómo va tu mes'])
        self.assertTrue(avisos[0]['cuerpo'].endswith('Toca para ver el detalle.'))
        self.assertEqual(avisos_del_dia(self.ana, self.perfil, domingo + timedelta(days=1)), [])


class ComandoTests(TestCase):

    def setUp(self):
        self.hoy = timezone.localdate()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        suscripcion(self.ana, 'ana')
        GastoPendiente.objects.create(usuario=self.ana, nombre='Luz', monto=Decimal('25990'),
                                      fecha_vencimiento=self.hoy)

    def _correr(self, *args):
        salida = StringIO()
        call_command('enviar_recordatorios', *args, stdout=salida)
        return salida.getvalue()

    @CON_CLAVE
    def test_manda_una_vez_al_dia(self):
        with mock.patch.object(push, 'enviar_a_usuario', return_value=1) as enviar:
            salida = self._correr()
            self.assertEqual(enviar.call_count, 1)
            usuario, aviso = enviar.call_args[0]
            self.assertEqual(usuario, self.ana)
            self.assertEqual(aviso['titulo'], 'Hoy vence Luz')
            self.assertIn('1 avisos a 1 persona.', salida)
            self.assertEqual(UserProfile.objects.get(usuario=self.ana).push_ultimo_dia, self.hoy)
            self._correr()
            self.assertEqual(enviar.call_count, 1)
            self._correr('--forzar')
            self.assertEqual(enviar.call_count, 2)

    @SIN_CLAVE
    def test_sin_clave_no_manda_nada(self):
        with mock.patch.object(push, 'enviar_a_usuario') as enviar:
            self.assertIn('Falta VAPID_PRIVADA', self._correr())
        enviar.assert_not_called()

    @CON_CLAVE
    def test_cuentas_inactivas_o_sin_aparato_no_reciben(self):
        beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2', is_active=False)
        carla = User.objects.create_user('carla', 'carla@ejemplo.cl', 'clave-larga-3')
        suscripcion(beto, 'beto')
        for usuario in (beto, carla):
            GastoPendiente.objects.create(usuario=usuario, nombre='Luz', monto=Decimal('1000'),
                                          fecha_vencimiento=self.hoy)
        with mock.patch.object(push, 'enviar_a_usuario', return_value=1) as enviar:
            self._correr()
        self.assertEqual({c[0][0] for c in enviar.call_args_list}, {self.ana})

    @CON_CLAVE
    def test_una_cuenta_con_error_no_frena_a_las_demas(self):
        beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        suscripcion(beto, 'beto')

        def armar(usuario, *args):
            if usuario == self.ana:
                raise RuntimeError('falla')
            return [{'titulo': 'Hola'}]

        with mock.patch('finanzas.management.commands.enviar_recordatorios.avisos_del_dia',
                        side_effect=armar), \
                mock.patch.object(push, 'enviar_a_usuario', return_value=1) as enviar, \
                self.assertLogs('finanzas', 'ERROR'):
            self._correr()
        self.assertEqual([c[0][0] for c in enviar.call_args_list], [beto])
        self.assertIsNone(UserProfile.objects.get(usuario=self.ana).push_ultimo_dia)
        self.assertEqual(UserProfile.objects.get(usuario=beto).push_ultimo_dia, self.hoy)
