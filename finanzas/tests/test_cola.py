from django.conf import settings
from django.test import TestCase

from .. import cola


def tarea_que_falla():
    raise RuntimeError('falla a propósito')


class ColaTests(TestCase):

    def test_en_las_pruebas_la_cola_corre_al_tiro(self):
        self.assertTrue(cola.sincronica())

    def test_una_tarea_deja_su_resultado(self):
        tarea = cola.encolar('finanzas.cola.latido')
        self.assertEqual(cola.resultado(tarea), {'listo': True, 'ok': True, 'resultado': 'ok'})

    def test_en_modo_sincronico_un_error_de_la_tarea_se_ve_al_tiro(self):
        with self.assertRaisesMessage(RuntimeError, 'falla a propósito'):
            cola.encolar('finanzas.tests.test_cola.tarea_que_falla')

    def test_una_tarea_desconocida_no_esta_lista(self):
        self.assertEqual(cola.resultado('no-existe'), {'listo': False})

    def test_sin_reintentos_para_no_repetir_un_correo_ni_un_cobro(self):
        self.assertEqual(settings.Q_CLUSTER['max_attempts'], 1)
        self.assertGreater(settings.Q_CLUSTER['retry'], settings.Q_CLUSTER['timeout'])

    def test_el_respaldo_no_lleva_lo_que_espera_en_la_cola(self):
        from ..management.commands.respaldar_postgres import TABLAS_SIN_DATOS
        self.assertIn('django_q_ormq', TABLAS_SIN_DATOS)
        self.assertIn('django_q_task', TABLAS_SIN_DATOS)
