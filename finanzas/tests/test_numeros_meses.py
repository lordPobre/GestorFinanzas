from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings

from ..models import AbonoPrestamo, Deuda, PagoCuota, Persona, Prestamo, Transaccion
from ..rendimiento import _memo
from ..servicios.mes import (CLAVES_NUMEROS, _numeros_pasados, _resumen_mes, invalidar, numeros_mes,
                              numeros_meses, resumen_mes)
from ..servicios.panel import primeros_pasos


class NumerosMesesTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        hoy = date.today().replace(day=1)
        self.meses = [((hoy - relativedelta(months=i)).year, (hoy - relativedelta(months=i)).month)
                      for i in range(5, 0, -1)]

    def _fecha(self, atras, dia=10):
        f = date.today().replace(day=1) - relativedelta(months=atras)
        return f.replace(day=dia)

    def _datos(self):
        for atras in (1, 2, 4):
            Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal('800000'),
                                       categoria='Sueldo', fecha=self._fecha(atras, 1))
            Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('45990'),
                                       categoria='Comida', fecha=self._fecha(atras), pagado=True)
            Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('12500'),
                                       categoria='Comida', fecha=self._fecha(atras, 28), pagado=False)
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('33333'),
                                   categoria='Comida', fecha=self._fecha(3), es_cuota=True)
        corta = Deuda.objects.create(usuario=self.ana, acreedor='Notebook', monto_total=Decimal('100000'),
                                     cuotas_totales=3, fecha_inicio=self._fecha(4, 15))
        larga = Deuda.objects.create(usuario=self.ana, acreedor='Celular', monto_total=Decimal('240000'),
                                     cuotas_totales=12, fecha_inicio=self._fecha(3, 5))
        for d, atras in ((corta, 4), (corta, 3), (larga, 3), (larga, 1)):
            f = self._fecha(atras)
            PagoCuota.objects.create(deuda=d, periodo=Deuda.periodo_de(f.year, f.month),
                                     monto=Decimal('30000'), fecha_pago=f)
        tia = Persona.objects.create(usuario=self.ana, nombre='Tía', lado='LE_DEBO')
        prestamo = Prestamo.objects.create(persona=tia, descripcion='Arriendo', monto=Decimal('300000'),
                                           tipo='CUOTAS', cuotas_totales=3, fecha=self._fecha(4))
        AbonoPrestamo.objects.create(prestamo=prestamo, monto=Decimal('100000'), fecha=self._fecha(2))
        amigo = Persona.objects.create(usuario=self.ana, nombre='Pedro', lado='ME_DEBE')
        otro = Prestamo.objects.create(persona=amigo, descripcion='Pasajes', monto=Decimal('90000'))
        AbonoPrestamo.objects.create(prestamo=otro, monto=Decimal('20000'), fecha=self._fecha(2))

    def _esperado(self, mes):
        r = _resumen_mes(self.ana, *mes)
        return {k: r[k] for k in CLAVES_NUMEROS}

    def test_da_lo_mismo_que_el_resumen_completo(self):
        self._datos()
        juntos = _numeros_pasados(self.ana, self.meses)
        for mes in self.meses:
            self.assertEqual(juntos[mes], self._esperado(mes), mes)
            self.assertEqual(_numeros_pasados(self.ana, [mes])[mes], self._esperado(mes), mes)

    def test_sin_datos_da_ceros(self):
        juntos = _numeros_pasados(self.ana, self.meses)
        for mes in self.meses:
            self.assertEqual(juntos[mes], self._esperado(mes))

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                                           'LOCATION': 'pruebas-numeros-meses'}})
    def test_cinco_meses_en_pocas_consultas_y_luego_desde_cache(self):
        self._datos()
        with self.assertNumQueries(5):
            primera = numeros_meses(self.ana, self.meses)
        with self.assertNumQueries(0):
            segunda = numeros_meses(self.ana, self.meses)
        self.assertEqual(primera, segunda)

    def test_otro_mes_dentro_de_la_serie_no_usa_lo_guardado(self):
        self._datos()
        juntos = numeros_meses(self.ana, self.meses)
        cache.clear()
        for mes in self.meses:
            self.assertEqual(numeros_meses(self.ana, [mes])[mes], juntos[mes], mes)

    def test_en_la_misma_peticion_reusa_el_mes_ya_calculado(self):
        self._datos()
        hoy = date.today()
        token = _memo.set({})
        try:
            r = resumen_mes(self.ana, hoy.year, hoy.month)
            with self.assertNumQueries(0):
                datos = numeros_mes(self.ana, hoy.year, hoy.month)
        finally:
            _memo.reset(token)
        self.assertEqual(datos, {k: r[k] for k in CLAVES_NUMEROS})

    def test_invalidar_cambia_la_version_aunque_ya_se_haya_leido(self):
        token = _memo.set({})
        try:
            antes = numeros_meses(self.ana, self.meses)
            Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal('50000'),
                                       categoria='Sueldo', fecha=self._fecha(1, 3))
            invalidar(self.ana.pk)
            despues = numeros_meses(self.ana, self.meses)
        finally:
            _memo.reset(token)
        self.assertEqual(despues[self.meses[-1]]['ingresos'], antes[self.meses[-1]]['ingresos'] + 50000)

    def test_primeros_pasos_en_una_consulta(self):
        self._datos()
        with self.assertNumQueries(1):
            pasos, hechos = primeros_pasos(self.ana)
        self.assertEqual([p['hecho'] for p in pasos], [True, True, True, False, False, False])
        self.assertEqual(hechos, 3)
