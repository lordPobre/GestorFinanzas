import re
from datetime import UTC, date, datetime
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from .. import fechas
from ..models import Transaccion
from ..servicios.mes_elegido import mes_pedido

NOCHE_DEL_31_EN_CHILE = datetime(2026, 11, 1, 2, 30, tzinfo=UTC)


class HoyEsLaFechaDeChileTests(SimpleTestCase):

    def test_de_noche_sigue_siendo_el_mismo_dia(self):
        with mock.patch('django.utils.timezone.now', return_value=NOCHE_DEL_31_EN_CHILE):
            self.assertEqual(fechas.hoy(), date(2026, 10, 31))

    def test_nadie_usa_la_fecha_del_servidor(self):
        base = Path(settings.BASE_DIR) / 'finanzas'
        culpables = []
        for archivo in base.rglob('*.py'):
            partes = archivo.relative_to(base).parts
            if partes[0] in ('tests', 'migrations'):
                continue
            if re.search(r'\bdate\.today\(', archivo.read_text(encoding='utf-8')):
                culpables.append('/'.join(partes))
        self.assertEqual(culpables, [])


class LaNocheDelUltimoDiaTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def test_el_mes_elegido_por_defecto_es_el_de_chile(self):
        pedido = mock.Mock(GET={})
        with mock.patch('django.utils.timezone.now', return_value=NOCHE_DEL_31_EN_CHILE):
            self.assertEqual(mes_pedido(pedido)[:2], (2026, 10))

    def test_un_gasto_de_hoy_no_aparece_como_futuro(self):
        with mock.patch('django.utils.timezone.now', return_value=NOCHE_DEL_31_EN_CHILE):
            gasto = Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=1000,
                                               categoria='Comida', fecha=date(2026, 10, 31), pagado=False)
            self.assertEqual(gasto.texto_estado_pago, 'Sin pagar')


class IndicesDeMovimientosTests(SimpleTestCase):

    def test_transaccion_tiene_los_indices_del_mes(self):
        campos = [tuple(i.fields) for i in Transaccion._meta.indexes]
        self.assertIn(('usuario', 'fecha'), campos)
        self.assertIn(('usuario', 'tipo', 'fecha'), campos)
