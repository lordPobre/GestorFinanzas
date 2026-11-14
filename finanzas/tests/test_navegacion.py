from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .. import navegacion


def _trozo(html, desde, hasta):
    inicio = html.index(desde)
    return html[inicio:html.index(hasta, inicio)]


class NavegacionTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _html(self, nombre='metas'):
        return self.client.get(reverse(nombre)).content.decode()

    def test_cada_pantalla_tiene_una_sola_etiqueta(self):
        etiquetas = [e['etiqueta'] for e in navegacion.ENTRADAS]
        self.assertEqual(len(etiquetas), len(set(etiquetas)))

    def test_la_barra_lateral_y_la_de_abajo_dicen_lo_mismo(self):
        html = self._html()
        lateral = _trozo(html, 'class="sidebar-nav"', '</nav>')
        barra = _trozo(html, 'class="bottomnav barra-2c"', '</nav>')
        for _clave, etiqueta, _icono, url, _pantallas in navegacion.SECCIONES_2C:
            enlace = f'href="{reverse(url)}" data-label="{etiqueta}"'
            self.assertIn(enlace, lateral)
            self.assertIn(enlace, barra)

    def test_las_secciones_mantienen_su_orden(self):
        html = self._html()
        for desde in ('class="sidebar-nav"', 'class="bottomnav barra-2c"'):
            trozo = _trozo(html, desde, '</nav>')
            posiciones = [trozo.index(f'href="{reverse(s[3])}"') for s in navegacion.SECCIONES_2C]
            self.assertEqual(posiciones, sorted(posiciones), desde)

    def test_marca_la_pantalla_actual(self):
        lateral = _trozo(self._html('por_pagar'), 'class="sidebar-nav"', '</nav>')
        self.assertIn(f'href="{reverse("por_pagar")}" data-label="Pagos" class="nav-item active" '
                      'aria-current="page"', lateral)
        self.assertEqual(lateral.count('aria-current="page"'), 1)

    def test_la_cartola_en_revision_marca_importar(self):
        items = navegacion.armar('revisar_cartola', {}, False)
        activas = [i['clave'] for i in items if i['activa']]
        self.assertEqual(activas, ['importar_cartola'])

    def test_mas_se_marca_fuera_de_las_tres_de_la_barra(self):
        self.assertTrue(navegacion.mas_activo('metas'))
        self.assertTrue(navegacion.mas_activo(None))
        for clave in ('dashboard', 'por_pagar', 'deudas'):
            self.assertFalse(navegacion.mas_activo(clave))

    def test_los_contadores_salen_donde_corresponde(self):
        items = navegacion.armar('metas', {'prestamos_activos': 2, 'cuotas_activas': 3}, False)
        cuentas = {i['clave']: i['cuenta_items'] for i in items}
        self.assertEqual(cuentas['prestamos'], 2)
        self.assertEqual(cuentas['deudas'], 3)
        self.assertIsNone(cuentas['metas'])

    def test_el_menu_de_la_cuenta_trae_lo_de_la_cuenta(self):
        menu = _trozo(self._html(), 'class="topbar-menu f2c-menu"', '</form>')
        for clave in ('perfil', 'encuesta', 'clave_api'):
            self.assertIn(f'href="{reverse(clave)}"', menu)

    def test_resultados_de_la_encuesta_solo_para_el_personal(self):
        url = reverse('encuesta_resultados')
        self.assertNotIn(f'href="{url}"', self._html())
        self.ana.is_staff = True
        self.ana.save(update_fields=['is_staff'])
        self.assertIn(f'href="{url}"', _trozo(self._html(), 'class="topbar-menu f2c-menu"', '</form>'))
