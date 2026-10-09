import logging
import time

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render

from .. import auditoria
from ..models import CodigoRespaldo, SegundoFactor
from ..seguridad import (MAX_INTENTOS as MAX_INTENTOS_LOGIN, _ip, esta_bloqueado, limpiar_intentos,
                         registrar_fallo)
from ..redirecciones import destino_seguro
from .comun import contadores

logger = logging.getLogger('finanzas')

SEGUNDOS_2FA = 5 * 60


def _clave_sesion(request):
    return f'sesion-clave:{request.user.pk}'


def _olvidar_2fa(request):
    for clave in ('2fa_pendiente', '2fa_desde', '2fa_next'):
        request.session.pop(clave, None)

def entrar(request):
    from django.contrib.auth.forms import AuthenticationForm

    ip = _ip(request)
    usuario_txt = (request.POST.get('username') or '').strip()[:150]
    restan = esta_bloqueado(usuario_txt, ip)

    if request.method == 'POST' and restan:
        minutos = max(1, restan // 60)
        messages.error(
            request,
            f'Demasiados intentos fallidos. Espera {minutos} minuto'
            + ('s' if minutos != 1 else '') + ' antes de volver a probar.')
        return render(request, 'registration/login.html',
                      {'form': AuthenticationForm(), 'bloqueado': True})

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            usuario = form.get_user()
            limpiar_intentos(usuario_txt, ip)

            factor = SegundoFactor.objects.filter(usuario=usuario, activo=True).first()
            if factor:
                request.session['2fa_pendiente'] = usuario.pk
                request.session['2fa_desde'] = time.time()
                request.session['2fa_next'] = destino_seguro(
                    request, request.POST.get('next') or request.GET.get('next'))
                return redirect('verificar_codigo')

            login(request, usuario)
            destino = destino_seguro(request, request.POST.get('next') or request.GET.get('next'))
            return redirect(destino or 'dashboard')

        intentos = registrar_fallo(usuario_txt, ip)
        quedan = MAX_INTENTOS_LOGIN - intentos
        if quedan > 0:
            messages.error(
                request,
                'Usuario o contraseña incorrectos. '
                f'Te queda{"n" if quedan != 1 else ""} {quedan} intento'
                + ('s' if quedan != 1 else '') + '.')
        else:
            auditoria.registrar('bloqueo', request, referencia=usuario_txt, detalle='contraseña')
            messages.error(request, 'Demasiados intentos. Espera 15 minutos.')
        return render(request, 'registration/login.html', {'form': form})

    return render(request, 'registration/login.html',
                  {'form': AuthenticationForm()})

def verificar_codigo(request):
    uid = request.session.get('2fa_pendiente')
    if not uid:
        return redirect('login')

    desde = request.session.get('2fa_desde')
    try:
        vencido = not desde or time.time() - float(desde) > SEGUNDOS_2FA
    except (TypeError, ValueError):
        vencido = True
    if vencido:
        _olvidar_2fa(request)
        messages.error(request, 'Pasó demasiado tiempo. Vuelve a entrar con tu contraseña.')
        return redirect('login')

    try:
        usuario = User.objects.get(pk=uid)
        factor = usuario.segundo_factor
    except (User.DoesNotExist, SegundoFactor.DoesNotExist):
        request.session.pop('2fa_pendiente', None)
        return redirect('login')

    ip = _ip(request)
    clave_2fa = f'2fa:{uid}'

    if request.method == 'POST':
        restan = esta_bloqueado(clave_2fa, ip)
        if restan:
            messages.error(request, f'Demasiados intentos. Espera {max(1, restan // 60)} minutos.')
            return render(request, 'registration/verificar.html', {'bloqueado': True})

        codigo = request.POST.get('codigo', '')
        usa_respaldo = bool(request.POST.get('es_respaldo'))

        ok = (CodigoRespaldo.consumir(usuario, codigo) if usa_respaldo
              else factor.verificar(codigo))

        if ok:
            limpiar_intentos(clave_2fa, ip)
            request.session.pop('2fa_pendiente', None)
            request.session.pop('2fa_desde', None)
            destino = destino_seguro(request, request.session.pop('2fa_next', ''))
            request.metodo_acceso = 'código de respaldo' if usa_respaldo else 'código de verificación'
            login(request, usuario)

            if usa_respaldo:
                auditoria.registrar('codigo_respaldo_usado', request, usuario)
                quedan = CodigoRespaldo.objects.filter(usuario=usuario, usado=False).count()
                messages.warning(
                    request,
                    f'Usaste un código de respaldo. Te quedan {quedan}. '
                    'Genera otros desde tu perfil si te quedan pocos.')

            return redirect(destino or 'dashboard')

        registrar_fallo(clave_2fa, ip)
        auditoria.registrar('codigo_fallido', request, usuario, detalle='acceso')
        messages.error(request, 'Código incorrecto o ya usado.')

    return render(request, 'registration/verificar.html', {
        'usuario': usuario,
        'tiene_respaldo': CodigoRespaldo.objects.filter(usuario=usuario, usado=False).exists(),
    })

def _qr_svg(uri, escala=6):
    try:
        import qrcode
    except ImportError:
        return None

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1, border=2,
    )
    qr.add_data(uri)
    qr.make(fit=True)
    matriz = qr.get_matrix()

    lado = len(matriz) * escala
    piezas = []
    for y, fila in enumerate(matriz):
        x = 0
        while x < len(fila):
            if fila[x]:
                ancho = 1
                while x + ancho < len(fila) and fila[x + ancho]:
                    ancho += 1
                piezas.append(
                    f'M{x * escala} {y * escala}h{ancho * escala}v{escala}h-{ancho * escala}z')
                x += ancho
            else:
                x += 1

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{lado}" height="{lado}" '
        f'viewBox="0 0 {lado} {lado}" shape-rendering="crispEdges" role="img" '
        f'aria-label="Código QR para configurar la verificación en dos pasos">'
        f'<rect width="{lado}" height="{lado}" fill="#ffffff"/>'
        f'<path d="{"".join(piezas)}" fill="#191919"/>'
        f'</svg>'
    )

def _confirma_identidad(request, factor):
    ip, clave = _ip(request), _clave_sesion(request)
    if esta_bloqueado(clave, ip):
        return False
    if request.user.has_usable_password():
        ok = request.user.check_password(request.POST.get('password', ''))
    else:
        ok = factor.verificar(request.POST.get('codigo', ''))
    if ok:
        limpiar_intentos(clave, ip)
    else:
        registrar_fallo(clave, ip)
    return ok

def _error_identidad(request):
    if esta_bloqueado(_clave_sesion(request), _ip(request)):
        return 'Demasiados intentos. Espera unos minutos antes de volver a probar.'
    if request.user.has_usable_password():
        return 'Contraseña incorrecta.'
    return 'El código no coincide. Revisa la hora de tu teléfono.'

@login_required(login_url='/login/')
def configurar_2fa(request):
    factor, _ = SegundoFactor.objects.get_or_create(
        usuario=request.user,
        defaults={'secreto': SegundoFactor.generar_secreto()},
    )

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'activar':
            if factor.verificar(request.POST.get('codigo', '')):
                factor.activo = True
                factor.save(update_fields=['activo'])
                codigos = CodigoRespaldo.generar(request.user)
                auditoria.registrar('2fa_activada', request)
                messages.success(request, 'Verificación en dos pasos activada.')
                return render(request, 'finanzas/codigos_respaldo.html',
                              {'codigos': codigos, 'recien_creados': True, **contadores(request.user)})
            messages.error(request, 'El código no coincide. Revisa la hora de tu teléfono.')

        elif accion == 'desactivar':
            if not _confirma_identidad(request, factor):
                messages.error(request, _error_identidad(request))
                return redirect('configurar_2fa')
            factor.delete()
            CodigoRespaldo.objects.filter(usuario=request.user).delete()
            auditoria.registrar('2fa_desactivada', request)
            messages.success(request, 'Verificación en dos pasos desactivada.')
            return redirect('perfil')

        elif accion == 'regenerar':
            if not _confirma_identidad(request, factor):
                messages.error(request, _error_identidad(request))
                return redirect('configurar_2fa')
            codigos = CodigoRespaldo.generar(request.user)
            auditoria.registrar('codigos_regenerados', request)
            return render(request, 'finanzas/codigos_respaldo.html',
                          {'codigos': codigos, 'recien_creados': False, **contadores(request.user)})

    contexto = {
        'factor': factor,
        'tiene_password': request.user.has_usable_password(),
        'codigos_restantes': CodigoRespaldo.objects.filter(
            usuario=request.user, usado=False).count(),
    }
    if not factor.activo:
        contexto['uri'] = factor.uri()
        contexto['secreto'] = factor.secreto
        contexto['qr_svg'] = _qr_svg(factor.uri())
        s = factor.secreto
        contexto['secreto_legible'] = ' '.join(s[i:i + 4] for i in range(0, len(s), 4))
    contexto.update(contadores(request.user))
    return render(request, 'finanzas/configurar_2fa.html', contexto)
