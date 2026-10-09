from django.test import SimpleTestCase
from django.urls import resolve, reverse

from ..views import acceso, cuenta


class SeparacionDeCuentaTests(SimpleTestCase):

    def test_las_rutas_de_entrada_usan_las_vistas_de_acceso(self):
        for nombre, vista in (('login', acceso.entrar), ('verificar_codigo', acceso.verificar_codigo),
                              ('configurar_2fa', acceso.configurar_2fa)):
            self.assertIs(resolve(reverse(nombre)).func, vista, nombre)

    def test_cuenta_sigue_exponiendo_lo_que_movi(self):
        self.assertIs(cuenta.entrar, acceso.entrar)
        self.assertIs(cuenta.configurar_2fa, acceso.configurar_2fa)
        self.assertIs(cuenta._clave_sesion, acceso._clave_sesion)
