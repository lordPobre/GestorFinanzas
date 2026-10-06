from django.contrib.auth.decorators import login_required
from django.core import signing
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from ..seguridad import limitar
from ..templatetags.voz import SAL, puede_usar
from ..voz import sintetizar

SALUDOS = ('Buenos días', 'Buenas tardes', 'Buenas noches')
HORAS_VALIDEZ = 24


def _texto(request, campo):
    token = request.POST.get(campo, '')
    if not token:
        return ''
    try:
        datos = signing.loads(token, salt=SAL, max_age=HORAS_VALIDEZ * 3600)
    except signing.BadSignature:
        return None
    if not isinstance(datos, dict) or datos.get('u') != request.user.pk:
        return None
    return str(datos.get('t') or '')


@login_required(login_url='/login/')
@require_POST
@limitar(40, 3600, 'Ya escuchaste varios resúmenes esta hora.')
def hablar(request):
    if not puede_usar(request.user):
        return JsonResponse({'ok': False}, status=403)

    frase = _texto(request, 'frase')
    cambio = _texto(request, 'cambio')
    if frase is None or cambio is None or not frase:
        return JsonResponse({'ok': False}, status=400)

    partes = []
    saludo = request.POST.get('saludo', '')
    if cambio and saludo in SALUDOS:
        partes.append(f'{saludo}.')
    if cambio:
        partes.append(cambio)
    partes.append(frase)

    audio = sintetizar(' '.join(partes))
    if not audio:
        return JsonResponse({'ok': False}, status=503)
    respuesta = HttpResponse(audio, content_type='audio/mpeg')
    respuesta['Cache-Control'] = 'no-store'
    return respuesta
