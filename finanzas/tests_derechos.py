"""Tests de los derechos del titular y de la salud del servicio.

Tres cosas que no pueden romperse sin que nadie se entere:

  · Un ingreso ya conocido del mes siguiente tiene que poder anotarse, y un
    gasto futuro no. La validación vivía al revés y el selector de fecha del
    panel quedaba inservible para su caso principal.
  · Eliminar la cuenta tiene que borrar TODO y no dejar nada colgando. Y no
    puede ocurrir sin reautenticación.
  · La descarga de datos tiene que traer lo del titular y nada de otro, y
    nunca las credenciales del segundo factor.
"""
from datetime import date, timedelta
from decimal import Decimal
import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import TransaccionForm
from .models import (CodigoRespaldo, Deuda, MetaAhorro, Persona, Prestamo,
                     SegundoFactor, Suscripcion, Transaccion, UserProfile)

class FechaDeUnMovimiento(TestCase):
    """Qué fechas acepta el formulario y cuáles no."""

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def _datos(self, tipo, fecha, categoria):
        return {'tipo': tipo, 'monto': '500000', 'categoria': categoria,
                'descripcion': 'prueba', 'fecha': fecha.isoformat()}

    def test_un_ingreso_del_proximo_mes_se_acepta(self):
        proximo = date.today() + timedelta(days=30)
        form = TransaccionForm(self._datos('INGRESO', proximo, 'Sueldo'), usuario=self.ana)
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_un_gasto_futuro_sigue_rechazado(self):
        manana = date.today() + timedelta(days=1)
        form = TransaccionForm(self._datos('EGRESO', manana, 'Comida'), usuario=self.ana)
        self.assertFalse(form.is_valid())
        self.assertIn('fecha', form.errors)

    def test_un_ingreso_a_mas_de_un_ano_se_rechaza(self):
        lejano = date.today() + timedelta(days=400)
        form = TransaccionForm(self._datos('INGRESO', lejano, 'Sueldo'), usuario=self.ana)
        self.assertFalse(form.is_valid())
        self.assertIn('fecha', form.errors)

    def test_una_fecha_pasada_se_acepta_en_los_dos_tipos(self):
        ayer = date.today() - timedelta(days=1)
        for tipo, cat in (('INGRESO', 'Sueldo'), ('EGRESO', 'Comida')):
            form = TransaccionForm(self._datos(tipo, ayer, cat), usuario=self.ana)
            self.assertTrue(form.is_valid(), f'{tipo}: {form.errors.as_json()}')

    def test_el_ingreso_futuro_no_ensucia_el_mes_en_curso(self):
        """El total del mes se calcula por rango, así que el de octubre no
        puede aparecer en el de septiembre."""
        from .servicios.mes import resumen_mes

        hoy = date.today()
        futuro = hoy + timedelta(days=45)
        Transaccion.objects.create(usuario=self.ana, tipo='INGRESO',
                                   monto=Decimal('900000'), categoria='Sueldo',
                                   fecha=futuro)
        resumen = resumen_mes(self.ana, hoy.year, hoy.month)
        self.assertEqual(resumen['ingresos'], 0)

class DescargaDeMisDatos(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO',
                                   monto=Decimal('12000'), categoria='Comida',
                                   descripcion='almuerzo de ana', fecha=date.today())
        Transaccion.objects.create(usuario=self.beto, tipo='EGRESO',
                                   monto=Decimal('9000'), categoria='Comida',
                                   descripcion='almuerzo de beto', fecha=date.today())
        SegundoFactor.objects.create(usuario=self.ana, secreto='SECRETOQUENODEBESALIR',
                                     activo=True)
        self.client.force_login(self.ana)

    def _descargar(self):
        respuesta = self.client.get(reverse('mis_datos'))
        self.assertEqual(respuesta.status_code, 200)
        return json.loads(respuesta.content.decode('utf-8'))

    def test_trae_lo_propio(self):
        datos = self._descargar()
        descripciones = [m['descripcion'] for m in datos['movimientos']]
        self.assertIn('almuerzo de ana', descripciones)

    def test_no_trae_lo_de_otro(self):
        cuerpo = self.client.get(reverse('mis_datos')).content.decode('utf-8')
        self.assertNotIn('almuerzo de beto', cuerpo)

    def test_no_entrega_el_secreto_del_segundo_factor(self):
        cuerpo = self.client.get(reverse('mis_datos')).content.decode('utf-8')
        self.assertNotIn('SECRETOQUENODEBESALIR', cuerpo)
        self.assertNotIn('password', cuerpo)

    def test_pide_sesion(self):
        self.client.logout()
        respuesta = self.client.get(reverse('mis_datos'))
        self.assertEqual(respuesta.status_code, 302)

class BorradoDeLaCuenta(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        for usuario in (self.ana, self.beto):
            UserProfile.objects.get_or_create(usuario=usuario)
            Transaccion.objects.create(usuario=usuario, tipo='EGRESO',
                                       monto=Decimal('5000'), categoria='Comida',
                                       fecha=date.today())
            deuda = Deuda.objects.create(usuario=usuario, acreedor='Tienda',
                                         monto_total=Decimal('120000'),
                                         cuotas_totales=12, fecha_inicio=date.today())
            deuda.pagos.create(periodo=date.today().year * 100 + date.today().month,
                               monto=Decimal('10000'))
            persona = Persona.objects.create(usuario=usuario, nombre='Alguien')
            Prestamo.objects.create(persona=persona, descripcion='prestado',
                                    monto=Decimal('30000'))
            MetaAhorro.objects.create(usuario=usuario, nombre='Viaje',
                                      monto_meta=Decimal('400000'))
            Suscripcion.objects.create(usuario=usuario, nombre='Servicio',
                                       monto=Decimal('7000'),
                                       fecha_inicio=date.today())
            SegundoFactor.objects.create(usuario=usuario, secreto='X' * 16)
            CodigoRespaldo.objects.create(usuario=usuario, codigo_hash='h')
        self.client.force_login(self.ana)
        self.url = reverse('eliminar_cuenta')

    def test_sin_la_contrasena_no_borra_nada(self):
        self.client.post(self.url, {'confirmacion': 'ELIMINAR', 'password': 'la-equivocada'})
        self.assertTrue(User.objects.filter(pk=self.ana.pk).exists())

    def test_sin_escribir_eliminar_no_borra_nada(self):
        self.client.post(self.url, {'confirmacion': 'si', 'password': 'clave-larga-1'})
        self.assertTrue(User.objects.filter(pk=self.ana.pk).exists())

    def test_borra_la_cuenta_y_todo_lo_que_cuelga(self):
        self.client.post(self.url, {'confirmacion': 'ELIMINAR', 'password': 'clave-larga-1'})

        self.assertFalse(User.objects.filter(pk=self.ana.pk).exists())
        self.assertEqual(Transaccion.objects.filter(usuario=self.ana).count(), 0)
        self.assertEqual(Deuda.objects.filter(usuario=self.ana).count(), 0)
        self.assertEqual(Persona.objects.filter(usuario=self.ana).count(), 0)
        self.assertEqual(MetaAhorro.objects.filter(usuario=self.ana).count(), 0)
        self.assertEqual(Suscripcion.objects.filter(usuario=self.ana).count(), 0)
        self.assertEqual(SegundoFactor.objects.filter(usuario=self.ana).count(), 0)
        self.assertEqual(CodigoRespaldo.objects.filter(usuario=self.ana).count(), 0)
        self.assertEqual(UserProfile.objects.filter(usuario=self.ana).count(), 0)

    def test_no_toca_la_cuenta_de_al_lado(self):
        self.client.post(self.url, {'confirmacion': 'ELIMINAR', 'password': 'clave-larga-1'})

        self.assertTrue(User.objects.filter(pk=self.beto.pk).exists())
        self.assertEqual(Transaccion.objects.filter(usuario=self.beto).count(), 1)
        self.assertEqual(Deuda.objects.filter(usuario=self.beto).count(), 1)
        self.assertEqual(Persona.objects.filter(usuario=self.beto).count(), 1)

    def test_pide_sesion(self):
        self.client.logout()
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)

class SaludDelServicio(TestCase):
    def test_responde_sin_sesion(self):
        respuesta = self.client.get(reverse('salud'))
        self.assertEqual(respuesta.status_code, 200)
        datos = json.loads(respuesta.content.decode('utf-8'))
        self.assertEqual(datos['estado'], 'ok')
        self.assertEqual(datos['partes']['base'], 'ok')
        self.assertEqual(datos['partes']['cache'], 'ok')

class BloqueoDelSegundoFactor(TestCase):
    """El código de seis dígitos también se limita: sin tope, un millón de
    combinaciones se prueban en minutos."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        SegundoFactor.objects.create(usuario=self.ana, secreto='A' * 16, activo=True)

    def test_tras_cinco_codigos_malos_queda_bloqueado(self):
        sesion = self.client.session
        sesion['2fa_pendiente'] = self.ana.pk
        sesion.save()

        for _ in range(5):
            self.client.post(reverse('verificar_codigo'), {'codigo': '000000'})

        respuesta = self.client.post(reverse('verificar_codigo'), {'codigo': '000000'})
        self.assertContains(respuesta, 'Demasiados intentos', status_code=200)
