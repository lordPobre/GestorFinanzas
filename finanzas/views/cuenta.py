import json
import logging
from datetime import date, datetime
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User
from django.core import signing
from django.db import transaction
from django.db.models.fields.files import FieldFile
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .. import alta as altas
from .. import auditoria, legal, marketing, sesiones, verificacion
from .. import correo as servicio_correo
from ..models import (AltaPendiente, Categoria, CodigoRespaldo, Deuda, EventoSeguridad, GastoPendiente,
                      MetaAhorro, Passkey, Persona, Presupuesto, RespuestaEncuesta, SegundoFactor,
                      SesionActiva, Suscripcion, Transaccion, UserProfile)
from ..seguridad import _ip, esta_bloqueado, limitar, limpiar_intentos, red, registrar_fallo, sumar
from ..servicios.mes import nombre_mes_es
from .. import push
from .comun import contadores, get_or_create_profile, monto_post, redirigir
from .recordatorios import CAMPOS_PUSH, opciones_de
from .acceso import _clave_sesion, configurar_2fa, entrar, verificar_codigo  # noqa: F401

logger = logging.getLogger('finanzas')

SAL_CAMBIO_CORREO = 'finanzas.correo.cambio'
HORAS_CAMBIO_CORREO = 48


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

class PerfilForm(forms.ModelForm):

    MAX_FOTO_MB = 5
    class Meta:
        model = UserProfile
        fields = ['foto', 'nombre_completo', 'email', 'telefono', 'ciudad', 'pais', 'moneda']
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'placeholder': 'Ej: Juan Pérez'}),
            'email':           forms.EmailInput(attrs={'placeholder': 'Ej: juan@email.com'}),
            'telefono':        forms.TextInput(attrs={'placeholder': 'Ej: +56 9 1234 5678'}),
            'ciudad':          forms.TextInput(attrs={'placeholder': 'Ej: Santiago'}),
            'pais':            forms.TextInput(attrs={'placeholder': 'Ej: Chile'}),
            'moneda':          forms.Select(),
            'foto':            forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def clean_foto(self):
        from django.core.files.uploadedfile import UploadedFile

        from ..fotos import recodificar

        foto = self.cleaned_data.get('foto')
        if not isinstance(foto, UploadedFile):
            return foto
        if getattr(foto, 'size', 0) > self.MAX_FOTO_MB * 1024 * 1024:
            raise forms.ValidationError(
                f'La imagen pesa demasiado. El máximo son {self.MAX_FOTO_MB} MB.')
        return recodificar(foto)

def _revisar_cambio_correo(request):
    factor = SegundoFactor.objects.filter(usuario=request.user, activo=True).first()
    con_password = request.user.has_usable_password()
    if not con_password and not factor:
        return ''
    ip, clave = _ip(request), _clave_sesion(request)
    if esta_bloqueado(clave, ip):
        return 'Demasiados intentos. Espera unos minutos antes de volver a probar.'
    if con_password:
        ok = request.user.check_password(request.POST.get('password_actual', ''))
    else:
        ok = factor.verificar(request.POST.get('codigo_actual', ''))
    if not ok:
        registrar_fallo(clave, ip)
        return ('Para cambiar el email escribe tu contraseña actual.' if con_password
                else 'Para cambiar el email escribe el código de tu app de verificación.')
    limpiar_intentos(clave, ip)
    return ''

def _pedir_cambio_correo(request, profile, nuevo):
    usuario = request.user
    profile.email_pendiente = nuevo
    profile.email_pendiente_desde = timezone.now()
    profile.save(update_fields=['email_pendiente', 'email_pendiente_desde'])

    token = signing.dumps({'uid': usuario.pk, 'nuevo': nuevo.lower(),
                           'actual': (usuario.email or '').strip().lower()},
                          salt=SAL_CAMBIO_CORREO)
    enlace = servicio_correo.url_absoluta(
        request, reverse('confirmar_cambio_correo', kwargs={'token': token}))
    servicio_correo.enviar(
        nuevo, 'Confirma tu nuevo correo en Fintora',
        render_to_string('registration/correo_cambio.txt', {
            'usuario': usuario, 'enlace': enlace, 'horas': HORAS_CAMBIO_CORREO}))

    anterior = (usuario.email or '').strip()
    if anterior:
        servicio_correo.enviar(
            anterior, 'Pidieron cambiar el correo de tu cuenta de Fintora',
            render_to_string('registration/correo_cambio_aviso.txt', {
                'usuario': usuario, 'nuevo': nuevo,
                'enlace': servicio_correo.url_absoluta(request, reverse('sesiones_activas'))}))
    auditoria.registrar('correo_cambio_pedido', request, detalle=nuevo)

@limitar(20, 3600, 'Demasiados intentos con enlaces de confirmación. Prueba más tarde.', destino='login')
def confirmar_cambio_correo(request, token):
    try:
        datos = signing.loads(token, salt=SAL_CAMBIO_CORREO,
                              max_age=HORAS_CAMBIO_CORREO * 3600)
    except signing.BadSignature:
        datos = None

    usuario = perfil = None
    if isinstance(datos, dict):
        usuario = User.objects.filter(pk=datos.get('uid'), is_active=True).first()
        perfil = UserProfile.objects.filter(usuario=usuario).first() if usuario else None

    valido = bool(
        perfil and perfil.email_pendiente
        and perfil.email_pendiente.lower() == datos.get('nuevo')
        and (usuario.email or '').strip().lower() == datos.get('actual')
        and not User.objects.filter(email__iexact=perfil.email_pendiente)
                            .exclude(pk=usuario.pk).exists())
    if not valido:
        messages.error(request, 'El enlace no sirve: venció, ya se usó o pediste otro '
                                'cambio después.')
        return redirect('perfil' if request.user.is_authenticated else 'login')

    nuevo = perfil.email_pendiente
    usuario.email = nuevo
    usuario.save(update_fields=['email'])
    perfil.email = nuevo
    perfil.email_pendiente = ''
    perfil.email_pendiente_desde = None
    perfil.correo_verificado = True
    perfil.correo_verificado_en = timezone.now()
    perfil.save(update_fields=['email', 'email_pendiente', 'email_pendiente_desde',
                               'correo_verificado', 'correo_verificado_en'])

    propia = request.user.is_authenticated and request.user.pk == usuario.pk
    actual = (request.session.session_key or '') if propia else ''
    cerradas = sesiones.cerrar_otras(usuario, actual)
    auditoria.registrar('correo_cambiado', request, usuario,
                        detalle=f'{cerradas} sesiones cerradas')
    messages.success(request, 'Listo, tu correo quedó cambiado. Cerramos las demás '
                              'sesiones abiertas.')
    return redirect('perfil' if propia else 'login')

@login_required(login_url='/login/')
def perfil(request):
    profile = get_or_create_profile(request.user)
    pw_form = PasswordChangeForm(request.user)
    perfil_form = PerfilForm(instance=profile)

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'perfil':
            email_antes = profile.email
            perfil_form = PerfilForm(request.POST, request.FILES, instance=profile)
            if perfil_form.is_valid():
                correo = (perfil_form.cleaned_data.get('email') or '').strip()
                cambia_correo = bool(correo) and (
                    correo.lower() != (request.user.email or '').strip().lower())
                error_correo = _revisar_cambio_correo(request) if cambia_correo else ''
            if perfil_form.is_valid() and error_correo:
                perfil_form.add_error('email', error_correo)
                messages.error(request, error_correo)
            elif perfil_form.is_valid():
                if cambia_correo:
                    perfil_form.instance.email = email_antes
                if request.POST.get('quitar_foto'):
                    perfil_form.instance.foto = None
                perfil_form.save()
                nombre = perfil_form.cleaned_data.get('nombre_completo', '').strip()
                if nombre:
                    partes = nombre.split(' ', 1)
                    request.user.first_name = partes[0]
                    request.user.last_name = partes[1] if len(partes) > 1 else ''
                    request.user.save(update_fields=['first_name', 'last_name'])
                if cambia_correo:
                    _pedir_cambio_correo(request, profile, correo)
                    messages.info(
                        request,
                        f'Te mandamos un enlace a {correo}. El email cambia cuando lo abras.')
                messages.success(request, 'Perfil actualizado correctamente.')
                return redirect('perfil')
        elif accion == 'password':
            ip, clave = _ip(request), _clave_sesion(request)
            if esta_bloqueado(clave, ip):
                messages.error(request, 'Demasiados intentos con la contraseña. '
                                        'Espera unos minutos.')
                return redirect('perfil')
            pw_form = PasswordChangeForm(request.user, request.POST)
            if pw_form.is_valid():
                user = pw_form.save()
                update_session_auth_hash(request, user)
                limpiar_intentos(clave, ip)
                auditoria.registrar('contrasena_cambiada', request, user)
                messages.success(request, 'Contraseña actualizada.')
                return redirect('perfil')
            if 'old_password' in pw_form.errors:
                registrar_fallo(clave, ip)
        elif accion == 'aviso_mensual':
            profile.aviso_mensual = request.POST.get('activar') == '1'
            profile.save(update_fields=['aviso_mensual'])
            messages.success(
                request,
                f'Te avisaremos cada día {profile.aviso_dia} lo que quede por pagar.'
                if profile.aviso_mensual else 'Aviso mensual desactivado.')
            return redirect('perfil')
        elif accion == 'analisis_ia':
            profile.analisis_ia = request.POST.get('activar') == '1'
            profile.save(update_fields=['analisis_ia'])
            messages.success(
                request,
                'El análisis pedirá una interpretación a la IA con tus números agregados.'
                if profile.analisis_ia
                else 'Análisis con IA desactivado. Nada saldrá del servidor.')
            return redirect('perfil')
        elif accion == 'aceptar_politica':
            profile.politica_version = legal.VERSION
            profile.politica_aceptada = timezone.now()
            profile.save(update_fields=['politica_version', 'politica_aceptada'])
            messages.success(request, 'Gracias. Quedó registrada tu aceptación.')
            return redirigir(request, 'perfil')
        elif accion == 'recordatorios':
            campo = request.POST.get('campo')
            if campo in CAMPOS_PUSH:
                setattr(profile, campo, request.POST.get('activar') == '1')
                profile.save(update_fields=[campo])
                messages.success(request, 'Listo, quedó guardado.')
            return redirect('perfil')
        elif accion == 'aviso_dia':
            try:
                dia = int(request.POST.get('aviso_dia') or 20)
            except (TypeError, ValueError):
                dia = 20
            profile.aviso_dia = min(31, max(1, dia))
            profile.save(update_fields=['aviso_dia'])
            messages.success(request, f'El aviso saldrá cada día {profile.aviso_dia}.')
            return redirect('perfil')

    context = {
        'perfil_form': perfil_form, 'pw_form': pw_form, 'profile': profile,
        'dias_aviso': range(1, 32),
        'total_trans': Transaccion.objects.filter(usuario=request.user).count(),
        'total_deudas': Deuda.objects.filter(usuario=request.user).count(),
        'miembro_desde': nombre_mes_es(request.user.date_joined.year,
                                       request.user.date_joined.month),
        'politica_al_dia': profile.politica_version == legal.VERSION,
        'push_clave': push.clave_publica(),
        'n_push': request.user.suscripciones_push.count(),
        'opciones_push': opciones_de(profile),
        'sesiones_abiertas': len(sesiones.listar(
            request.user, request.session.session_key or '')),
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/perfil.html', context)

def _valor_serializable(valor):
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, FieldFile):
        if not valor:
            return None
        try:
            return valor.url
        except Exception:
            return None
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    return str(valor)

CAMPOS_OCULTOS = {'secreto', 'codigo_hash', 'password', 'clave_publica', 'credencial_id', 'contador',
                  'endpoint', 'p256dh', 'auth'}

def _fila(obj):
    fila = {}
    for campo in obj._meta.fields:
        if campo.name in CAMPOS_OCULTOS or campo.name == 'id' or campo.is_relation:
            continue
        fila[campo.name] = _valor_serializable(getattr(obj, campo.name, None))
    return fila

def _filas(consulta):
    return [_fila(obj) for obj in consulta]

@login_required(login_url='/login/')
def mis_datos(request):
    u = request.user
    hoy = timezone.localdate()

    perfil_obj = UserProfile.objects.filter(usuario=u).first()
    factor = SegundoFactor.objects.filter(usuario=u).first()

    datos = {
        'generado': timezone.now().isoformat(),
        'aplicacion': 'Fintora',
        'cuenta': {
            'usuario': u.get_username(),
            'correo': u.email,
            'nombre': u.first_name,
            'apellido': u.last_name,
            'alta': u.date_joined.isoformat() if u.date_joined else None,
            'ultimo_acceso': u.last_login.isoformat() if u.last_login else None,
        },
        'perfil': _fila(perfil_obj) if perfil_obj else None,
        'presupuesto': _filas(Presupuesto.objects.filter(usuario=u)),
        'movimientos': _filas(Transaccion.objects.filter(usuario=u).order_by('fecha')),
        'categorias_propias': _filas(Categoria.objects.filter(usuario=u)),
        'compras_en_cuotas': [
            {**_fila(d), 'pagos': _filas(d.pagos.all())}
            for d in Deuda.objects.filter(usuario=u).prefetch_related('pagos')
        ],
        'personas': [
            {**_fila(persona), 'prestamos': [
                {**_fila(p), 'abonos': _filas(p.abonos.all())}
                for p in persona.prestamos.all()
            ]}
            for persona in Persona.objects.filter(usuario=u)
                                          .prefetch_related('prestamos__abonos')
        ],
        'metas_de_ahorro': [
            {**_fila(m), 'aportes': _filas(m.aportes.all())}
            for m in MetaAhorro.objects.filter(usuario=u).prefetch_related('aportes')
        ],
        'suscripciones': [
            {**_fila(s), 'pagos': _filas(s.pagos.all())}
            for s in Suscripcion.objects.filter(usuario=u).prefetch_related('pagos')
        ],
        'gastos_pendientes': _filas(GastoPendiente.objects.filter(usuario=u)),
        'topes_por_categoria': _filas(u.topes.all()),
        'aparatos_con_recordatorios': _filas(u.suscripciones_push.all()),
        'accesos_face_id_o_huella': _filas(Passkey.objects.filter(usuario=u)),
        'respuestas_a_la_encuesta': _filas(RespuestaEncuesta.objects.filter(usuario=u)),
        'eventos_de_seguridad': _filas(EventoSeguridad.objects.filter(usuario=u)),
        'verificacion_dos_pasos': {
            'activa': bool(factor and factor.activo),
            'codigos_de_respaldo_sin_usar': CodigoRespaldo.objects.filter(
                usuario=u, usado=False).count(),
        },
    }

    cuerpo = json.dumps(datos, ensure_ascii=False, indent=2)
    respuesta = HttpResponse(cuerpo, content_type='application/json; charset=utf-8')
    archivo = f'Fintora_mis_datos_{u.get_username()}_{hoy:%Y-%m-%d}.json'
    respuesta['Content-Disposition'] = f'attachment; filename="{archivo}"'
    logger.info('Descarga de datos personales solicitada por el usuario %s', u.pk)
    auditoria.registrar('datos_descargados', request, u)
    return respuesta

@login_required(login_url='/login/')
def eliminar_cuenta(request):
    u = request.user
    tiene_password = u.has_usable_password()

    if request.method != 'POST':
        return render(request, 'finanzas/eliminar_cuenta.html', {
            'tiene_password': tiene_password,
            'resumen': {
                'movimientos': Transaccion.objects.filter(usuario=u).count(),
                'cuotas': Deuda.objects.filter(usuario=u).count(),
                'personas': Persona.objects.filter(usuario=u).count(),
                'metas': MetaAhorro.objects.filter(usuario=u).count(),
                'suscripciones': Suscripcion.objects.filter(usuario=u).count(),
            },
            **contadores(request.user),
        })

    if request.POST.get('confirmacion', '').strip().upper() != 'ELIMINAR':
        messages.warning(request, 'Escribe ELIMINAR para confirmar.')
        return redirect('eliminar_cuenta')

    ip = _ip(request)
    clave_borrado = f'borrado:{u.pk}'
    restan = esta_bloqueado(clave_borrado, ip)
    if restan:
        minutos = max(1, restan // 60)
        messages.error(
            request,
            f'Demasiados intentos. Espera {minutos} minuto' + ('s' if minutos != 1 else '') + '.')
        return redirect('eliminar_cuenta')

    if tiene_password:
        if not u.check_password(request.POST.get('password', '')):
            registrar_fallo(clave_borrado, ip)
            messages.error(request, 'La contraseña no es correcta.')
            return redirect('eliminar_cuenta')
    elif request.POST.get('password', '').strip() != u.get_username():
        registrar_fallo(clave_borrado, ip)
        messages.error(request, 'Ese no es tu nombre de usuario.')
        return redirect('eliminar_cuenta')

    perfil_obj = UserProfile.objects.filter(usuario=u).first()
    if perfil_obj and perfil_obj.foto:
        try:
            perfil_obj.foto.delete(save=False)
        except Exception:
            logger.exception('No se pudo borrar la foto de perfil del usuario %s', u.pk)

    uid, nombre = u.pk, u.get_username()
    auditoria.registrar('cuenta_eliminada', request, u, referencia=nombre)
    logout(request)
    User.objects.filter(pk=uid).delete()
    logger.warning('Cuenta eliminada a pedido del titular: id=%s usuario=%s', uid, nombre)
    messages.success(request, 'Tu cuenta y todos tus datos fueron eliminados.')
    return redirect('login')

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
