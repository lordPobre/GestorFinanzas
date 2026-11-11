from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas import diseno
from finanzas.models import AbonoPrestamo, Persona, Prestamo
from finanzas.templatetags.f2c import pr_abonos, pr_pasos, prestamos_mes
from finanzas.tests.test_csp_estilos import ATRIBUTO_STYLE


class Prestamos2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        self.claude = Persona.objects.create(usuario=self.ana, nombre='Claude', contacto='+56 9 1234 5678')
        self.viaje = Prestamo.objects.create(persona=self.claude, descripcion='Pasajes', monto=Decimal('200000'),
                                             tipo='CUOTAS', cuotas_totales=3)
        AbonoPrestamo.objects.create(prestamo=self.viaje, monto=Decimal('66667'), nota='Transferencia')
        self.camila = Persona.objects.create(usuario=self.ana, nombre='Camila')
        Prestamo.objects.create(persona=self.camila, descripcion='Entradas', monto=Decimal('20000'))

    def _cuerpo(self, url):
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, 'finanzas/prestamos_2c.html')
        return respuesta.content.decode('utf-8')

    def test_la_cabecera_trae_el_reparto_y_lo_del_mes(self):
        cuerpo = self._cuerpo(reverse('prestamos'))
        self.assertIn('class="pr2c-hero pr2c-top-lista"', cuerpo)
        self.assertIn('Quién te debe', cuerpo)
        self.assertIn('class="pr2c-reparto"', cuerpo)
        self.assertIn('Este mes te toca cobrar', cuerpo)
        self.assertIn('css/prestamos-2c.css', cuerpo)
        self.assertEqual(cuerpo.count('class="pr2c-fila"') + cuerpo.count('class="pr2c-fila on"'), 2)
        self.assertIsNone(ATRIBUTO_STYLE.search(cuerpo))

    def test_la_persona_trae_cuotas_abonos_y_acciones(self):
        cuerpo = self._cuerpo(reverse('detalle_persona', args=[self.claude.pk]))
        self.assertIn('Registrar abono', cuerpo)
        self.assertIn(f'data-open="#abono{self.viaje.pk}"', cuerpo)
        self.assertIn('Cobrar por WhatsApp', cuerpo)
        self.assertIn('https://wa.me/56912345678?text=', cuerpo)
        self.assertIn('Cuota 1', cuerpo)
        self.assertIn('Te la pagó', cuerpo)
        self.assertIn('class="pr2c-paso viene"', cuerpo)
        self.assertIn('Lo que te ha devuelto', cuerpo)
        self.assertIn('Transferencia', cuerpo)
        self.assertIn('data-ancho-pct="', cuerpo)
        self.assertIn('class="pr2c-fila on"', cuerpo)
        self.assertIsNone(ATRIBUTO_STYLE.search(cuerpo))

    def test_el_lado_debo(self):
        pedro = Persona.objects.create(usuario=self.ana, nombre='Pedro', lado='LE_DEBO')
        Prestamo.objects.create(persona=pedro, descripcion='Arriendo', monto=Decimal('90000'))
        cuerpo = self._cuerpo(reverse('detalle_persona', args=[pedro.pk]))
        self.assertIn('Debes', cuerpo)
        self.assertIn('Registrar un pago', cuerpo)
        self.assertIn('Este mes pagas', cuerpo)
        self.assertNotIn('Cobrar por WhatsApp', cuerpo)

    def test_sin_personas_se_ve_el_vacio(self):
        Persona.objects.all().delete()
        cuerpo = self._cuerpo(reverse('prestamos'))
        self.assertIn('Nadie te debe', cuerpo)
        self.assertNotIn('class="pr2c-reparto"', cuerpo)


class PasosDePrestamoTests(TestCase):
    def setUp(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.persona = Persona.objects.create(usuario=ana, nombre='Beto')

    def test_muestra_seis_cuotas_y_cuenta_el_resto(self):
        largo = Prestamo.objects.create(persona=self.persona, descripcion='Notebook', monto=Decimal('120000'),
                                        tipo='CUOTAS', cuotas_totales=12)
        pp = pr_pasos(largo)
        self.assertEqual(len(pp['pasos']), 6)
        self.assertEqual(pp['mas'], 6)
        self.assertEqual(pp['pasos'][0]['estado'], 'mes')
        self.assertEqual(pp['pasos'][1]['estado'], 'viene')

    def test_un_pago_unico_tiene_devuelto_y_falta(self):
        unico = Prestamo.objects.create(persona=self.persona, descripcion='Almuerzo', monto=Decimal('15000'))
        AbonoPrestamo.objects.create(prestamo=unico, monto=Decimal('5000'))
        pp = pr_pasos(unico)
        self.assertEqual([p['estado'] for p in pp['pasos']], ['pagada', 'mes'])
        self.assertEqual(pp['pasos'][1]['monto'], Decimal('10000'))

    def test_lo_del_mes_y_los_abonos(self):
        unico = Prestamo.objects.create(persona=self.persona, descripcion='Almuerzo', monto=Decimal('15000'))
        AbonoPrestamo.objects.create(prestamo=unico, monto=Decimal('5000'), nota='Efectivo')
        mes = prestamos_mes([self.persona])
        self.assertEqual(mes['total'], Decimal('10000'))
        self.assertEqual(mes['quienes'][0]['nombre'], 'Beto')
        abonos = pr_abonos(self.persona)
        self.assertEqual(abonos[0]['nota'], 'Efectivo')
        self.assertEqual(abonos[0]['prestamo'], 'Almuerzo')
