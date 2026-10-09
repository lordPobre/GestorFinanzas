from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from ..models import Categoria
from ..views.comun import contadores


class CategoriasDelPanelTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        Categoria.objects.create(usuario=self.ana, nombre='Mascotas', tipo='EGRESO')
        Categoria.objects.create(usuario=self.ana, nombre='Arriendos', tipo='INGRESO')
        Categoria.objects.create(usuario=self.ana, nombre='Vieja', tipo='EGRESO', activa=False)

    def test_las_opciones_son_las_mismas_que_antes(self):
        datos = contadores(self.ana)
        self.assertEqual(datos['cats_egreso'], Categoria.opciones(self.ana, 'EGRESO'))
        self.assertEqual(datos['cats_ingreso'], Categoria.opciones(self.ana, 'INGRESO'))
        self.assertEqual(datos['cats_egreso_json'], [list(c) for c in Categoria.opciones(self.ana, 'EGRESO')])

    def test_las_categorias_se_leen_de_la_base_una_sola_vez(self):
        with CaptureQueriesContext(connection) as consultas:
            contadores(self.ana)
        de_categorias = [q for q in consultas.captured_queries
                         if 'finanzas_categoria' in q['sql'] and 'FROM "finanzas_categoria"' in q['sql']]
        self.assertEqual(len(de_categorias), 1)
