from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import PagoServicio, SugerenciaDescartada, Suscripcion, Transaccion
from ..servicios.detectar_suscripciones import clave_de, sugerencias

HOY = date(2026, 9, 20)


class DetectarTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def cobro(self, descripcion, monto, fecha, categoria='Otros'):
        return Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=monto, categoria=categoria,
                                          fecha=fecha, descripcion=descripcion, pagado=True, fecha_pago=fecha)

    def tres_meses(self, descripcion='SMARTFIT PAC 88123', monto=24990, meses=(7, 8, 9)):
        return [self.cobro(descripcion, monto, date(2026, m, 5)) for m in meses]

    def test_la_clave_ignora_numeros_y_ruido(self):
        self.assertEqual(clave_de('SMARTFIT PAC 88123'), clave_de('Smartfit pago 99812'))

    def test_detecta_un_cobro_mensual(self):
        self.tres_meses()
        s = sugerencias(self.ana, HOY)
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]['monto'], 24990)
        self.assertEqual(s[0]['meses'], 3)
        self.assertEqual(s[0]['dia'], 5)
        self.assertTrue(s[0]['cobrada_este_mes'])

    def test_necesita_tres_meses_seguidos(self):
        self.tres_meses(meses=(5, 7, 9))
        self.assertEqual(sugerencias(self.ana, HOY), [])

    def test_montos_muy_distintos_no_cuentan(self):
        self.cobro('Almacen Don Pepe', 10000, date(2026, 7, 5))
        self.cobro('Almacen Don Pepe', 30000, date(2026, 8, 5))
        self.cobro('Almacen Don Pepe', 18000, date(2026, 9, 5))
        self.assertEqual(sugerencias(self.ana, HOY), [])

    def test_varios_en_un_mes_no_es_suscripcion(self):
        self.tres_meses(descripcion='Uber trip')
        self.cobro('Uber trip', 24990, date(2026, 9, 12))
        self.assertEqual(sugerencias(self.ana, HOY), [])

    def test_si_ya_no_se_cobra_no_sugiere(self):
        self.tres_meses(meses=(4, 5, 6))
        self.assertEqual(sugerencias(self.ana, HOY), [])

    def test_ignora_las_ya_registradas(self):
        self.tres_meses()
        Suscripcion.objects.create(usuario=self.ana, nombre='Smartfit', monto=24990, fecha_inicio=HOY)
        self.assertEqual(sugerencias(self.ana, HOY), [])

    def test_ignora_las_descartadas(self):
        self.tres_meses()
        SugerenciaDescartada.objects.create(usuario=self.ana, clave=clave_de('SMARTFIT PAC 88123'))
        self.assertEqual(sugerencias(self.ana, HOY), [])


class VistasTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        hoy = date.today()
        for atras in (2, 1, 0):
            m, y = hoy.month - atras, hoy.year
            if m < 1:
                m, y = m + 12, y - 1
            f = date(y, m, 1)
            Transaccion.objects.create(
                usuario=self.ana, tipo='EGRESO', monto=24990, categoria='Otros', fecha=f,
                descripcion='SMARTFIT PAC 88123', pagado=True, fecha_pago=f)

    def test_la_pantalla_muestra_la_sugerencia(self):
        r = self.client.get(reverse('suscripciones'))
        self.assertContains(r, '¿Estas son suscripciones?')

    def test_agregar_crea_la_suscripcion_sin_duplicar_el_mes(self):
        self.client.post(reverse('agregar_sugerencia'), {'clave': clave_de('SMARTFIT PAC 88123')})
        sub = Suscripcion.objects.get(usuario=self.ana)
        self.assertEqual(int(sub.monto), 24990)
        self.assertEqual(sub.cobros.count(), 3)
        self.assertTrue(sub.pagada_este_mes)
        self.assertEqual(PagoServicio.objects.filter(suscripcion=sub).count(), 1)

    def test_descartar_la_oculta(self):
        self.client.post(reverse('descartar_sugerencia'), {'clave': clave_de('SMARTFIT PAC 88123')})
        r = self.client.get(reverse('suscripciones'))
        self.assertNotContains(r, '¿Estas son suscripciones?')
