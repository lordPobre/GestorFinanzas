from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .. import legal
from ..cartolas.base import Cartola, MovimientoLeido
from ..ia_repetidos import _prompt, revisar_pares
from ..models import Deuda, PagoCuota, Transaccion, UserProfile
from ..servicios.repetidos import buscar_repetidos, clasificar, marcar_repetidas, parecido
from ..views.cartola import SESION


def _d(fecha, desc, categoria='Comida', monto='23450'):
    return {'fecha': fecha, 'descripcion': desc, 'categoria': categoria,
            'monto': Decimal(monto), 'tipo': 'EGRESO'}


class ReglasTests(SimpleTestCase):

    def test_la_misma_descripcion_con_otro_formato_es_segura(self):
        self.assertEqual(parecido('LIDER EXPRESS MAIPU', 'Lider Express Maipú'), 1.0)
        self.assertEqual(clasificar(_d(date(2026, 9, 14), 'REDCOMPRA LIDER EXPRESS 4521'),
                                    _d(date(2026, 9, 15), 'Lider express')), 'seguro')

    def test_una_descripcion_distinta_con_la_misma_categoria_es_dudosa(self):
        self.assertEqual(clasificar(_d(date(2026, 9, 14), 'Super'),
                                    _d(date(2026, 9, 15), 'LIDER EXPRESS')), 'dudoso')

    def test_lejos_en_el_tiempo_o_con_otra_cuota_no_es_repetida(self):
        self.assertIsNone(clasificar(_d(date(2026, 9, 1), 'LIDER'), _d(date(2026, 9, 9), 'LIDER')))
        self.assertIsNone(clasificar(_d(date(2026, 9, 19), 'FALABELLA TV · cuota 2 de 3'),
                                     _d(date(2026, 9, 19), 'FALABELLA TV · cuota 3 de 3')))

    def test_comercios_distintos_sin_pista_no_son_repetidos(self):
        self.assertIsNone(clasificar(_d(date(2026, 9, 14), 'COPEC', 'Transporte'),
                                     _d(date(2026, 9, 14), 'NETFLIX', 'Ocio')))

    def test_el_mensaje_a_la_ia_lleva_solo_el_par(self):
        texto = _prompt([('0', _d(date(2026, 9, 14), 'Super'), _d(date(2026, 9, 15), 'LIDER'))])
        self.assertIn('P1: A) 14/09/2026 · gasto · $23.450 · Comida · «Super»', texto)
        self.assertEqual([l for l in texto.splitlines() if l.startswith('P')], [
            'P1: A) 14/09/2026 · gasto · $23.450 · Comida · «Super» | '
            'B) 15/09/2026 · gasto · $23.450 · Comida · «LIDER»'])
        self.assertNotIn('@', texto)


class _ConUsuario(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil, _ = UserProfile.objects.get_or_create(usuario=self.ana)
        self.perfil.analisis_ia = True
        self.perfil.politica_version = legal.VERSION
        self.perfil.save()

    def gasto(self, fecha, desc, monto='23450', categoria='Comida'):
        return Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal(monto),
                                          categoria=categoria, fecha=fecha, descripcion=desc)

    def cartola(self, *movs):
        return Cartola(banco='Banco de Chile', movimientos=[
            MovimientoLeido(fecha=f, descripcion=d, monto=Decimal(m), tipo='EGRESO', saldo=0,
                            categoria=c) for f, d, m, c in movs])


class CartolaRepetidaTests(_ConUsuario):

    def test_una_fila_segura_reemplaza_la_anterior(self):
        previa = self.gasto(date(2026, 9, 14), 'Lider express')
        cartola = self.cartola((date(2026, 9, 15), 'REDCOMPRA LIDER EXPRESS 4521', '23450', 'Comida'))
        with patch('finanzas.ia_repetidos.revisar_pares') as ia:
            marcar_repetidas(cartola, self.ana)
        ia.assert_not_called()
        fila = cartola.movimientos[0]
        self.assertEqual(fila.reemplaza_id, previa.pk)
        self.assertTrue(fila.reemplaza_seguro)
        self.assertIn('se reemplaza', fila.aviso)

    def test_una_dudosa_la_decide_la_ia(self):
        previa = self.gasto(date(2026, 9, 14), 'Super')
        cartola = self.cartola((date(2026, 9, 15), 'LIDER EXPRESS', '23450', 'Comida'))
        with patch('finanzas.ia_repetidos.revisar_pares', return_value={'0': True}) as ia:
            marcar_repetidas(cartola, self.ana)
        ia.assert_called_once()
        fila = cartola.movimientos[0]
        self.assertEqual((fila.reemplaza_id, fila.reemplaza_seguro), (previa.pk, True))
        self.assertIn('La IA', fila.aviso)

    def test_si_la_ia_dice_que_no_se_importa_como_nueva(self):
        self.gasto(date(2026, 9, 14), 'Super')
        cartola = self.cartola((date(2026, 9, 15), 'LIDER EXPRESS', '23450', 'Comida'))
        with patch('finanzas.ia_repetidos.revisar_pares', return_value={'0': False}):
            marcar_repetidas(cartola, self.ana)
        self.assertIsNone(cartola.movimientos[0].reemplaza_id)

    def test_sin_aceptar_la_politica_nueva_no_se_consulta_a_la_ia(self):
        self.perfil.politica_version = '1.7'
        self.perfil.save()
        previa = self.gasto(date(2026, 9, 14), 'Super')
        cartola = self.cartola((date(2026, 9, 15), 'LIDER EXPRESS', '23450', 'Comida'))
        with patch('finanzas.ia_repetidos.revisar_pares') as ia:
            marcar_repetidas(cartola, self.ana)
        ia.assert_not_called()
        fila = cartola.movimientos[0]
        self.assertEqual((fila.reemplaza_id, fila.reemplaza_seguro), (previa.pk, False))

    def test_dos_filas_iguales_no_reclaman_la_misma_anterior(self):
        self.gasto(date(2026, 9, 14), 'Lider express')
        cartola = self.cartola((date(2026, 9, 14), 'LIDER EXPRESS', '23450', 'Comida'),
                               (date(2026, 9, 14), 'LIDER EXPRESS', '23450', 'Comida'))
        marcar_repetidas(cartola, self.ana)
        self.assertEqual(sum(1 for m in cartola.movimientos if m.reemplaza_id), 1)

    def test_confirmar_reemplaza_en_vez_de_duplicar(self):
        previa = self.gasto(date(2026, 9, 14), 'Super')
        self.client.force_login(self.ana)
        sesion = self.client.session
        sesion[SESION] = {
            'banco': 'Banco de Chile', 'periodo': '', 'cuenta': '', 'cuadra': True,
            'descuadre': '0', 'nota_cuadre': '', 'saldo_inicial': '', 'saldo_final': '',
            'movimientos': [{
                'fecha': '2026-09-15', 'descripcion': 'LIDER EXPRESS', 'monto': '23450',
                'tipo': 'EGRESO', 'categoria': 'Comida', 'cuota_actual': 0, 'cuota_total': 0,
                'es_suscripcion': False, 'ya_existe': False, 'aviso': '',
                'reemplaza_id': previa.pk, 'reemplaza_seguro': True,
            }],
        }
        sesion.save()
        self.client.post(reverse('confirmar_cartola'), {'sel_0': '1', 'reemplazar_0': '1'})
        self.assertEqual(Transaccion.objects.filter(usuario=self.ana).count(), 1)
        previa.refresh_from_db()
        self.assertEqual((previa.fecha, previa.descripcion, previa.categoria),
                         (date(2026, 9, 15), 'LIDER EXPRESS', 'Comida'))


class PantallaRepetidosTests(_ConUsuario):

    def test_encuentra_el_par_y_borra_la_copia(self):
        primera = self.gasto(date(2026, 9, 14), 'LIDER EXPRESS')
        copia = self.gasto(date(2026, 9, 14), 'Lider Express')
        self.client.force_login(self.ana)
        r = self.client.get(reverse('movimientos_repetidos'))
        self.assertEqual(r.status_code, 200)
        par = r.context['pares'][0]
        self.assertEqual((par['queda'], par['borra'], par['marcado']), (primera, copia, True))
        self.client.post(reverse('movimientos_repetidos'), {'borrar': [str(copia.pk)]})
        self.assertEqual(list(Transaccion.objects.filter(usuario=self.ana)), [primera])

    def test_queda_la_que_esta_unida_a_una_cuota(self):
        suelta = self.gasto(date(2026, 9, 19), 'FALABELLA TV · cuota 2 de 3', '99990', 'Compras')
        pagada = self.gasto(date(2026, 9, 19), 'FALABELLA TV · cuota 2 de 3', '99990', 'Compras')
        deuda = Deuda.objects.create(usuario=self.ana, acreedor='Falabella TV',
                                     monto_total=Decimal('299970'), cuotas_totales=3,
                                     fecha_inicio=date(2026, 8, 19))
        PagoCuota.objects.create(deuda=deuda, periodo=202609, monto=Decimal('99990'),
                                 fecha_pago=date(2026, 9, 19), transaccion=pagada)
        par = buscar_repetidos(self.ana)[0]
        self.assertEqual((par['queda'], par['borra']), (pagada, suelta))
        self.client.force_login(self.ana)
        self.client.post(reverse('movimientos_repetidos'), {'borrar': [str(pagada.pk)]})
        self.assertTrue(Transaccion.objects.filter(pk=pagada.pk).exists())

    def test_no_borra_movimientos_de_otra_persona(self):
        bruno = User.objects.create_user('bruno', 'bruno@ejemplo.cl', 'clave-larga-2')
        ajeno = Transaccion.objects.create(usuario=bruno, tipo='EGRESO', monto=Decimal('1000'),
                                           fecha=date(2026, 9, 1))
        self.client.force_login(self.ana)
        self.client.post(reverse('movimientos_repetidos'), {'borrar': [str(ajeno.pk)]})
        self.assertTrue(Transaccion.objects.filter(pk=ajeno.pk).exists())


class IaRepetidosTests(SimpleTestCase):

    def setUp(self):
        cache.clear()

    def test_sin_clave_no_responde_nada(self):
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}):
            self.assertEqual(revisar_pares([('0', _d(date(2026, 9, 14), 'Super'),
                                             _d(date(2026, 9, 15), 'LIDER'))]), {})
