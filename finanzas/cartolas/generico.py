from .base import registrar
from .universal import Universal


@registrar('generico', 'Otro banco (intento genérico)')
class Generico(Universal):

    pistas = ()
    etiqueta = 'Cartola genérica'
