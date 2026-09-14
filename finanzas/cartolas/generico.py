"""El intento para bancos sin parser propio.

Es el mismo motor universal (universal.py), registrado con un nombre que se
pueda elegir a mano en la pantalla de importar y que leer_cartola use como
último recurso cuando ningún lector reconoció el PDF.

POR QUÉ ES SEGURO INTENTARLO
----------------------------
Porque el error no es silencioso. Cada fila se comprueba contra la resta de
saldos, y si el formato no era el supuesto las cuentas no dan: con menos de
85% de filas cuadradas el archivo se rechaza en vez de entregar movimientos
inventados. Las que pasan llegan a la pantalla de revisión con el aviso de
cuadre en verde o en rojo.

Dicho de otro modo: este lector no promete leer tu banco. Promete que si no
puede, te lo va a decir.
"""
from .base import registrar
from .universal import Universal


@registrar('generico', 'Otro banco (intento genérico)')
class Generico(Universal):

    # Sin pistas: nunca se ofrece solo. leer_cartola lo usa como último
    # recurso, y en el selector el usuario lo puede elegir a mano. Si
    # respondiera True se comería las cartolas que otro lector lee mejor.
    pistas = ()
    etiqueta = 'Cartola genérica'
