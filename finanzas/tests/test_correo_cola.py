import os
from unittest import mock

from django.test import RequestFactory, TestCase, override_settings

from .. import alta, correo

DESTINO = 'ana@ejemplo.cl'


@override_settings(ES_STAGING=False)
class CorreoEnLaColaTests(TestCase):

    def test_en_modo_sincronico_devuelve_lo_que_dijo_resend(self):
        with mock.patch('finanzas.correo.enviar', return_value=True):
            self.assertTrue(correo.encolar(DESTINO, 'Asunto', 'Texto'))
        with mock.patch('finanzas.correo.enviar', return_value=False):
            self.assertFalse(correo.encolar(DESTINO, 'Asunto', 'Texto'))

    def test_la_tarea_manda_lo_mismo_que_antes(self):
        with mock.patch('finanzas.correo.enviar', return_value=True) as enviar:
            correo.encolar(DESTINO, 'Asunto', 'Texto')
            correo.encolar(DESTINO, 'Asunto', 'Texto', '<p>Texto</p>')
        self.assertEqual(enviar.call_args_list, [
            mock.call(DESTINO, 'Asunto', 'Texto'),
            mock.call(DESTINO, 'Asunto', 'Texto', '<p>Texto</p>'),
        ])

    def test_un_error_al_enviar_no_tumba_la_tarea(self):
        with mock.patch('finanzas.correo.enviar', side_effect=RuntimeError('caído')), \
                self.assertLogs('finanzas', 'ERROR'):
            self.assertFalse(correo.enviar_desde_cola(DESTINO, 'Asunto', 'Texto'))

    def test_con_la_cola_real_vuelve_al_tiro_y_no_guarda_el_contenido(self):
        with mock.patch.dict(os.environ, {'RESEND_API_KEY': 'prueba'}), \
                mock.patch('finanzas.cola.sincronica', return_value=False), \
                mock.patch('finanzas.cola.encolar', return_value='t1') as encolar, \
                mock.patch('finanzas.correo.enviar') as enviar:
            self.assertTrue(correo.encolar(DESTINO, 'Asunto', 'Texto'))
        enviar.assert_not_called()
        encolar.assert_called_once_with(correo.RUTA_TAREA, DESTINO, 'Asunto', 'Texto',
                                        q_options={'save': False})

    def test_con_la_cola_real_y_sin_resend_avisa_al_tiro(self):
        with mock.patch.dict(os.environ, {'RESEND_API_KEY': ''}), \
                mock.patch('finanzas.cola.sincronica', return_value=False), \
                mock.patch('finanzas.cola.encolar') as encolar, \
                self.assertLogs('finanzas', 'ERROR'):
            self.assertFalse(correo.encolar(DESTINO, 'Asunto', 'Texto'))
        encolar.assert_not_called()

    def test_si_la_cola_no_responde_el_correo_sale_igual(self):
        with mock.patch.dict(os.environ, {'RESEND_API_KEY': 'prueba'}), \
                mock.patch('finanzas.cola.sincronica', return_value=False), \
                mock.patch('finanzas.cola.encolar', side_effect=RuntimeError('sin base')), \
                mock.patch('finanzas.correo.enviar', return_value=True) as enviar, \
                self.assertLogs('finanzas', 'ERROR'):
            self.assertTrue(correo.encolar(DESTINO, 'Asunto', 'Texto'))
        enviar.assert_called_once_with(DESTINO, 'Asunto', 'Texto')

    def test_el_registro_deja_el_correo_en_la_cola(self):
        request = RequestFactory().post('/registro/')
        with mock.patch('finanzas.correo.encolar', return_value=True) as encolar, \
                mock.patch('finanzas.correo.enviar') as enviar:
            alta.pedir(request, 'nueva', 'Clave-segura-123', 'nueva@ejemplo.cl')
        encolar.assert_called_once()
        enviar.assert_not_called()
