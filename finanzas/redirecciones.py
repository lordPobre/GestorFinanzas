from django.utils.http import url_has_allowed_host_and_scheme


def destino_seguro(request, valor, por_defecto=''):
    valor = (valor or '').strip()
    if not valor.startswith('/') or valor.startswith('//') or '\\' in valor:
        return por_defecto
    if any(ord(c) < 32 or ord(c) == 127 for c in valor):
        return por_defecto
    if not url_has_allowed_host_and_scheme(valor, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        return por_defecto
    return valor
