from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from finanzas.models import AbonoPrestamo, Persona, Prestamo, Transaccion
from finanzas.servicios.mes import resumen_mes
from finanzas.servicios.pendientes import pendientes_del_mes


class DiaDePagoTests(SimpleTestCase):

    def test_la_cuota_se_paga_el_dia_en_que_se_anoto(self):
        p = Prestamo(descripcion='Arriendo', monto=Decimal('300000'), tipo='CUOTAS',
                     cuotas_totales=3, fecha=date(2026, 1, 31))
        self.assertEqual(p.dia_de_pago(2026, 2), date(2026, 2, 28))
        self.assertEqual(p.dia_de_pago(2026, 3), date(2026, 3, 31))

    def test_un_pago_unico_va_a_fin_de_mes(self):
        p = Prestamo(descripcion='Asado', monto=Decimal('50000'), tipo='UNICO', fecha=date(2026, 4, 3))
        self.assertEqual(p.dia_de_pago(2026, 4), date(2026, 4, 30))


class Base(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        self.hoy = date.today()

    def prestamo(self, nombre='Carla', monto='300000', tipo='CUOTAS', cuotas=3, lado='LE_DEBO',
                 usuario=None, fecha=None, contacto=''):
        persona = Persona.objects.create(usuario=usuario or self.ana, nombre=nombre, lado=lado,
                                         contacto=contacto)
        return Prestamo.objects.create(persona=persona, descripcion='Préstamo', monto=Decimal(monto),
                                       tipo=tipo, cuotas_totales=cuotas, fecha=fecha or self.hoy)

    def abonar(self, prestamo, monto, fecha=None):
        return AbonoPrestamo.objects.create(prestamo=prestamo, monto=Decimal(monto),
                                            fecha=fecha or self.hoy)


class CompromisoDelMesTests(Base):

    def test_la_cuota_del_mes_y_lo_que_falta(self):
        p = self.prestamo()
        y, m = self.hoy.year, self.hoy.month
        self.assertEqual(p.monto_cuota, Decimal('100000'))
        self.assertEqual(p.falta_este_mes(y, m), Decimal('100000'))
        self.abonar(p, '40000')
        self.assertEqual(p.falta_este_mes(y, m), Decimal('60000'))
        self.abonar(p, '60000')
        self.assertEqual(p.falta_este_mes(y, m), 0)

    def test_pagar_de_mas_cuenta_como_pagado_ese_mes(self):
        p = self.prestamo()
        self.abonar(p, '150000')
        y, m = self.hoy.year, self.hoy.month
        self.assertEqual(p.compromiso_del_mes(y, m), Decimal('150000'))
        self.assertEqual(p.falta_este_mes(y, m), 0)

    def test_el_pago_unico_se_espera_entero_este_mes(self):
        p = self.prestamo(monto='50000', tipo='UNICO', cuotas=1)
        y, m = self.hoy.year, self.hoy.month
        self.assertEqual(p.falta_este_mes(y, m), Decimal('50000'))
        self.abonar(p, '20000')
        self.assertEqual(p.falta_este_mes(y, m), Decimal('30000'))
        self.assertEqual(p.compromiso_del_mes(y, m), Decimal('50000'))

    def test_lo_ya_devuelto_no_vuelve_a_pedirse(self):
        p = self.prestamo(fecha=self.hoy - relativedelta(months=2))
        self.abonar(p, '300000', fecha=self.hoy - relativedelta(months=1))
        self.assertTrue(p.esta_pagado)
        self.assertEqual(p.falta_este_mes(self.hoy.year, self.hoy.month), 0)

    def test_la_cuota_nunca_pasa_de_lo_pendiente(self):
        p = self.prestamo(monto='250000')
        self.abonar(p, '200000', fecha=self.hoy - relativedelta(months=1))
        self.assertEqual(p.falta_este_mes(self.hoy.year, self.hoy.month), Decimal('50000'))


class PorPagarTests(Base):

    def _debo(self, year=None, month=None):
        items = pendientes_del_mes(self.ana, year or self.hoy.year, month or self.hoy.month)
        return [i for i in items if i['tipo'] == 'debo']

    def test_la_cuota_aparece_en_por_pagar(self):
        p = self.prestamo()
        filas = self._debo()
        self.assertEqual(len(filas), 1)
        fila = filas[0]
        self.assertEqual((fila['nombre'], fila['monto'], fila['pagado']), ('Carla', Decimal('100000'), False))
        self.assertEqual(fila['detalle'], 'Le debes · cuota 1 de 3')
        self.assertEqual(fila['fecha'], p.dia_de_pago(self.hoy.year, self.hoy.month))
        self.assertEqual(fila['url_pagar'], reverse('pagar_mes_prestamo', args=[p.pk]))

    def test_el_pago_unico_dice_que_es_unico(self):
        self.prestamo(monto='50000', tipo='UNICO', cuotas=1)
        self.assertEqual(self._debo()[0]['detalle'], 'Le debes · pago único')

    def test_lo_que_me_deben_no_aparece(self):
        self.prestamo(lado='ME_DEBE')
        self.assertEqual(self._debo(), [])

    def test_solo_el_mes_en_curso(self):
        self.prestamo()
        siguiente = self.hoy + relativedelta(months=1)
        self.assertEqual(self._debo(siguiente.year, siguiente.month), [])

    def test_pagada_la_cuota_sale_de_la_lista(self):
        p = self.prestamo()
        self.abonar(p, '100000')
        self.assertEqual(self._debo(), [])

    def test_no_muestra_lo_de_otra_cuenta(self):
        self.prestamo(usuario=self.beto)
        self.assertEqual(self._debo(), [])


class PuedesGastarTests(Base):

    def setUp(self):
        super().setUp()
        Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal('1000000'),
                                   categoria='Sueldo', fecha=self.hoy, descripcion='Sueldo')

    def _resumen(self, fecha=None):
        fecha = fecha or self.hoy
        return resumen_mes(self.ana, fecha.year, fecha.month)

    def test_lo_que_debes_resta_de_puedes_gastar(self):
        self.prestamo()
        r = self._resumen()
        self.assertEqual(r['exacto']['total_debo_mes'], Decimal('100000'))
        self.assertEqual(r['debo_pendiente_mes'], 100000.0)
        self.assertEqual(r['exacto']['disponible'], Decimal('900000'))

    def test_pagar_la_cuota_no_la_cuenta_dos_veces(self):
        p = self.prestamo()
        self.abonar(p, '100000')
        r = self._resumen()
        self.assertEqual((r['debo_pagado_mes'], r['debo_pendiente_mes']), (100000.0, 0.0))
        self.assertEqual(r['exacto']['disponible'], Decimal('900000'))

    def test_un_abono_parcial_suma_lo_pagado_y_lo_que_falta(self):
        p = self.prestamo()
        self.abonar(p, '30000')
        r = self._resumen()
        self.assertEqual((r['debo_pagado_mes'], r['debo_pendiente_mes']), (30000.0, 70000.0))
        self.assertEqual(r['exacto']['disponible'], Decimal('900000'))

    def test_lo_que_me_deben_no_toca_la_cifra(self):
        self.prestamo(lado='ME_DEBE', monto='500000')
        r = self._resumen()
        self.assertEqual(r['exacto']['total_debo_mes'], 0)
        self.assertEqual(r['exacto']['disponible'], Decimal('1000000'))

    def test_un_mes_cerrado_cuenta_solo_lo_pagado_ese_mes(self):
        anterior = self.hoy - relativedelta(months=1)
        p = self.prestamo(fecha=self.hoy - relativedelta(months=2))
        self.abonar(p, '100000', fecha=anterior)
        r = self._resumen(anterior)
        self.assertEqual(r['exacto']['total_debo_mes'], Decimal('100000'))
        self.assertEqual(r['debo_pendiente_mes'], 0.0)


class PantallasDeboTests(Base):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.ana)

    def test_marcar_pagada_la_cuota_del_mes(self):
        p = self.prestamo()
        url = reverse('pagar_mes_prestamo', args=[p.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        abono = AbonoPrestamo.objects.get(prestamo=p)
        self.assertEqual((abono.monto, abono.nota, abono.fecha),
                         (Decimal('100000'), 'Pago del mes', date.today()))
        self.client.post(url)
        self.assertEqual(AbonoPrestamo.objects.filter(prestamo=p).count(), 1)

    def test_marcar_pagada_solo_por_post(self):
        p = self.prestamo()
        self.assertEqual(self.client.get(reverse('pagar_mes_prestamo', args=[p.pk])).status_code, 405)
        self.assertFalse(AbonoPrestamo.objects.exists())

    def test_lo_que_me_deben_no_se_marca_pagado_desde_ahi(self):
        p = self.prestamo(lado='ME_DEBE')
        self.assertEqual(self.client.post(reverse('pagar_mes_prestamo', args=[p.pk])).status_code, 404)
        self.assertFalse(AbonoPrestamo.objects.exists())

    def test_no_se_paga_lo_que_debe_otra_cuenta(self):
        p = self.prestamo(usuario=self.beto)
        self.assertEqual(self.client.post(reverse('pagar_mes_prestamo', args=[p.pk])).status_code, 404)
        self.assertFalse(AbonoPrestamo.objects.exists())

    def test_crear_una_persona_en_debo(self):
        self.client.post(reverse('crear_persona'), {
            'nombre': 'Carla', 'lado': 'LE_DEBO', 'monto': '300.000', 'tipo': 'CUOTAS',
            'cuotas_totales': '3', 'descripcion': 'Arriendo'})
        persona = Persona.objects.get(usuario=self.ana)
        prestamo = persona.prestamos.get()
        self.assertEqual(persona.lado, 'LE_DEBO')
        self.assertEqual((prestamo.monto, prestamo.cuotas_totales), (Decimal('300000'), 3))

    def test_sin_lado_valido_la_persona_va_a_me_deben(self):
        for lado in ('', 'cualquier cosa'):
            with self.subTest(lado=lado):
                self.client.post(reverse('crear_persona'), {'nombre': f'P{lado}', 'lado': lado})
        self.assertEqual(set(Persona.objects.values_list('lado', flat=True)), {'ME_DEBE'})

    def test_las_pestanas_separan_los_dos_lados(self):
        self.prestamo('Carla', '300000')
        self.prestamo('Diego', '50000', tipo='UNICO', cuotas=1, lado='ME_DEBE')
        me_deben = self.client.get(reverse('prestamos'))
        debo = self.client.get(reverse('prestamos') + '?lado=debo')
        self.assertEqual([p.nombre for p in me_deben.context['personas']], ['Diego'])
        self.assertEqual([p.nombre for p in debo.context['personas']], ['Carla'])
        self.assertFalse(me_deben.context['debo'])
        self.assertTrue(debo.context['debo'])
        for r in (me_deben, debo):
            self.assertEqual((r.context['total_me_deben'], r.context['total_debo']), (50000, 300000))

    def test_el_detalle_abre_en_la_pestana_de_la_persona(self):
        p = self.prestamo()
        r = self.client.get(reverse('detalle_persona', args=[p.persona.pk]))
        self.assertEqual(r.context['lado'], 'LE_DEBO')

    def test_whatsapp_solo_para_cobrar(self):
        debo = self.prestamo('Carla', contacto='+56 9 1234 5678').persona
        cobro = self.prestamo('Diego', lado='ME_DEBE', contacto='+56 9 1234 5678').persona
        self.assertEqual(debo.enlace_whatsapp, '')
        self.assertTrue(cobro.enlace_whatsapp.startswith('https://wa.me/56912345678?text='))

    def test_el_inicio_trae_el_boton_para_pagar(self):
        p = self.prestamo()
        r = self.client.get(reverse('dashboard'))
        self.assertContains(r, reverse('pagar_mes_prestamo', args=[p.pk]))
