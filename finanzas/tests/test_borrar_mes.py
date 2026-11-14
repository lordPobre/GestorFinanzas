from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from finanzas.models import Transaccion
from finanzas.servicios import borrar_mes


class BorrarGastosDelMesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-1')
        self.gasto = self._crear(self.ana, 'EGRESO', '1000', date(2026, 11, 5), descripcion='Jumbo')
        self.debo = self._crear(self.ana, 'EGRESO', '500', date(2026, 11, 8), pagado=False)
        self.ingreso = self._crear(self.ana, 'INGRESO', '9000', date(2026, 11, 1))
        self.cuota = self._crear(self.ana, 'EGRESO', '300', date(2026, 11, 3), es_cuota=True)
        self.sub = self._crear(self.ana, 'EGRESO', '4500', date(2026, 11, 2), origen=Transaccion.SUSCRIPCION)
        self.otro_mes = self._crear(self.ana, 'EGRESO', '700', date(2026, 10, 30))
        self.de_beto = self._crear(self.beto, 'EGRESO', '800', date(2026, 11, 5))

    def _crear(self, usuario, tipo, monto, fecha, **extra):
        return Transaccion.objects.create(usuario=usuario, tipo=tipo, monto=Decimal(monto), fecha=fecha,
                                          categoria='Comida', **extra)

    def _quedan(self):
        return set(Transaccion.objects.values_list('pk', flat=True))

    def test_borra_solo_los_gastos_del_mes(self):
        hecho = borrar_mes.borrar(self.ana, 2026, 11)
        self.assertEqual(hecho['n'], 2)
        self.assertEqual(hecho['total'], Decimal('1500'))
        self.assertEqual(self._quedan(), {self.ingreso.pk, self.cuota.pk, self.sub.pk, self.otro_mes.pk,
                                          self.de_beto.pk})

    def test_deshacer_los_devuelve_con_su_id(self):
        hecho = borrar_mes.borrar(self.ana, 2026, 11)
        self.assertEqual(borrar_mes.deshacer(self.ana, hecho['token']), 2)
        self.assertFalse(Transaccion.objects.get(pk=self.debo.pk).pagado)
        self.assertEqual(Transaccion.objects.get(pk=self.gasto.pk).descripcion, 'Jumbo')
        self.assertEqual(borrar_mes.deshacer(self.ana, hecho['token']), 0)

    def test_otra_persona_no_puede_deshacer(self):
        hecho = borrar_mes.borrar(self.ana, 2026, 11)
        self.assertEqual(borrar_mes.deshacer(self.beto, hecho['token']), 0)
        self.assertFalse(Transaccion.objects.filter(pk=self.gasto.pk).exists())

    def test_el_resumen_separa_lo_que_se_queda(self):
        r = borrar_mes.resumen(list(Transaccion.objects.filter(usuario=self.ana, fecha__month=11)))
        self.assertEqual(r['borrar']['n'], 2)
        self.assertEqual(r['ingresos']['n'], 1)
        self.assertEqual(r['cuotas']['n'], 1)
        self.assertEqual(r['suscripciones']['n'], 1)
        self.assertEqual(r['quedan'], 3)


class VistasBorrarMesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('1000'),
                                   fecha=date(2026, 11, 5), categoria='Comida')
        self.client.force_login(self.ana)

    def test_la_lista_del_mes_trae_el_boton_y_la_confirmacion(self):
        cuerpo = self.client.get(reverse('inicio_movimientos') + '?year=2026&month=11').content.decode('utf-8')
        self.assertIn('data-borrar-mes-abrir', cuerpo)
        self.assertIn('Eliminar 1 gasto<', cuerpo)
        self.assertIn('name="mes" value="2026-11"', cuerpo)

    def test_borrar_deja_el_aviso_con_deshacer_una_vez(self):
        respuesta = self.client.post(reverse('borrar_gastos_mes'), {'mes': '2026-11', 'next': reverse('dashboard')})
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Transaccion.objects.filter(usuario=self.ana).exists())
        cuerpo = self.client.get(reverse('dashboard')).content.decode('utf-8')
        self.assertIn('data-borrado-aviso', cuerpo)
        self.assertIn('Eliminaste 1 gasto de noviembre', cuerpo)
        self.assertNotIn('data-borrado-aviso', self.client.get(reverse('dashboard')).content.decode('utf-8'))

    def test_deshacer_desde_la_vista(self):
        self.client.post(reverse('borrar_gastos_mes'), {'mes': '2026-11', 'next': reverse('dashboard')})
        token = self.client.session['borrado_mes']['token']
        self.client.post(reverse('deshacer_borrar_mes'), {'token': token, 'next': reverse('dashboard')})
        self.assertEqual(Transaccion.objects.filter(usuario=self.ana).count(), 1)

    def test_un_mes_que_no_existe_no_borra_nada(self):
        self.client.post(reverse('borrar_gastos_mes'), {'mes': 'nada', 'next': reverse('dashboard')})
        self.assertEqual(Transaccion.objects.filter(usuario=self.ana).count(), 1)
