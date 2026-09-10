"""Lectura de cartolas bancarias en PDF.

Nada de esto sale a internet ni necesita un servicio pago: el PDF de una
cartola chilena trae capa de texto real, así que se lee con pypdf (Python
puro, sin dependencias) y se interpreta con expresiones regulares.

El PDF nunca toca el disco. Se lee del request en memoria, se descarta, y
lo que sigue viaje es la lista de movimientos ya interpretada.
"""
from .base import Cartola, MovimientoLeido, leer_cartola, BANCOS
from .analisis import enriquecer

# Importar cada parser es lo que lo registra en BANCOS: el decorador
# @registrar corre al importar el módulo, no al definir la clase en el aire.
# Sin estas líneas el registro queda vacío y no se reconoce ninguna cartola.
#
# El orden es el que se prueba al reconocer. El genérico queda fuera del
# recorrido (leer_cartola lo llama solo al final, si ninguno reconoció).
from . import banco_chile   # noqa: F401
from . import cmr           # noqa: F401
from . import generico      # noqa: F401

__all__ = ['Cartola', 'MovimientoLeido', 'leer_cartola', 'enriquecer', 'BANCOS']
