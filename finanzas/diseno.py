from django.conf import settings

COOKIE = 'diseno'
VALOR = '2c'
ACTUAL = 'actual'
DURACION = 365 * 24 * 60 * 60


def para_todos():
    return bool(getattr(settings, 'DISENO_2C_PARA_TODOS', False))


def activo(request):
    if request is None:
        return False
    valor = request.COOKIES.get(COOKIE)
    if para_todos():
        return valor != ACTUAL
    return valor == VALOR
