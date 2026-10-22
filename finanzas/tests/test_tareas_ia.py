from unittest import mock

from django.contrib.auth.models import User
from django.core import signing
from django.test import TestCase
from django.urls import reverse
from django_q.models import Task

from .. import tareas_ia
from ..views.comun import get_or_create_profile

IA = {'diagnostico': 'Vas bien.', 'recomendaciones': ['Ahorra un poco.']}


class TareasIATests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'Clave-segura-123')
        self.perfil = get_or_create_profile(self.ana)
        self.client.force_login(self.ana)

    def _firmar(self, tarea, usuario):
        return signing.dumps({'t': tarea, 'u': usuario.pk}, salt=tareas_ia.SAL)

    def test_en_modo_sincronico_responde_como_antes_y_no_deja_la_tarea(self):
        with mock.patch('finanzas.ia.interpretar_con_ia', return_value=IA):
            r = self.client.post(reverse('analisis_ia'))
        self.assertEqual(r.json(), {'ok': True, 'ia': IA})
        self.assertFalse(Task.objects.filter(group=tareas_ia.GRUPO).exists())

    def test_con_la_cola_real_devuelve_un_numero_de_tarea(self):
        with mock.patch('finanzas.cola.sincronica', return_value=False), \
                mock.patch('finanzas.cola.encolar', return_value='t1') as encolar, \
                mock.patch('finanzas.ia.interpretar_con_ia') as interpretar:
            r = self.client.post(reverse('analisis_ia'))
        interpretar.assert_not_called()
        self.assertEqual(encolar.call_args[0][0], 'finanzas.tareas_ia.interpretar')
        firmado = r.json()['tarea']
        self.assertEqual(signing.loads(firmado, salt=tareas_ia.SAL), {'t': 't1', 'u': self.ana.pk})

    def test_la_pantalla_recibe_el_resultado_cuando_esta_listo(self):
        firmado = self._firmar('t1', self.ana)
        url = reverse('tarea_ia')
        with mock.patch('finanzas.cola.recoger', return_value={'listo': False}):
            self.assertEqual(self.client.get(url, {'t': firmado}).json(), {'listo': False})
        listo = {'listo': True, 'ok': True, 'resultado': {'ok': True, 'ia': IA}}
        with mock.patch('finanzas.cola.recoger', return_value=listo):
            self.assertEqual(self.client.get(url, {'t': firmado}).json(), {'listo': True, 'ok': True, 'ia': IA})

    def test_una_tarea_que_fallo_se_ve_como_ia_no_disponible(self):
        fallida = {'listo': True, 'ok': False, 'resultado': None}
        with mock.patch('finanzas.cola.recoger', return_value=fallida):
            r = self.client.get(reverse('tarea_ia'), {'t': self._firmar('t1', self.ana)})
        self.assertEqual(r.json(), {'listo': True, 'ok': False, 'msg': 'IA no disponible'})

    def test_nadie_puede_leer_la_tarea_de_otra_persona(self):
        beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'Clave-segura-456')
        with mock.patch('finanzas.cola.recoger') as recoger:
            ajena = self.client.get(reverse('tarea_ia'), {'t': self._firmar('t1', beto)})
            inventada = self.client.get(reverse('tarea_ia'), {'t': 't1'})
        recoger.assert_not_called()
        self.assertEqual(ajena.status_code, 404)
        self.assertEqual(inventada.status_code, 404)

    def test_si_apagan_la_ia_antes_de_que_corra_la_tarea_no_se_llama(self):
        self.perfil.analisis_ia = False
        self.perfil.save(update_fields=['analisis_ia'])
        with mock.patch('finanzas.ia.interpretar_con_ia') as interpretar:
            self.assertEqual(tareas_ia.interpretar(self.ana.pk, '$'), tareas_ia.SIN_IA)
        interpretar.assert_not_called()

    def test_si_la_cola_no_responde_la_ia_corre_al_tiro(self):
        with mock.patch('finanzas.cola.sincronica', return_value=False), \
                mock.patch('finanzas.cola.encolar', side_effect=RuntimeError('sin base')), \
                mock.patch('finanzas.ia.interpretar_con_ia', return_value=IA), \
                self.assertLogs('finanzas', 'ERROR'):
            r = self.client.post(reverse('analisis_ia'))
        self.assertEqual(r.json(), {'ok': True, 'ia': IA})
