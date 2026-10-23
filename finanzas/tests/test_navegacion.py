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

    def test_la_barra_lateral_y_la_hoja_dicen_lo_mismo(self):
        html = self._html()
        lateral = _trozo(html, 'class="sidebar-nav"', '</nav>')
        hoja = _trozo(html, 'class="hoja-grid"', 'class="hoja-salir"')
        for e in navegacion.ENTRADAS:
            if e.get('solo_personal'):
                continue
            url = reverse(e['clave'])
            if e.get('grupo'):
                self.assertIn(f'href="{url}" data-label="{e["etiqueta"]}"', lateral)
            if e.get('hoja'):
                trozo = _trozo(hoja, f'href="{url}"', '</a>')
                self.assertIn(f'<span>{e["etiqueta"]}</span>', trozo)

    def test_la_hoja_mantiene_su_orden(self):
        hoja = _trozo(self._html(), 'class="hoja-grid"', 'class="hoja-salir"')
        claves = [e['clave'] for e in sorted(navegacion.ENTRADAS, key=lambda e: e.get('hoja') or 0)
                  if e.get('hoja') and not e.get('solo_personal')]
        posiciones = [hoja.index(f'href="{reverse(c)}"') for c in claves]
        self.assertEqual(posiciones, sorted(posiciones))

    def test_marca_la_pantalla_actual(self):
        lateral = _trozo(self._html('por_pagar'), 'class="sidebar-nav"', '</nav>')
        self.assertIn(f'href="{reverse("por_pagar")}" data-label="Por pagar" class="nav-item active" '
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

    def test_resultados_de_la_encuesta_solo_para_el_personal(self):
        url = reverse('encuesta_resultados')
        self.assertNotIn(f'href="{url}"', self._html())
        self.ana.is_staff = True
        self.ana.save(update_fields=['is_staff'])
        html = self._html()
        self.assertIn(f'href="{url}"', _trozo(html, 'class="topbar-menu"', '</form>'))
        self.assertIn(f'href="{url}"', _trozo(html, 'class="hoja-grid"', 'class="hoja-salir"'))
