from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .. import telegram
from ..models import ChatTelegram, ClaveApi
from ..seguridad import sumar
from .api import nueva_clave
from .comun import contadores


TOPE_CLAVES_HORA = 10


@login_required(login_url='/login/')
def clave_api(request):
    nueva = ''
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'crear':
            usadas, _ = sumar(f'clave_api:{request.user.pk}', 3600)
            if usadas > TOPE_CLAVES_HORA:
                messages.warning(request, 'Creaste varias claves seguidas. Espera un rato.')
                return redirect('clave_api')
            nueva = nueva_clave(request.user)
        elif accion == 'revocar':
            ClaveApi.objects.filter(usuario=request.user).delete()
            messages.success(request, 'Revocaste la clave. Lo que la usaba deja de funcionar.')
            return redirect('clave_api')
        elif accion == 'telegram_quitar':
            vinculo = ChatTelegram.objects.filter(usuario=request.user).first()
            if vinculo:
                telegram.llamar('sendMessage', chat_id=vinculo.chat_id,
                                text='Desconectaste este chat desde Fintora. Ya no anoto lo que me escribas aquí.')
                vinculo.delete()
            messages.success(request, 'Desconectaste Telegram.')
            return redirect('clave_api')
    chat = ChatTelegram.objects.filter(usuario=request.user).first()
    listo = telegram.configurado()
    ctx = {
        'clave': ClaveApi.objects.filter(usuario=request.user).first(),
        'nueva': nueva,
        'telegram_listo': listo,
        'chat_telegram': chat,
        'enlace_telegram': telegram.enlace(telegram.nuevo_codigo(request.user)) if listo and not chat else '',
    }
    ctx.update(contadores(request.user))
    respuesta = render(request, 'finanzas/clave_api.html', ctx)
    respuesta['Cache-Control'] = 'no-store'
    return respuesta
