import hashlib
import json
import secrets
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .. import fechas
from ..categorias_base import SLUGS_BASE
from ..models import Categoria, ClaveApi, Transaccion
from ..seguridad import sumar
from ..servicios.anotar_texto import MAX_MONTO, interpretar
from ..templatetags.moneda import money
from .comun import simbolo_de

PREFIJO = 'ftr_'
TOPE_HORA = 120
HORAS_DESHACER = 24


def huella(clave):
    return hashlib.sha256(clave.encode()).hexdigest()


def nueva_clave(usuario):
    clave = PREFIJO + secrets.token_urlsafe(32)
    with transaction.atomic():
        ClaveApi.objects.filter(usuario=usuario).delete()
        ClaveApi.objects.create(usuario=usuario, huella=huella(clave), prefijo=clave[:8])
    return clave


def _usuario(request):
    cabecera = request.headers.get('Authorization', '')
    if not cabecera.startswith('Bearer '):
        return None
    clave = cabecera[7:].strip()
    if not clave.startswith(PREFIJO) or len(clave) > 100:
        return None
    fila = ClaveApi.objects.select_related('usuario').filter(huella=huella(clave), usuario__is_active=True).first()
    if fila is None:
        return None
    ahora = timezone.now()
    if fila.usada is None or ahora - fila.usada > timedelta(minutes=1):
        ClaveApi.objects.filter(pk=fila.pk).update(usada=ahora)
    return fila.usuario


def _error(motivo, mensaje, estado):
    return JsonResponse({'ok': False, 'error': motivo, 'msg': mensaje}, status=estado)


def con_clave(vista):
    @wraps(vista)
    def envoltorio(request, *args, **kwargs):
        usuario = _usuario(request)
        if usuario is None:
            return _error('clave', 'La clave no es válida o fue revocada. Crea otra en Perfil.', 401)
        usados, _ = sumar(f'api:{usuario.pk}', 3600)
        if usados > TOPE_HORA:
            return _error('tope', 'Anotaste muchas cosas seguidas. Espera un rato.', 429)
        return vista(request, usuario, *args, **kwargs)
    return csrf_exempt(envoltorio)


def _datos(request):
    if (request.content_type or '').startswith('application/json'):
        try:
            datos = json.loads(request.body or b'{}')
        except ValueError:
            return None
        return datos if isinstance(datos, dict) else None
    return request.POST.dict()


def _leer(datos):
    tipo = str(datos.get('tipo') or '').upper() or None
    if datos.get('texto'):
        leido = interpretar(str(datos['texto']), tipo)
    else:
        try:
            monto = Decimal(str(datos.get('monto', '')).replace(',', '.'))
        except InvalidOperation:
            monto = None
        descripcion = ' '.join(str(datos.get('descripcion') or '').split())[:200]
        tipo = tipo if tipo in ('INGRESO', 'EGRESO') else 'EGRESO'
        leido = interpretar(descripcion, tipo)
        leido['monto'] = monto if monto is not None and 0 < monto <= MAX_MONTO else None
        leido['claro'] = leido['monto'] is not None
        leido['descripcion'] = descripcion[:1].upper() + descripcion[1:]
    if datos.get('categoria'):
        leido['categoria'] = str(datos['categoria'])
    if datos.get('fecha'):
        try:
            leido['fecha'] = date.fromisoformat(str(datos['fecha'])[:10])
        except ValueError:
            pass
    return leido


@require_http_methods(['POST'])
@con_clave
def movimientos(request, usuario):
    datos = _datos(request)
    if datos is None:
        return _error('formato', 'No pude leer lo que mandaste.', 400)
    leido = _leer(datos)
    if not leido['claro']:
        return _error('monto', 'No encontré el monto. Prueba con «5.000 café» o «5 lucas en café».', 400)
    if abs((leido['fecha'] - fechas.hoy()).days) > 31:
        return _error('fecha', 'La fecha tiene que estar dentro del último mes.', 400)

    opciones = dict(Categoria.opciones_por_tipo(usuario)[leido['tipo']])
    categoria = leido['categoria']
    if categoria not in opciones and categoria not in SLUGS_BASE:
        categoria = 'Otros_Ingresos' if leido['tipo'] == 'INGRESO' else 'Otros'

    tx = Transaccion.objects.create(
        usuario=usuario, tipo=leido['tipo'], monto=leido['monto'], categoria=categoria,
        fecha=leido['fecha'], descripcion=leido['descripcion'], origen=Transaccion.API,
        pagado=True, fecha_pago=leido['fecha'],
    )
    nombre = opciones.get(categoria, categoria.replace('_', ' '))
    monto = money(tx.monto, simbolo_de(usuario))
    return JsonResponse({
        'ok': True, 'id': tx.pk, 'tipo': tx.tipo, 'monto': str(tx.monto), 'monto_texto': monto,
        'categoria': categoria, 'categoria_nombre': nombre, 'descripcion': tx.descripcion,
        'fecha': tx.fecha.isoformat(), 'texto': f'Anotado: {monto} en {nombre}',
    }, status=201)


@require_http_methods(['DELETE'])
@con_clave
def movimiento(request, usuario, transaccion_id):
    tx = Transaccion.objects.filter(pk=transaccion_id, usuario=usuario, origen=Transaccion.API,
                                    fecha__gte=fechas.hoy() - timedelta(days=1)).first()
    if tx is None:
        return _error('no_existe', 'Ese movimiento ya no se puede deshacer desde aquí.', 404)
    tx.delete()
    return JsonResponse({'ok': True, 'texto': 'Listo, lo borré.'})
