import json
import os
import unittest
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse

from .. import legal
from ..models import Deuda, Persona, Suscripcion, Transaccion, UserProfile
from .test_navegador import ESCRITORIO, IPHONE, SIN_TOUR, sync_playwright

COMPARAR = os.environ.get('COMPARAR_ESTILOS', '')
GUARDAR = '' if COMPARAR else os.environ.get('GUARDAR_ESTILOS', '')

CON_SESION = ('dashboard', 'por_pagar', 'deudas', 'prestamos', 'suscripciones', 'metas',
              'estadisticas', 'plan_plata', 'perfil', 'categorias', 'importar_cartola')
SIN_SESION = ('login', 'registro', 'privacidad', 'terminos')
APARATOS = {'telefono': IPHONE, 'computador': ESCRITORIO}

AHORA = datetime(2026, 10, 15, 18, 0, tzinfo=UTC)
AHORA_NAVEGADOR = '2026-10-15T15:00:00-03:00'

QUIETO = '*, *::before, *::after { animation: none !important; transition: none !important; caret-color: transparent !important; }'

PROPIEDADES = [
    'display', 'position', 'top', 'right', 'bottom', 'left', 'z-index', 'box-sizing',
    'width', 'height', 'min-width', 'max-width', 'min-height', 'max-height',
    'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
    'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'flex-direction', 'flex-wrap', 'flex-grow', 'flex-shrink', 'flex-basis', 'order',
    'justify-content', 'align-items', 'align-self', 'row-gap', 'column-gap',
    'grid-template-columns', 'grid-template-rows', 'grid-row-start', 'grid-row-end',
    'grid-column-start', 'grid-column-end',
    'color', 'background-color', 'background-image', 'background-size', 'background-position',
    'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width',
    'border-top-style', 'border-right-style', 'border-bottom-style', 'border-left-style',
    'border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color',
    'border-top-left-radius', 'border-top-right-radius', 'border-bottom-right-radius',
    'border-bottom-left-radius', 'box-shadow', 'outline-style', 'opacity', 'visibility',
    'overflow-x', 'overflow-y', 'font-family', 'font-size', 'font-weight', 'font-style',
    'line-height', 'letter-spacing', 'text-align', 'text-transform', 'text-decoration-line',
    'white-space', 'text-overflow', 'transform', 'filter', 'backdrop-filter', 'mix-blend-mode',
    'content', 'cursor', 'pointer-events', 'object-fit',
]

RECOLECTAR = """
(propiedades) => {
  const salida = {};
  const ruta = (el) => {
    const partes = [];
    while (el && el !== document.documentElement) {
      const padre = el.parentElement;
      const clase = el.classList[0] || '';
      const iguales = [...padre.children].filter((h) => h.tagName === el.tagName && (h.classList[0] || '') === clase);
      partes.unshift(el.tagName.toLowerCase() + (clase ? '.' + clase : '') + ':' + (iguales.indexOf(el) + 1));
      el = padre;
    }
    return partes.join('>');
  };
  for (const el of document.querySelectorAll('body, body *')) {
    if (el.closest('script, style, template, noscript, svg *')) continue;
    for (const pseudo of ['', '::before', '::after']) {
      const calculado = getComputedStyle(el, pseudo || null);
      if (pseudo && (calculado.content === 'none' || calculado.content === 'normal')) continue;
      const valores = {};
      for (const p of propiedades) valores[p] = calculado.getPropertyValue(p);
      salida[ruta(el) + pseudo] = valores;
    }
  }
  return salida;
}
"""


@unittest.skipUnless((GUARDAR or COMPARAR) and sync_playwright,
                     'Comparar estilos: GUARDAR_ESTILOS=archivo.json o COMPARAR_ESTILOS=archivo.json, con playwright')
class EstilosCalculadosTests(StaticLiveServerTestCase):
    host = 'localhost'

    @classmethod
    def setUpClass(cls):
        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
        cls.reloj = mock.patch('django.utils.timezone.now', return_value=AHORA)
        cls.reloj.start()
        super().setUpClass()
        cls.pw = sync_playwright().start()
        cls.navegador = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.navegador.close()
        cls.pw.stop()
        super().tearDownClass()
        cls.reloj.stop()

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-de-prueba-1')
        perfil, _ = UserProfile.objects.get_or_create(usuario=self.ana)
        perfil.politica_version = legal.VERSION
        perfil.save()
        hoy = date(2026, 10, 15)
        inicio = hoy.replace(day=1)
        for i, (nombre, monto) in enumerate((('Supermercado', '38420'), ('Bencina', '25000'), ('Farmacia', '9990'))):
            Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal(monto),
                                       categoria='Comida', fecha=inicio.replace(day=3 + i), descripcion=nombre)
        Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal('1250000'),
                                   categoria='Sueldo', fecha=inicio, descripcion='Sueldo')
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('31400'),
                                   categoria='Otros', fecha=inicio.replace(day=22), descripcion='Luz', pagado=False)
        Deuda.objects.create(usuario=self.ana, acreedor='Notebook', monto_total=Decimal('659880'),
                             cuotas_totales=12, fecha_inicio=inicio)
        Suscripcion.objects.create(usuario=self.ana, nombre='Plan celular', monto=Decimal('12990'),
                                   dia_cobro=20, fecha_inicio=inicio)
        Persona.objects.create(usuario=self.ana, nombre='Javiera', lado='ME_DEBE')

    def _contexto(self, aparato, con_sesion):
        contexto = self.navegador.new_context(service_workers='block', locale='es-CL', bypass_csp=True,
                                              timezone_id='America/Santiago', **aparato)
        contexto.add_init_script(SIN_TOUR)
        contexto.clock.set_fixed_time(AHORA_NAVEGADOR)
        if con_sesion:
            cliente = Client()
            cliente.force_login(self.ana)
            contexto.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                                   'value': cliente.cookies[settings.SESSION_COOKIE_NAME].value,
                                   'url': self.live_server_url}])
        return contexto

    def _medir(self, pagina, nombre):
        pagina.goto(self.live_server_url + reverse(nombre), wait_until='networkidle')
        pagina.add_style_tag(content=QUIETO)
        pagina.wait_for_timeout(400)
        return pagina.evaluate(RECOLECTAR, PROPIEDADES)

    def _todo(self):
        medidas = {}
        for etiqueta, aparato in APARATOS.items():
            for con_sesion, nombres in ((True, CON_SESION), (False, SIN_SESION)):
                contexto = self._contexto(aparato, con_sesion)
                pagina = contexto.new_page()
                pagina.set_default_timeout(15000)
                for nombre in nombres:
                    clave = f'{etiqueta}/{nombre}' + ('' if con_sesion else '/sin-sesion')
                    medidas[clave] = self._medir(pagina, nombre)
                contexto.close()
        return medidas

    def test_estilos_calculados(self):
        medidas = self._todo()
        if GUARDAR:
            Path(GUARDAR).write_text(json.dumps(medidas, ensure_ascii=False), 'utf-8')
            return
        antes = json.loads(Path(COMPARAR).read_text('utf-8'))
        diferencias = []
        for pantalla in sorted(set(antes) | set(medidas)):
            viejo, nuevo = antes.get(pantalla, {}), medidas.get(pantalla, {})
            for ruta in sorted(set(viejo) | set(nuevo)):
                if ruta not in viejo or ruta not in nuevo:
                    diferencias.append(f'{pantalla} · {ruta} · {"aparece" if ruta in nuevo else "desaparece"}')
                    continue
                for propiedad, valor in viejo[ruta].items():
                    if nuevo[ruta].get(propiedad) != valor:
                        diferencias.append(f'{pantalla} · {ruta} · {propiedad}: {valor} → {nuevo[ruta].get(propiedad)}')
        informe = Path(COMPARAR).with_suffix('.diferencias.txt')
        informe.write_text('\n'.join(diferencias), 'utf-8')
        self.assertEqual(diferencias, [], f'{len(diferencias)} diferencias, detalle en {informe}')
