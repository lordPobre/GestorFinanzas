import logging

from django import forms
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .. import alta as altas
from .. import auditoria, marketing, sesiones, verificacion
from .. import correo as servicio_correo
from ..models import (AltaPendiente, CodigoRespaldo, Deuda, Presupuesto, SegundoFactor, SesionActiva,
                      Transaccion, UserProfile)
from ..seguridad import _ip, limitar, limpiar_intentos, red, sumar
from .comun import contadores, get_or_create_profile, monto_post
from .acceso import _clave_sesion, configurar_2fa, entrar, verificar_codigo  # noqa: F401
from .perfil import HORAS_CAMBIO_CORREO, SAL_CAMBIO_CORREO, PerfilForm  # noqa: F401
from .perfil import confirmar_cambio_correo, eliminar_cuenta, mis_datos, perfil  # noqa: F401

logger = logging.getLogger('finanzas')

MAX_SOLICITUDES_RESET = 3
VENTANA_RESET = 900
MAX_RESET_POR_CORREO = 3
VENTANA_RESET_CORREO = 3600
MAX_AVISOS_REGISTRO = 2

def _usuario_por_correo(correo):
    correo = (correo or '').strip()
    if not correo:
        return None
    usuario = User.objects.filter(email__iexact=correo, is_active=True).first()
    if usuario:
        return usuario
    perfil = UserProfile.objects.filter(email__iexact=correo,
                                        usuario__is_active=True).first()
    return perfil.usuario if perfil else None

def recuperar(request):
    from django.contrib.auth.tokens import default_token_generator
    from django.template.loader import render_to_string
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    from ..correo import configurado as correo_configurado, enviar, url_absoluta

    enviado = False
    correo_txt = ''

    if request.method == 'POST':
        correo_txt = (request.POST.get('email') or '').strip()

        usados, _ = sumar(f'reset:{red(_ip(request))}', VENTANA_RESET)
        if usados > MAX_SOLICITUDES_RESET:
            messages.warning(
                request,
                'Ya pediste varios enlaces. Espera unos minutos antes de intentarlo otra vez.')
            return render(request, 'registration/recuperar.html',
                          {'email': correo_txt})

        por_correo, _ = sumar(f'reset-correo:{correo_txt.lower()[:150]}', VENTANA_RESET_CORREO)
        usuario = (_usuario_por_correo(correo_txt)
                   if por_correo <= MAX_RESET_POR_CORREO else None)
        if usuario:
            auditoria.registrar('recuperacion_pedida', request, usuario)
            enlace = url_absoluta(request, reverse('restablecer', kwargs={
                'uidb64': urlsafe_base64_encode(force_bytes(usuario.pk)),
                'token': default_token_generator.make_token(usuario),
            }))
            contexto_correo = {
                'usuario': usuario,
                'enlace': enlace,
                'horas': 1,
            }
            cuerpo = render_to_string('registration/correo_recuperar.txt', contexto_correo)
            cuerpo_html = render_to_string('registration/correo_recuperar.html', contexto_correo)
            if not enviar(usuario.email or correo_txt,
                          'Recupera tu contraseña de Fintora', cuerpo, cuerpo_html):
                logging.getLogger('finanzas').error(
                    'Reset solicitado para %s pero el correo no salió', usuario.pk)
                if not correo_configurado():
                    messages.error(
                        request,
                        'El envío de correos no está configurado todavía. '
                        'Escríbeme y te ayudo a restablecerla a mano.')
                    return render(request, 'registration/recuperar.html',
                                  {'email': correo_txt})
        enviado = True

    return render(request, 'registration/recuperar.html',
                  {'enviado': enviado, 'email': correo_txt})

@limitar(20, 3600, 'Demasiados intentos con enlaces de recuperación. Prueba más tarde.', destino='login')
def restablecer(request, uidb64, token):
    from django.contrib.auth.forms import SetPasswordForm
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_str
    from django.utils.http import urlsafe_base64_decode

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        usuario = User.objects.get(pk=uid, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        usuario = None

    valido = usuario is not None and default_token_generator.check_token(usuario, token)
    if not valido:
        return render(request, 'registration/restablecer.html', {'valido': False})

    factor = SegundoFactor.objects.filter(usuario=usuario, activo=True).first()
    form = SetPasswordForm(usuario)

    if request.method == 'POST':
        form = SetPasswordForm(usuario, request.POST)

        codigo_ok = True
        if factor:
            codigo = (request.POST.get('codigo') or '').strip()
            es_respaldo = request.POST.get('es_respaldo') == '1'
            if es_respaldo:
                codigo_ok = CodigoRespaldo.consumir(usuario, codigo)
            else:
                codigo_ok = factor.verificar(codigo)
            if not codigo_ok:
                auditoria.registrar('codigo_fallido', request, usuario, detalle='restablecer')
                form.add_error(None, 'El código de verificación no es correcto.')

        if form.is_valid() and codigo_ok:
            form.save()
            limpiar_intentos(usuario.username, _ip(request))
            auditoria.registrar('contrasena_restablecida', request, usuario)
            messages.success(request, 'Tu contraseña quedó cambiada. Entra con ella.')
            return redirect('login')

    return render(request, 'registration/restablecer.html', {
        'valido': True,
        'form': form,
        'usuario': usuario,
        'pide_codigo': factor is not None,
        'tiene_respaldo': factor is not None and CodigoRespaldo.objects.filter(
            usuario=usuario, usado=False).exists(),
    })

def _avisar_registro_repetido(request, correo):
    enviados, _ = sumar(f'registro-repetido:{correo.lower()[:150]}', 86400)
    if enviados > MAX_AVISOS_REGISTRO:
        return
    contexto = {
        'entrar': servicio_correo.url_absoluta(request, reverse('login')),
        'recuperar': servicio_correo.url_absoluta(request, reverse('recuperar')),
    }
    servicio_correo.enviar(correo, 'Ya tienes una cuenta en Fintora',
                           render_to_string('registration/correo_registro_repetido.txt', contexto))
    logger.info('Registro con un correo que ya tiene cuenta: aviso enviado')

@limitar(5, 3600, 'Demasiados registros desde esta conexión. Prueba más tarde.')
def registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        correo = (request.POST.get('email_perfil') or '').strip()
        error_correo = ''
        acepta = bool(request.POST.get('acepta_politica'))
        correo_ocupado = False

        if not correo:
            error_correo = 'Necesitamos tu email para poder recuperar tu contraseña.'
        else:
            try:
                forms.EmailField().clean(correo)
            except forms.ValidationError:
                error_correo = 'Ese email no parece válido. Revísalo.'
            else:
                correo_ocupado = User.objects.filter(email__iexact=correo).exists()

        if not acepta:
            error_correo = error_correo or (
                'Tienes que aceptar la política de privacidad y los términos de uso.')

        if form.is_valid() and not error_correo:
            if correo_ocupado:
                _avisar_registro_repetido(request, correo)
            else:
                altas.pedir(request, form.cleaned_data['username'], form.cleaned_data['password1'],
                            correo, request.POST.get('nombre_completo', '').strip())
            messages.info(request, f'Te mandamos un correo a {correo}. Ábrelo para seguir.')
            return redirect('login')

        if error_correo:
            form.add_error(None, error_correo)
    else:
        form = UserCreationForm()
    return render(request, 'registration/registro.html', {'form': form})

@login_required(login_url='/login/')
def onboarding(request):
    profile = get_or_create_profile(request.user)
    if profile.onboarding_completado:
        return redirect('dashboard')
    return render(request, 'finanzas/onboarding.html', {'profile': profile})

@login_required(login_url='/login/')
def completar_onboarding(request):
    if request.method != 'POST':
        return redirect('dashboard')

    ingreso_monto = monto_post(request, 'ingreso_monto')
    if ingreso_monto > 0:
        Transaccion.objects.create(
            usuario=request.user, tipo='INGRESO', monto=ingreso_monto,
            categoria='Sueldo',
            descripcion=request.POST.get('ingreso_desc') or 'Ingreso mensual',
            fecha=timezone.localdate(),
        )

    acreedor = request.POST.get('deuda_acreedor', '').strip()
    deuda_cuota = monto_post(request, 'deuda_cuota')
    if acreedor and deuda_cuota > 0:
        try:
            cuotas = max(1, int(request.POST.get('deuda_cuotas', 1)))
        except (ValueError, TypeError):
            cuotas = 1
        Deuda.objects.create(
            usuario=request.user, acreedor=acreedor,
            monto_total=deuda_cuota * cuotas, cuotas_totales=cuotas,
            fecha_inicio=timezone.localdate(),
        )

    presupuesto_val = monto_post(request, 'presupuesto')
    if presupuesto_val > 0:
        p, _ = Presupuesto.objects.get_or_create(
            usuario=request.user, defaults={'limite_mensual': presupuesto_val})
        p.limite_mensual = presupuesto_val
        p.save(update_fields=['limite_mensual'])

    profile = get_or_create_profile(request.user)
    profile.onboarding_completado = True
    profile.save(update_fields=['onboarding_completado'])
    messages.success(request, f'Listo, {profile.nombre_display}. Tu mes ya está armado.')
    return redirect(reverse('dashboard') + '?tour=1')


@limitar(20, 3600, 'Demasiados intentos con enlaces de confirmación. Prueba más tarde.', destino='login')
def confirmar_alta(request, token):
    pendiente = altas.buscar(token)
    if pendiente is None:
        return render(request, 'registration/alta_confirmar.html', {'valido': False})
    if request.method != 'POST':
        return render(request, 'registration/alta_confirmar.html', {'valido': True, 'alta': pendiente})

    with transaction.atomic():
        pendiente = AltaPendiente.objects.select_for_update().filter(pk=pendiente.pk).first()
        if pendiente is None:
            return render(request, 'registration/alta_confirmar.html', {'valido': False})
        if User.objects.filter(email__iexact=pendiente.correo).exists():
            pendiente.delete()
            messages.info(request, 'Ese correo ya tiene una cuenta. Entra con ella.')
            return redirect('login')
        if User.objects.filter(username__iexact=pendiente.username).exists():
            pendiente.delete()
            messages.warning(request, 'Alguien tomó ese nombre de usuario mientras tanto. '
                                      'Regístrate de nuevo con otro.')
            return redirect('registro')
        user = User.objects.create(username=pendiente.username, email=pendiente.correo,
                                   password=pendiente.password)
        profile, _ = UserProfile.objects.get_or_create(usuario=user)
        profile.nombre_completo = pendiente.nombre_completo
        profile.email = pendiente.correo
        profile.politica_version = pendiente.politica_version
        profile.politica_aceptada = pendiente.creada
        profile.correo_verificado = True
        profile.correo_verificado_en = timezone.now()
        profile.save()
        pendiente.delete()

    login(request, user)
    marketing.marcar_registro(request)
    logger.info('Alta de cuenta %s con politica version %s', user.pk, profile.politica_version)
    messages.success(request, 'Listo, tu cuenta quedó creada y tu correo confirmado.')
    return redirect('onboarding')

@limitar(20, 3600, 'Demasiados intentos con enlaces de confirmación. Prueba más tarde.', destino='login')
def verificar_correo(request, token):
    usuario = verificacion.usuario_de(token)
    if usuario is None:
        return render(request, 'registration/correo_confirmado.html', {'valido': False})

    perfil = get_or_create_profile(usuario)
    nuevo = not perfil.correo_verificado
    if nuevo:
        verificacion.marcar(perfil)
        logger.info('Correo confirmado por el usuario %s', usuario.pk)

    return render(request, 'registration/correo_confirmado.html', {
        'valido': True,
        'usuario': usuario,
        'nuevo': nuevo,
        'con_sesion': request.user.is_authenticated and request.user.pk == usuario.pk,
    })

@login_required(login_url='/login/')
@limitar(4, 3600, 'Ya pediste varios correos de confirmación. Espera un rato.')
def reenviar_verificacion(request):
    if request.method != 'POST':
        return redirect('perfil')

    perfil = get_or_create_profile(request.user)
    if perfil.correo_verificado:
        return redirect('perfil')

    destino = (request.user.email or '').strip()
    if not destino:
        messages.error(request, 'Primero guarda un correo en tus datos.')
    elif verificacion.enviar(request, request.user):
        messages.success(request, f'Te mandamos otro correo a {destino}.')
    else:
        messages.error(request,
                       'No se pudo enviar el correo. Revisa que la dirección esté bien escrita.')
    return redirect('perfil')

@login_required(login_url='/login/')
def sesiones_activas(request):
    clave = request.session.session_key or ''

    if request.method == 'POST':
        if request.POST.get('accion') == 'cerrar_todas':
            cerradas = sesiones.cerrar_otras(request.user, clave)
            if cerradas:
                auditoria.registrar('sesiones_cerradas', request, detalle=f'{cerradas} sesiones')
                messages.success(
                    request,
                    f'Cerramos {cerradas} sesión{"es" if cerradas != 1 else ""}. '
                    'Esta sigue abierta.')
            else:
                messages.info(request, 'No había otras sesiones abiertas.')
        else:
            objetivo = (request.POST.get('sesion') or '').strip()
            fila = (SesionActiva.objects.filter(usuario=request.user, pk=int(objetivo)).first()
                    if objetivo.isdigit() else None)
            if fila and fila.clave == clave:
                messages.warning(request,
                                 'Esa es la sesión que estás usando. Para cerrarla, sal de la cuenta.')
            elif fila and sesiones.cerrar(request.user, fila.clave):
                auditoria.registrar('sesiones_cerradas', request, detalle='1 sesión')
                messages.success(request, 'Sesión cerrada.')
            else:
                messages.info(request, 'Esa sesión ya no estaba abierta.')
        return redirect('sesiones_activas')

    contexto = {
        'sesiones': sesiones.listar(request.user, clave),
        'minutos_refresco': sesiones.MINUTOS_REFRESCO,
    }
    contexto.update(contadores(request.user))
    return render(request, 'finanzas/sesiones.html', contexto)

