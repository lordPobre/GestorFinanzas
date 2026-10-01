from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from ..models import EventoSeguridad, SesionActiva

DIAS = 90
MAXIMO = 150

SIN_DUENO = ('acceso_fallido', 'bloqueo')
OCULTOS = ('admin_denegado', 'cuenta_eliminada')
FALLIDOS = {'acceso_fallido', 'bloqueo', 'codigo_fallido', 'passkey_fallida'}

TEXTOS = {
    'acceso': ('Entraste', 'fa-right-to-bracket', 'green'),
    'salida': ('Cerraste sesión', 'fa-right-from-bracket', ''),
    'acceso_fallido': ('Contraseña incorrecta', 'fa-circle-xmark', 'coral'),
    'bloqueo': ('Acceso bloqueado por intentos', 'fa-lock', 'coral'),
    'codigo_fallido': ('Código de verificación incorrecto', 'fa-circle-xmark', 'coral'),
    'passkey_fallida': ('Face ID o huella rechazado', 'fa-fingerprint', 'coral'),
    '2fa_activada': ('Activaste la verificación en dos pasos', 'fa-shield-halved', 'blue'),
    '2fa_desactivada': ('Desactivaste la verificación en dos pasos', 'fa-shield-halved', 'orange'),
    'codigos_regenerados': ('Generaste códigos de respaldo nuevos', 'fa-key', 'blue'),
    'codigo_respaldo_usado': ('Usaste un código de respaldo', 'fa-key', 'orange'),
    'passkey_agregada': ('Vinculaste Face ID o huella', 'fa-fingerprint', 'blue'),
    'passkey_quitada': ('Quitaste Face ID o huella', 'fa-fingerprint', 'orange'),
    'contrasena_cambiada': ('Cambiaste la contraseña', 'fa-key', 'blue'),
    'recuperacion_pedida': ('Pediste recuperar la contraseña', 'fa-envelope', 'orange'),
    'contrasena_restablecida': ('Restableciste la contraseña', 'fa-key', 'blue'),
    'sesiones_cerradas': ('Cerraste sesiones a distancia', 'fa-laptop', 'blue'),
    'datos_descargados': ('Descargaste tus datos', 'fa-download', 'blue'),
}

METODOS = {
    'contraseña': 'Con contraseña',
    'google': 'Con Google',
    'face_id_o_huella': 'Con Face ID o huella',
    'código de verificación': 'Con contraseña y código',
    'código de respaldo': 'Con un código de respaldo',
}

CON_DETALLE = {'passkey_agregada', 'passkey_quitada', 'sesiones_cerradas'}


def _consulta(usuario):
    desde = max(timezone.now() - timedelta(days=DIAS), usuario.date_joined)
    nombres = {usuario.get_username().lower()}
    if usuario.email:
        nombres.add(usuario.email.lower())
    por_nombre = Q()
    for nombre in nombres:
        por_nombre |= Q(referencia__iexact=nombre)
    propios = Q(usuario=usuario)
    intentos = Q(usuario__isnull=True, tipo__in=SIN_DUENO) & por_nombre
    return (EventoSeguridad.objects
            .filter(propios | intentos, creado__gte=desde)
            .exclude(tipo__in=OCULTOS)
            .order_by('-creado'))


def _fila(evento):
    titulo, icono, color = TEXTOS.get(
        evento.tipo, (evento.get_tipo_display(), 'fa-circle-info', ''))
    nota = ''
    if evento.tipo == 'acceso':
        nota = METODOS.get(evento.detalle, '')
    elif evento.tipo in CON_DETALLE:
        nota = evento.detalle
    aparato = SesionActiva(agente=evento.agente).aparato if evento.agente else ''
    return {
        'titulo': titulo,
        'icono': icono,
        'color': color,
        'nota': nota,
        'aparato': aparato,
        'ip': evento.ip or '',
        'cuando': evento.creado,
        'alerta': evento.tipo in FALLIDOS,
    }


def actividad(usuario):
    eventos = list(_consulta(usuario)[:MAXIMO])
    hoy = timezone.localdate()
    dias = []
    for evento in eventos:
        dia = timezone.localtime(evento.creado).date()
        if not dias or dias[-1]['fecha'] != dia:
            dias.append({
                'fecha': dia,
                'hoy': dia == hoy,
                'ayer': dia == hoy - timedelta(days=1),
                'filas': [],
            })
        dias[-1]['filas'].append(_fila(evento))
    return {
        'dias': dias,
        'accesos': sum(1 for e in eventos if e.tipo == 'acceso'),
        'fallidos': sum(1 for e in eventos if e.tipo in FALLIDOS),
        'dias_mostrados': DIAS,
    }
