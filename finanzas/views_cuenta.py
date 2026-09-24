"""Cuenta: entrar, registrarse, perfil, datos personales y cierre.

Estaba todo en views.py junto al dashboard, las cuotas y las metas. Son
áreas distintas: acá no se calcula ni un peso — se decide quién entra, qué
aceptó, qué se lleva y qué se borra. Tenerlo aparte hace que un cambio en el
acceso no obligue a leer dos mil líneas de finanzas, y que las pruebas de
cuenta importen solo esto.

Lo que sigue en views.py son las pantallas de plata. Este módulo importa de
allí tres ayudas compartidas (contadores, el perfil y el nombre del mes) y
nunca al revés, así que no hay import circular.
"""
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
from django.db.models.fields.files import FieldFile
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from . import auditoria, legal, sesiones, verificacion
from .models import (Categoria, CodigoRespaldo, Deuda, EventoSeguridad, GastoPendiente, MetaAhorro,
                     Passkey, Persona, Presupuesto, RespuestaEncuesta, SegundoFactor, Suscripcion,
                     Transaccion, UserProfile)
from .seguridad import (MAX_INTENTOS as MAX_INTENTOS_LOGIN, _ip, esta_bloqueado,
                        limitar, limpiar_intentos, registrar_fallo)
from .views import _monto_post, contadores, get_or_create_profile, nombre_mes_es

logger = logging.getLogger('finanzas')

def entrar(request):
    """Acceso con tope de intentos.

    La LoginView de Django no limita nada: se pueden probar contraseñas sin
    fin. En una app con datos financieros eso es la puerta más fácil, así
    que cinco fallos bloquean quince minutos.
    """
    from django.contrib.auth import authenticate
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
                request.session['2fa_next'] = request.POST.get('next') or request.GET.get('next', '')
                return redirect('verificar_codigo')

            login(request, usuario)
            destino = request.POST.get('next') or request.GET.get('next')
            if destino and destino.startswith('/') and not destino.startswith('//'):
                return redirect(destino)
            return redirect('dashboard')

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
    """Segundo paso del acceso.

    El usuario llega con '2fa_pendiente' en la sesión, puesto por entrar().
    Hasta que el código sea correcto no hay login(), así que no puede tocar
    ninguna pantalla de la app.
    """
    uid = request.session.get('2fa_pendiente')
    if not uid:
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
            destino = request.session.pop('2fa_next', '')
            request.metodo_acceso = 'código de respaldo' if usa_respaldo else 'código de verificación'
            login(request, usuario)

            if usa_respaldo:
                auditoria.registrar('codigo_respaldo_usado', request, usuario)
                quedan = CodigoRespaldo.objects.filter(usuario=usuario, usado=False).count()
                messages.warning(
                    request,
                    f'Usaste un código de respaldo. Te quedan {quedan}. '
                    'Genera otros desde tu perfil si te quedan pocos.')

            if destino and destino.startswith('/') and not destino.startswith('//'):
                return redirect(destino)
            return redirect('dashboard')

        registrar_fallo(clave_2fa, ip)
        auditoria.registrar('codigo_fallido', request, usuario, detalle='acceso')
        messages.error(request, 'Código incorrecto o ya usado.')

    return render(request, 'registration/verificar.html', {
        'usuario': usuario,
        'tiene_respaldo': CodigoRespaldo.objects.filter(usuario=usuario, usado=False).exists(),
    })

def _qr_svg(uri, escala=6):
    """Código QR como SVG, listo para incrustar en el HTML.

    SVG y no PNG: escala sin pixelarse y no necesita Pillow ni guardar un
    archivo. Se dibuja como una sola ruta de rectángulos, que pesa poco.

    Si la librería no está instalada devuelve None y la pantalla muestra la
    clave manual, que funciona igual de bien aunque sea más incómoda.
    """
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

@login_required(login_url='/login/')
def configurar_2fa(request):
    """Activar la verificación en dos pasos.

    El secreto se crea al abrir la pantalla pero el factor queda inactivo
    hasta que el usuario confirme un código. Así se comprueba que su app
    quedó bien configurada ANTES de exigirle el código para entrar — si no,
    se quedaría fuera de su propia cuenta.
    """
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
                              {'codigos': codigos, 'recien_creados': True})
            messages.error(request, 'El código no coincide. Revisa la hora de tu teléfono.')

        elif accion == 'desactivar':
            if not request.user.check_password(request.POST.get('password', '')):
                messages.error(request, 'Contraseña incorrecta.')
                return redirect('configurar_2fa')
            factor.delete()
            CodigoRespaldo.objects.filter(usuario=request.user).delete()
            auditoria.registrar('2fa_desactivada', request)
            messages.success(request, 'Verificación en dos pasos desactivada.')
            return redirect('perfil')

        elif accion == 'regenerar':
            if not request.user.check_password(request.POST.get('password', '')):
                messages.error(request, 'Contraseña incorrecta.')
                return redirect('configurar_2fa')
            codigos = CodigoRespaldo.generar(request.user)
            auditoria.registrar('codigos_regenerados', request)
            return render(request, 'finanzas/codigos_respaldo.html',
                          {'codigos': codigos, 'recien_creados': False})

    contexto = {
        'factor': factor,
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

MAX_SOLICITUDES_RESET = 3
VENTANA_RESET = 900

def _usuario_por_correo(correo):
    """Busca por User.email y, si no aparece, por UserProfile.email.

    Las cuentas creadas antes de que el email fuera obligatorio guardaban
    el correo solo en el perfil. Sin este segundo intento, esos usuarios no
    podrían recuperar nunca su contraseña.
    """
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
    """Pide el correo y manda el enlace."""
    from django.contrib.auth.tokens import default_token_generator
    from django.core.cache import cache
    from django.template.loader import render_to_string
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    from .correo import configurado as correo_configurado, enviar, url_absoluta

    enviado = False
    correo_txt = ''

    if request.method == 'POST':
        correo_txt = (request.POST.get('email') or '').strip()

        clave = f'reset:{_ip(request)}'
        usados = cache.get(clave, 0)
        if usados >= MAX_SOLICITUDES_RESET:
            messages.warning(
                request,
                'Ya pediste varios enlaces. Espera unos minutos antes de intentarlo otra vez.')
            return render(request, 'registration/recuperar.html',
                          {'email': correo_txt})
        cache.set(clave, usados + 1, VENTANA_RESET)

        usuario = _usuario_por_correo(correo_txt)
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
                          'Recupera tu contraseña de Rekon', cuerpo, cuerpo_html):
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

def restablecer(request, uidb64, token):
    """Valida el enlace y cambia la contraseña."""
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

@limitar(5, 3600, 'Demasiados registros desde esta conexión. Prueba más tarde.')
def registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        correo = (request.POST.get('email_perfil') or '').strip()
        error_correo = ''
        acepta = bool(request.POST.get('acepta_politica'))

        if not correo:
            error_correo = 'Necesitamos tu email para poder recuperar tu contraseña.'
        else:
            try:
                forms.EmailField().clean(correo)
            except forms.ValidationError:
                error_correo = 'Ese email no parece válido. Revísalo.'
            else:
                if User.objects.filter(email__iexact=correo).exists():
                    error_correo = 'Ya hay una cuenta con ese email.'

        if not acepta:
            error_correo = error_correo or (
                'Tienes que aceptar la política de privacidad y los términos de uso.')

        if form.is_valid() and not error_correo:
            user = form.save(commit=False)
            user.email = correo
            user.save()
            login(request, user)
            profile, _ = UserProfile.objects.get_or_create(usuario=user)
            profile.nombre_completo = request.POST.get('nombre_completo', '').strip()
            profile.email = correo
            profile.politica_version = legal.VERSION
            profile.politica_aceptada = timezone.now()
            profile.save()
            logger.info('Alta de cuenta %s con politica version %s',
                        user.pk, legal.VERSION)

            # Doble opt-in: el correo queda sin confirmar hasta que la
            # persona abra el enlace. No se le impide entrar — se le avisa.
            if verificacion.enviar(request, user):
                messages.info(
                    request,
                    f'Te mandamos un correo a {correo} para confirmar la dirección.')
            return redirect('onboarding')

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

    ingreso_monto = _monto_post(request, 'ingreso_monto')
    if ingreso_monto > 0:
        Transaccion.objects.create(
            usuario=request.user, tipo='INGRESO', monto=ingreso_monto,
            categoria='Sueldo',  # antes 'Otros': el sueldo es la categoría real
            descripcion=request.POST.get('ingreso_desc') or 'Ingreso mensual',
            fecha=timezone.localdate(),
        )

    acreedor = request.POST.get('deuda_acreedor', '').strip()
    deuda_cuota = _monto_post(request, 'deuda_cuota')
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

    presupuesto_val = _monto_post(request, 'presupuesto')
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
    """Antes se definía dentro de la vista, así que se reconstruía en cada
    request y no se podía importar desde otro módulo."""

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
        """Una foto de teléfono pesa 5-12 MB sin comprimir. Sin tope, el
        servidor las guarda todas y el avatar de 40px descarga megas."""
        foto = self.cleaned_data.get('foto')
        if foto and getattr(foto, 'size', 0) > self.MAX_FOTO_MB * 1024 * 1024:
            raise forms.ValidationError(
                f'La imagen pesa demasiado. El máximo son {self.MAX_FOTO_MB} MB.')
        return foto

@login_required(login_url='/login/')
def perfil(request):
    profile = get_or_create_profile(request.user)
    pw_form = PasswordChangeForm(request.user)
    perfil_form = PerfilForm(instance=profile)

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'perfil':
            perfil_form = PerfilForm(request.POST, request.FILES, instance=profile)
            if perfil_form.is_valid():
                if request.POST.get('quitar_foto'):
                    perfil_form.instance.foto = None
                perfil_form.save()
                nombre = perfil_form.cleaned_data.get('nombre_completo', '').strip()
                if nombre:
                    partes = nombre.split(' ', 1)
                    request.user.first_name = partes[0]
                    request.user.last_name = partes[1] if len(partes) > 1 else ''
                    request.user.save(update_fields=['first_name', 'last_name'])
                correo = (perfil_form.cleaned_data.get('email') or '').strip()
                if correo and correo.lower() != (request.user.email or '').lower():
                    if not User.objects.filter(email__iexact=correo).exclude(
                            pk=request.user.pk).exists():
                        request.user.email = correo
                        request.user.save(update_fields=['email'])
                        # La dirección nueva no está comprobada: dar por
                        # verificado lo que nadie confirmó vaciaría de
                        # sentido el paso del registro.
                        profile.correo_verificado = False
                        profile.correo_verificado_en = None
                        profile.save(update_fields=['correo_verificado',
                                                    'correo_verificado_en'])
                        verificacion.enviar(request, request.user)
                    else:
                        messages.warning(
                            request,
                            'Ese email ya está en otra cuenta, así que no se usará '
                            'para recuperar la contraseña de esta.')
                messages.success(request, 'Perfil actualizado correctamente.')
                return redirect('perfil')
        elif accion == 'password':
            pw_form = PasswordChangeForm(request.user, request.POST)
            if pw_form.is_valid():
                user = pw_form.save()
                update_session_auth_hash(request, user)
                auditoria.registrar('contrasena_cambiada', request, user)
                messages.success(request, 'Contraseña actualizada.')
                return redirect('perfil')
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

CAMPOS_OCULTOS = {'secreto', 'codigo_hash', 'password', 'clave_publica', 'credencial_id', 'contador'}

def _fila(obj):
    """Un objeto como diccionario plano, sin claves ajenas ni secretos."""
    fila = {}
    for campo in obj._meta.fields:
        if campo.name in CAMPOS_OCULTOS or campo.name == 'id' or campo.is_relation:
            continue
        fila[campo.name] = _valor_serializable(getattr(obj, campo.name, None))
    return fila

def _filas(consulta):
    """Los objetos de una consulta como lista de diccionarios planos."""
    return [_fila(obj) for obj in consulta]

@login_required(login_url='/login/')
def mis_datos(request):
    """Todo lo que la app guarda de ti, en un solo archivo JSON.

    La exportación a Excel y CSV entrega los movimientos, que es lo que se
    usa a diario. Esto es distinto: es el expediente completo —perfil,
    personas, préstamos, metas, suscripciones, presupuesto, estado del
    segundo factor— para que puedas llevártelo o revisarlo. JSON y no Excel
    porque tiene que ser fiel, no bonito.
    """
    u = request.user
    hoy = timezone.localdate()

    perfil_obj = UserProfile.objects.filter(usuario=u).first()
    factor = SegundoFactor.objects.filter(usuario=u).first()

    datos = {
        'generado': timezone.now().isoformat(),
        'aplicacion': 'Rekon',
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
    archivo = f'Rekon_mis_datos_{u.get_username()}_{hoy:%Y-%m-%d}.json'
    respuesta['Content-Disposition'] = f'attachment; filename="{archivo}"'
    logger.info('Descarga de datos personales solicitada por el usuario %s', u.pk)
    auditoria.registrar('datos_descargados', request, u)
    return respuesta

@login_required(login_url='/login/')
def eliminar_cuenta(request):
    """Borra la cuenta y todo lo que cuelga de ella. Sin vuelta atrás.

    Se pide la contraseña otra vez, no basta con tener la sesión abierta:
    un teléfono desbloqueado y desatendido no debería poder borrar el
    historial financiero de su dueño. Quien entró con Google no tiene
    contraseña utilizable, así que a esa cuenta se le pide escribir su
    nombre de usuario.

    Todas las claves ajenas a User son CASCADE, así que user.delete() se
    lleva movimientos, cuotas, personas, préstamos, metas, suscripciones,
    categorías, presupuesto y segundo factor. Lo único que no viaja en la
    cascada es la foto: vive en R2 o en el disco, y hay que borrarla a mano
    antes de perder la referencia.
    """
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
        })

    if request.POST.get('confirmacion', '').strip().upper() != 'ELIMINAR':
        messages.warning(request, 'Escribe ELIMINAR para confirmar.')
        return redirect('eliminar_cuenta')

    if tiene_password:
        if not u.check_password(request.POST.get('password', '')):
            registrar_fallo(f'borrado:{u.pk}', _ip(request))
            messages.error(request, 'La contraseña no es correcta.')
            return redirect('eliminar_cuenta')
    elif request.POST.get('password', '').strip() != u.get_username():
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

def verificar_correo(request, token):
    """Confirma la dirección desde el enlace del correo.

    No inicia sesión. Abrir el enlace prueba que la dirección existe, no que
    quien lo abre sea el dueño de la cuenta: cualquiera con acceso a esa
    bandeja —o un reenvío— entraría sin contraseña.
    """
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
    """Las sesiones abiertas de la cuenta, con cierre a distancia.

    Cambiar la contraseña no cierra las sesiones ya abiertas: Django las
    mantiene vivas a propósito para no echar de la app a quien la cambia. Si
    alguien se quedó dentro en un computador ajeno, esta pantalla es la única
    forma de sacarlo sin esperar a que caduque.
    """
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
            objetivo = (request.POST.get('clave') or '').strip()
            if objetivo and objetivo == clave:
                messages.warning(request,
                                 'Esa es la sesión que estás usando. Para cerrarla, sal de la cuenta.')
            elif sesiones.cerrar(request.user, objetivo):
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
