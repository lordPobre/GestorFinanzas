COOKIE = 'diseno'
VALOR = '2c'
DURACION = 365 * 24 * 60 * 60


def activo(request):
    return request is not None and request.COOKIES.get(COOKIE) == VALOR
