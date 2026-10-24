from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .. import legal
from ..models import UserProfile


class PantallaPreguntasTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil, _ = UserProfile.objects.update_or_create(
            usuario=self.ana, defaults={'onboarding_completado': True, 'analisis_ia': True,
                                        'politica_version': legal.VERSION})
        self.client.force_login(self.ana)

    def test_inicio_trae_el_boton_y_el_panel(self):
        r = self.client.get(reverse('dashboard'))
        self.assertContains(r, 'data-charla-abrir')
        self.assertContains(r, 'data-charla ')
        self.assertContains(r, f'data-url="{reverse("esfera_preguntar")}"')
        self.assertContains(r, 'js/pantallas/esfera-preguntas.js')
        self.assertContains(r, 'css/esfera-preguntas.css')
        self.assertContains(r, 'name="pregunta"')

    def test_sin_ia_no_hay_preguntas(self):
        self.perfil.analisis_ia = False
        self.perfil.save(update_fields=['analisis_ia'])
        r = self.client.get(reverse('dashboard'))
        self.assertNotContains(r, 'data-charla-abrir')
        self.assertNotContains(r, 'data-charla ')

    def test_la_esfera_del_panel_no_repite_el_nombre_de_transicion(self):
        r = self.client.get(reverse('dashboard'))
        self.assertEqual(r.content.decode().count('ini-esfera-bola'), 1)

    def test_las_otras_pantallas_con_esfera_traen_el_panel(self):
        for nombre in ('deudas', 'metas', 'prestamos', 'suscripciones'):
            with self.subTest(pantalla=nombre):
                r = self.client.get(reverse(nombre))
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, 'data-charla-abrir')
                self.assertContains(r, 'data-charla ')
                self.assertContains(r, 'js/pantallas/esfera-preguntas.js', count=1)
                self.assertContains(r, 'css/esfera-preguntas.css', count=1)

    def test_inicio_no_repite_el_panel(self):
        r = self.client.get(reverse('dashboard'))
        self.assertContains(r, 'js/pantallas/esfera-preguntas.js', count=1)
        self.assertContains(r, 'css/esfera-preguntas.css', count=1)
        self.assertEqual(r.content.decode().count('data-charla '), 1)

    def test_cada_pantalla_trae_sus_ideas(self):
        self.assertContains(self.client.get(reverse('deudas')), 'los próximos 3 meses')
        self.assertContains(self.client.get(reverse('metas')), '¿Cómo van mis metas?')
        self.assertContains(self.client.get(reverse('dashboard')), 'zapatillas')

    def test_sin_esfera_no_hay_panel(self):
        r = self.client.get(reverse('estadisticas'))
        self.assertNotContains(r, 'data-charla ')
        self.assertNotContains(r, 'esfera-preguntas.js')

    def test_sin_ia_las_otras_pantallas_no_traen_el_panel(self):
        self.perfil.analisis_ia = False
        self.perfil.save(update_fields=['analisis_ia'])
        r = self.client.get(reverse('deudas'))
        self.assertNotContains(r, 'data-charla')
        self.assertNotContains(r, 'esfera-preguntas')

    def test_en_escritorio_la_tarjeta_de_salud_abre_el_panel(self):
        for nombre in ('dashboard', 'deudas', 'suscripciones'):
            with self.subTest(pantalla=nombre):
                r = self.client.get(reverse(nombre))
                self.assertContains(r, 'data-tour="salud" data-charla-abrir')
                self.assertContains(r, 'Toca para preguntar')
                self.assertContains(r, 'data-charla-velo')

    def test_sin_ia_la_tarjeta_de_salud_no_abre_nada(self):
        self.perfil.analisis_ia = False
        self.perfil.save(update_fields=['analisis_ia'])
        r = self.client.get(reverse('dashboard'))
        self.assertNotContains(r, 'Toca para preguntar')
        self.assertNotContains(r, 'data-charla-velo')

    def test_sin_esfera_la_tarjeta_de_salud_no_abre_nada(self):
        r = self.client.get(reverse('estadisticas'))
        self.assertNotContains(r, 'data-tour="salud" data-charla-abrir')
        self.assertNotContains(r, 'Toca para preguntar')
