from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..urls import RUTAS_ANTIGUAS


class RutasAntiguasTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _ruta(self, patron):
        return '/' + patron.split('<')[0] + ('7/' if '<' in patron else '')

    def _destino(self, patron, nombre):
        if '<' not in patron:
            return reverse(nombre)
        clave = patron.split('<int:')[1].split('>')[0]
        return reverse(nombre, kwargs={clave: 7})

    def test_cada_ruta_antigua_lleva_a_la_nueva(self):
        for patron, nombre in RUTAS_ANTIGUAS:
            with self.subTest(patron=patron):
                respuesta = self.client.get(self._ruta(patron))
                self.assertEqual(respuesta.status_code, 308)
                self.assertEqual(respuesta['Location'], self._destino(patron, nombre))

    def test_un_post_a_la_ruta_antigua_conserva_el_metodo(self):
        respuesta = self.client.post('/pagar-cuota/7/', {'next': 'deudas'})
        self.assertEqual(respuesta.status_code, 308)
        self.assertEqual(respuesta['Location'], reverse('pagar_cuota', args=[7]))

    def test_la_consulta_se_conserva(self):
        respuesta = self.client.get('/registrar/?tipo=INGRESO')
        self.assertEqual(respuesta['Location'], reverse('registrar_transaccion') + '?tipo=INGRESO')

    def test_las_rutas_nuevas_siguen_un_solo_estilo(self):
        self.assertEqual(reverse('crear_deuda'), '/cuotas/nueva/')
        self.assertEqual(reverse('editar_deuda', args=[3]), '/cuotas/3/editar/')
        self.assertEqual(reverse('pagar_servicio', args=[3]), '/suscripciones/3/pagar/')
        self.assertEqual(reverse('aportar_meta', args=[3]), '/metas/3/aportar/')
        self.assertEqual(reverse('editar_categoria', args=[3]), '/categorias/3/editar/')

    def test_ingreso_abre_el_formulario_con_el_tipo(self):
        respuesta = self.client.get(reverse('registrar_ingreso'))
        self.assertRedirects(respuesta, reverse('registrar_transaccion') + '?tipo=INGRESO',
                             fetch_redirect_response=False)
