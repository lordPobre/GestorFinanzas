"""Lectura de cartolas bancarias y estados de cuenta en PDF.

Nada de esto sale a internet ni necesita un servicio pago: el PDF de una
cartola chilena trae capa de texto real, así que se lee con pypdf (Python
puro, sin dependencias) y se interpreta con expresiones regulares.

El PDF nunca toca el disco. Se lee del request en memoria, se descarta, y
lo que sigue viaje es la lista de movimientos ya interpretada.

DOS MOTORES, NO VEINTE PARSERS
------------------------------
Los formatos son muchos pero los mecanismos son dos:

  · universal.py — cartolas de cuenta (corriente, vista, ahorro). Llevan
    saldo corrido, y la resta entre saldos consecutivos da el monto y el
    signo de cada movimiento. Sirve para cualquier banco.

  · retail.py — estados de cuenta de tarjeta (casas comerciales). No tienen
    saldo: tienen cuotas, y todo es cargo. Se lee el valor de la cuota del
    mes y se comprueba la suma contra el total facturado.

Cada institución aporta solo las palabras con las que se reconoce su PDF.
Agregar un banco o una casa comercial es agregar una línea a la tabla de su
módulo, no escribir un archivo nuevo.
"""
from .base import Cartola, MovimientoLeido, leer_cartola, BANCOS
from .analisis import enriquecer

# Importar cada módulo es lo que registra sus lectores en BANCOS: el
# decorador @registrar corre al importar, no al definir la clase en el aire.
# Sin estas líneas el registro queda vacío y no se reconoce ninguna cartola.
#
# El orden es el que se prueba al reconocer, y por eso importa:
#
#   1. Los lectores con formato propio (banco_chile, cmr), que leen mejor
#      que el motor genérico el PDF para el que fueron escritos.
#   2. Las casas comerciales, antes que los bancos: un estado de cuenta de
#      Paris o de Jumbo lleva el nombre de Scotiabank impreso, y si el
#      lector del banco lo agarrara primero buscaría una cadena de saldos
#      que ese documento no tiene.
#   3. Los bancos con nombre.
#   4. El genérico, que queda fuera del recorrido: leer_cartola lo llama
#      solo al final, si ninguno reconoció.
from . import banco_chile   # noqa: F401
from . import cmr           # noqa: F401
from . import retail        # noqa: F401
from . import universal     # noqa: F401
from . import generico      # noqa: F401

__all__ = ['Cartola', 'MovimientoLeido', 'leer_cartola', 'enriquecer', 'BANCOS']
