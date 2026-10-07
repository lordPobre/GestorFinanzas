from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from finanzas.models import Categoria, TopeCategoria, Transaccion, UserProfile
from finanzas.servicios.recordatorios import avisos_del_dia, avisos_topes
from finanzas.servicios.topes import estado_tope, porcentaje, promedio_tres_meses, tono, topes_para_anotar
from finanzas.templatetags.moneda import money

COMIDA = 'Comida y Supermercado'


def gasto(usuario, monto, categoria='Comida', fecha=None, tipo='EGRESO'):
    return Transaccion.objects.create(usuario=usuario, tipo=tipo, monto=Decimal(monto),
                                      categoria=categoria, fecha=fecha or date.today(),
                                      descripcion='prueba')


class EstadoDelTopeTests(SimpleTestCase):

    def _tope(self, monto='100000'):
        return SimpleNamespace(monto=Decimal(monto), avisar=True)

    def test_los_tonos_cambian_en_80_y_en_100(self):
        for pct, esperado in ((0, 'verde'), (79, 'verde'), (80, 'amarillo'),
                              (99, 'amarillo'), (100, 'rojo'), (150, 'rojo')):
            with self.subTest(pct=pct):
                self.assertEqual(tono(pct), esperado)

    def test_bajo_el_tope_dice_lo_que_queda(self):
        self.assertEqual(estado_tope(self._tope(), Decimal('50000')), {
            'tope': 100000, 'gastado': 50000, 'pct': 50, 'ancho': 50, 'tono': 'verde',
            'queda': 50000, 'exceso': 0, 'avisar': True,
        })

    def test_pasado_el_tope_dice_cuanto_se_paso(self):
        estado = estado_tope(self._tope(), Decimal('120000'))
        self.assertEqual((estado['pct'], estado['ancho'], estado['tono']), (120, 100, 'rojo'))
        self.assertEqual((estado['queda'], estado['exceso']), (0, 20000))

    def test_sin_gasto_queda_todo(self):
        estado = estado_tope(self._tope(), None)
        self.assertEqual((estado['pct'], estado['tono'], estado['queda']), (0, 'verde', 100000))

    def test_un_tope_en_cero_no_divide(self):
        self.assertEqual(porcentaje(Decimal('5000'), Decimal('0')), 0)


class GuardarTopeTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        self.client.force_login(self.ana)
        self.url = reverse('guardar_tope')

    def test_poner_y_cambiar_un_tope(self):
        r = self.client.post(self.url, {'categoria': 'Comida', 'monto': '150.000', 'avisar': '1'})
        self.assertRedirects(r, reverse('categorias'), fetch_redirect_response=False)
        tope = TopeCategoria.objects.get(usuario=self.ana)
        self.assertEqual((tope.categoria, tope.monto, tope.avisar), ('Comida', Decimal('150000'), True))
        self.client.post(self.url, {'categoria': 'Comida', 'monto': '120.000'})
        tope = TopeCategoria.objects.get(usuario=self.ana)
        self.assertEqual((tope.monto, tope.avisar), (Decimal('120000'), False))

    def test_quitar_el_tope(self):
        TopeCategoria.objects.create(usuario=self.ana, categoria='Comida', monto=Decimal('100000'))
        self.client.post(self.url, {'categoria': 'Comida', 'quitar': '1'})
        self.assertFalse(TopeCategoria.objects.filter(usuario=self.ana).exists())

    def test_rechaza_ingresos_categorias_ajenas_y_montos_en_cero(self):
        ajena = Categoria.objects.create(usuario=self.beto, nombre='Mascotas')
        for datos in ({'categoria': 'Sueldo', 'monto': '1000'},
                      {'categoria': ajena.slug, 'monto': '1000'},
                      {'categoria': 'inventada', 'monto': '1000'},
                      {'categoria': 'Comida', 'monto': '0'},
                      {'categoria': 'Comida', 'monto': 'mucho'}):
            with self.subTest(datos=datos):
                self.client.post(self.url, datos)
        self.assertFalse(TopeCategoria.objects.exists())

    def test_una_categoria_propia_de_gasto_admite_tope(self):
        propia = Categoria.objects.create(usuario=self.ana, nombre='Mascotas')
        self.client.post(self.url, {'categoria': propia.slug, 'monto': '40.000'})
        self.assertTrue(TopeCategoria.objects.filter(usuario=self.ana, categoria=propia.slug).exists())

    def test_quitar_no_toca_el_tope_de_otra_cuenta(self):
        TopeCategoria.objects.create(usuario=self.beto, categoria='Comida', monto=Decimal('100000'))
        self.client.post(self.url, {'categoria': 'Comida', 'quitar': '1'})
        self.assertTrue(TopeCategoria.objects.filter(usuario=self.beto).exists())

    def test_solo_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_borrar_una_categoria_propia_borra_su_tope(self):
        propia = Categoria.objects.create(usuario=self.ana, nombre='Mascotas')
        TopeCategoria.objects.create(usuario=self.ana, categoria=propia.slug, monto=Decimal('40000'))
        self.client.post(reverse('eliminar_categoria', args=[propia.pk]))
        self.assertFalse(TopeCategoria.objects.filter(usuario=self.ana).exists())

    def test_la_pantalla_muestra_el_estado_del_tope(self):
        TopeCategoria.objects.create(usuario=self.ana, categoria='Comida', monto=Decimal('100000'))
        gasto(self.ana, '85000')
        r = self.client.get(reverse('categorias'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['con_topes'], 1)
        fila = next(c for c in r.context['de_gasto'] if c['slug'] == 'Comida')
        self.assertEqual((fila['tope']['pct'], fila['tope']['tono'], fila['tope']['queda']),
                         (85, 'amarillo', 15000))


class SugerenciaTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.hoy = date.today()
        self.inicio = date(self.hoy.year, self.hoy.month, 1)

    def test_el_promedio_es_de_los_tres_meses_anteriores(self):
        for meses, monto in ((1, '30000'), (2, '60000'), (3, '90000'), (4, '500000')):
            gasto(self.ana, monto, fecha=self.inicio - relativedelta(months=meses))
        gasto(self.ana, '999999', fecha=self.hoy)
        gasto(self.ana, '700000', categoria='Sueldo', tipo='INGRESO',
              fecha=self.inicio - relativedelta(months=1))
        promedios = promedio_tres_meses(self.ana, self.hoy)
        self.assertEqual(promedios['Comida'], 60000)
        self.assertNotIn('Sueldo', promedios)

    def test_el_panel_de_anotar_recibe_solo_los_topes_con_aviso(self):
        TopeCategoria.objects.create(usuario=self.ana, categoria='Comida', monto=Decimal('100000'))
        TopeCategoria.objects.create(usuario=self.ana, categoria='Transporte',
                                     monto=Decimal('50000'), avisar=False)
        gasto(self.ana, '30000')
        self.assertEqual(topes_para_anotar(self.ana, self.hoy),
                         {'Comida': [COMIDA, 100000.0, 30000.0]})

    def test_sin_topes_el_panel_no_recibe_nada(self):
        self.assertEqual(topes_para_anotar(self.ana, self.hoy), {})


class AvisosDeTopesTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.hoy = date.today()
        self.tope = TopeCategoria.objects.create(usuario=self.ana, categoria='Comida',
                                                 monto=Decimal('100000'))

    def _avisos(self, montos=False):
        return avisos_topes(self.ana, self.hoy, montos, '$')

    def test_bajo_el_80_no_avisa(self):
        gasto(self.ana, '50000')
        self.assertEqual(self._avisos(), [])

    def test_avisa_una_vez_al_80_y_una_vez_al_pasarse(self):
        gasto(self.ana, '85000')
        primero = self._avisos()
        self.assertEqual([a['titulo'] for a in primero], [f'Vas en 85 % de {COMIDA}'])
        self.assertEqual(primero[0]['cuerpo'], 'Toca para ver tus categorías.')
        self.assertEqual(primero[0]['url'], '/categorias/')
        self.assertEqual(self._avisos(), [])
        gasto(self.ana, '20000')
        self.assertEqual([a['titulo'] for a in self._avisos()], [f'Pasaste tu tope de {COMIDA}'])
        self.assertEqual(self._avisos(), [])

    def test_con_montos_dice_lo_que_queda_o_lo_que_se_paso(self):
        gasto(self.ana, '85000')
        self.assertEqual(self._avisos(montos=True)[0]['cuerpo'],
                         f'Te quedan {money(15000.0, "$")} este mes.')
        gasto(self.ana, '20000')
        self.assertEqual(self._avisos(montos=True)[0]['cuerpo'],
                         f'Vas {money(5000.0, "$")} por encima.')

    def test_el_mes_nuevo_vuelve_a_avisar(self):
        gasto(self.ana, '85000')
        self._avisos()
        TopeCategoria.objects.filter(pk=self.tope.pk).update(aviso_periodo=190001)
        self.assertEqual(len(self._avisos()), 1)

    def test_los_avisos_del_dia_respetan_la_opcion(self):
        gasto(self.ana, '85000')
        perfil, _ = UserProfile.objects.get_or_create(usuario=self.ana)
        perfil.push_vence = perfil.push_dia_antes = False
        self.assertEqual(avisos_del_dia(self.ana, perfil, self.hoy), [])
        perfil.push_topes = True
        self.assertEqual([a['etiqueta'] for a in avisos_del_dia(self.ana, perfil, self.hoy)],
                         ['tope-Comida'])
