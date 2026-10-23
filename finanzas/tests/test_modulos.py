import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
PLANTILLAS = RAIZ / 'finanzas' / 'templates' / 'finanzas'
JS = RAIZ / 'static' / 'js'
ETIQUETA = re.compile(r"<script([^>]*?)\ssrc=\"\{% static 'js/([\w/-]+)\.js' %\}\"([^>]*)>")
CLASICOS = {'pantallas/modales-temprano', 'pantallas/registro-sw', 'pantallas/barra-estado', 'pantallas/saludo-hora'}
AL_USAR = ('pantallas/anotar', 'pantallas/anotar-tope', 'pantallas/panel-anotar', 'tour')


def etiquetas():
    for plantilla in sorted(PLANTILLAS.glob('*.html')):
        texto = plantilla.read_text(encoding='utf-8')
        if plantilla.name != 'base.html' and "{% extends 'finanzas/base.html' %}" not in texto:
            continue
        for m in ETIQUETA.finditer(texto):
            yield plantilla.name, m.group(2), m.group(1) + m.group(3)


class ModulosTests(SimpleTestCase):

    def test_hay_scripts_que_revisar(self):
        self.assertGreater(len(list(etiquetas())), 40)

    def test_la_app_carga_sus_scripts_como_modulos(self):
        for plantilla, archivo, atributos in etiquetas():
            if archivo in CLASICOS:
                continue
            with self.subTest(plantilla=plantilla, archivo=archivo):
                self.assertIn('type="module"', atributos)
                self.assertIn('nonce=', atributos)

    def test_los_que_tienen_que_correr_antes_siguen_clasicos(self):
        vistos = set()
        for _plantilla, archivo, atributos in etiquetas():
            if archivo in CLASICOS:
                vistos.add(archivo)
                self.assertNotIn('type="module"', atributos, archivo)
        self.assertEqual(vistos, CLASICOS)

    def test_un_modulo_que_lee_su_etiqueta_la_encuentra(self):
        for plantilla, archivo, atributos in etiquetas():
            codigo = (JS / f'{archivo}.js').read_text(encoding='utf-8')
            if archivo in CLASICOS or 'currentScript' not in codigo:
                continue
            nombre = archivo.rsplit('/', 1)[-1]
            with self.subTest(plantilla=plantilla, archivo=archivo):
                self.assertIn(f'data-js="{nombre}"', atributos)
                self.assertIn(f'script[data-js="{nombre}"]', codigo)

    def test_lo_que_se_carga_al_usarlo_no_va_en_una_etiqueta(self):
        for plantilla, archivo, _ in etiquetas():
            self.assertNotIn(archivo, AL_USAR, plantilla)
