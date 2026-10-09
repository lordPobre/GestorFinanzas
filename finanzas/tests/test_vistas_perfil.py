from django.test import SimpleTestCase
from django.urls import resolve, reverse

from ..views import cuenta
from ..views import perfil as vistas_perfil


class SeparacionDePerfilTests(SimpleTestCase):

    def test_las_rutas_del_perfil_usan_las_vistas_de_perfil(self):
        for nombre, vista in (('perfil', vistas_perfil.perfil), ('mis_datos', vistas_perfil.mis_datos),
                              ('eliminar_cuenta', vistas_perfil.eliminar_cuenta)):
            self.assertIs(resolve(reverse(nombre)).func, vista, nombre)

    def test_cuenta_sigue_exponiendo_lo_que_movi(self):
        self.assertIs(cuenta.perfil, vistas_perfil.perfil)
        self.assertEqual(cuenta.SAL_CAMBIO_CORREO, vistas_perfil.SAL_CAMBIO_CORREO)
