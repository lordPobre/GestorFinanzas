import json
import os
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas import marketing

PIXELES = {
    'GA4_ID': 'G-PRUEBA1',
    'META_PIXEL_ID': '1234567890',
    'TIKTOK_PIXEL_ID': 'CPRUEBA',
    'X_PIXEL_ID': 'oprueba',
    'PLAUSIBLE_DOMINIO': 'fintora.cl',
    'GOOGLE_SITE_VERIFICATION': 'codigo-de-prueba',
}
VACIO = {k: '' for k in PIXELES}


class BuscadoresTests(TestCase):
    def test_robots_deja_entrar_solo_a_lo_publico(self):
        texto = self.client.get('/robots.txt').content.decode('utf-8')
        self.assertIn('Allow: /$', texto)
        self.assertIn('Allow: /privacidad/', texto)
        self.assertIn('Allow: /static/', texto)
        self.assertIn('Allow: /sitemap.xml$', texto)
        self.assertIn('Disallow: /', texto)
        self.assertIn(f'Sitemap: {marketing.SITIO}/sitemap.xml', texto)

    def test_sitemap_trae_las_paginas_publicas(self):
        xml = self.client.get('/sitemap.xml').content.decode('utf-8')
        for ruta in marketing.RUTAS_PUBLICAS:
            self.assertIn(f'<loc>{marketing.SITIO}{ruta}</loc>', xml)
        self.assertNotIn('/perfil/', xml)

    def test_la_portada_trae_canonical_imagen_y_datos_estructurados(self):
        cuerpo = self.client.get(reverse('dashboard')).content.decode('utf-8')
        self.assertIn(f'<link rel="canonical" href="{marketing.SITIO}/">', cuerpo)
        self.assertIn('og-fintora.png', cuerpo)
        self.assertIn('summary_large_image', cuerpo)
        trozo = cuerpo.split('<script type="application/ld+json"')[1].split('>', 1)[1].split('</script>')[0]
        datos = json.loads(trozo)
        tipos = [n['@type'] for n in datos['@graph']]
        self.assertIn('WebApplication', tipos)
        self.assertIn('FAQPage', tipos)

    def test_las_paginas_legales_tienen_descripcion(self):
        for nombre in ('privacidad', 'terminos', 'seguridad'):
            with self.subTest(pagina=nombre):
                cuerpo = self.client.get(reverse(nombre)).content.decode('utf-8')
                self.assertNotIn('<meta name="description" content="">', cuerpo)
                self.assertIn(f'href="{marketing.SITIO}{reverse(nombre)}"', cuerpo)

    def test_lo_publico_se_puede_indexar(self):
        for ruta in ('/', '/privacidad/', '/login/'):
            with self.subTest(ruta=ruta):
                self.assertNotIn('X-Robots-Tag', self.client.get(ruta).headers)

    def test_la_app_queda_fuera_de_google(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(ana)
        respuesta = self.client.get(reverse('dashboard'))
        self.assertEqual(respuesta.headers.get('X-Robots-Tag'), 'noindex, nofollow')


class PixelesTests(TestCase):
    def test_sin_ids_no_se_carga_nada(self):
        with mock.patch.dict(os.environ, VACIO):
            respuesta = self.client.get(reverse('dashboard'))
        cuerpo = respuesta.content.decode('utf-8')
        self.assertNotIn('data-cookies', cuerpo)
        self.assertNotIn('plausible', cuerpo)
        self.assertNotIn('facebook', respuesta.headers['Content-Security-Policy'])

    def test_con_ids_la_portada_pide_permiso(self):
        with mock.patch.dict(os.environ, PIXELES):
            respuesta = self.client.get(reverse('dashboard'))
        cuerpo = respuesta.content.decode('utf-8')
        self.assertIn('data-cookies', cuerpo)
        self.assertIn('data-meta="1234567890"', cuerpo)
        self.assertIn('data-domain="fintora.cl"', cuerpo)
        self.assertIn('codigo-de-prueba', cuerpo)
        politica = respuesta.headers['Content-Security-Policy']
        self.assertIn('https://connect.facebook.net', politica)
        self.assertIn('https://www.googletagmanager.com', politica)

    def test_dentro_de_la_app_no_hay_pixeles(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(ana)
        with mock.patch.dict(os.environ, PIXELES):
            respuesta = self.client.get(reverse('dashboard'))
        self.assertNotIn('data-cookies', respuesta.content.decode('utf-8'))
        self.assertNotIn('facebook', respuesta.headers['Content-Security-Policy'])

    def test_los_scripts_llevan_nonce(self):
        with mock.patch.dict(os.environ, PIXELES):
            for ruta in ('/', '/privacidad/'):
                cuerpo = self.client.get(ruta).content.decode('utf-8')
                for trozo in cuerpo.split('<script')[1:]:
                    self.assertIn('nonce=', trozo.split('>')[0])

    def test_la_politica_declara_la_medicion(self):
        cuerpo = self.client.get(reverse('privacidad')).content.decode('utf-8')
        self.assertIn('id="medicion"', cuerpo)
        for proveedor in ('Plausible', 'Google Analytics', 'Meta', 'TikTok'):
            self.assertIn(proveedor, cuerpo)
