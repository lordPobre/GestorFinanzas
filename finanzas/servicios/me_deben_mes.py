from decimal import Decimal

from ..templatetags.moneda import money
from .mes import MESES_LARGOS

CERO = Decimal('0')
UNO = Decimal('1')
ATRAS = 6
ADELANTE = 6
CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
ICONOS = {'pago': 'fa-arrow-down', 'falta': 'fa-clock', 'presto': 'fa-arrow-up', 'proy': 'fa-calendar'}


def _d(valor):
    return valor if isinstance(valor, Decimal) else Decimal(str(valor or 0))


def indice(fecha):
    return fecha.year * 12 + fecha.month - 1


def _largo(i):
    return f'{MESES_LARGOS[i % 12]} {i // 12}'


def _corto(i):
    return f'{CORTOS[i % 12]} {i // 12}'


def _suma(valores):
    return sum(valores, CERO)


class Plan:

    def __init__(self, prestamo, persona):
        self.prestamo = prestamo
        self.persona = persona
        self.inicio = indice(prestamo.fecha)
        self.monto = _d(prestamo.monto)
        en_cuotas = prestamo.tipo == 'CUOTAS' and prestamo.cuotas_totales > 0
        self.cuotas = prestamo.cuotas_totales if en_cuotas else 0
        self.cuota = prestamo.monto_cuota if en_cuotas else CERO
        self.abonos = [(indice(a.fecha), _d(a.monto)) for a in prestamo.abonos.all()]
        self.filas = {}

    def vence_hasta(self, i):
        if not self.cuotas:
            return CERO
        k = min(max(i - self.inicio + 1, 0), self.cuotas)
        return self.monto if k == self.cuotas else min(self.monto, self.cuota * k)

    def vence_en(self, i):
        return self.vence_hasta(i) - self.vence_hasta(i - 1)

    def pagado_hasta(self, i):
        return _suma(m for j, m in self.abonos if j <= i)

    def pagado_en(self, i):
        return _suma(m for j, m in self.abonos if j == i)

    def pendiente_en(self, i):
        return max(CERO, self.monto - self.pagado_hasta(i))

    def atraso_en(self, hoy):
        return min(self.pendiente_en(hoy), max(CERO, self.vence_hasta(hoy - 1) - self.pagado_hasta(hoy)))


def _ritmo(planes, hoy):
    total = bien = 0
    for p in planes:
        for i in range(p.inicio, min(hoy, p.inicio + p.cuotas)):
            total += 1
            if p.pagado_hasta(i) >= p.vence_hasta(i) - UNO:
                bien += 1
    return total, bien


def _proyectar(plan, hoy, hasta, factor):
    pend = plan.pendiente_en(hoy)
    filas = {}
    if not plan.cuotas:
        for i in range(hoy, hasta + 1):
            filas[i] = {'pago': CERO, 'disp': CERO, 'atrasado': CERO, 'despues': pend}
        return filas
    arr = plan.atraso_en(hoy)
    for i in range(hoy, hasta + 1):
        if i == hoy:
            disp = min(pend, max(CERO, plan.vence_hasta(hoy) - plan.pagado_hasta(hoy)))
        else:
            disp = min(pend, arr + plan.vence_en(i))
        atrasado = min(arr, disp)
        pago = disp * factor
        pend -= pago
        filas[i] = {'pago': pago, 'disp': disp, 'atrasado': atrasado, 'despues': pend}
        arr = disp - pago
    return filas


def _que_pago(p, i):
    pagado = p.pagado_hasta(i)
    if not p.cuotas:
        return 'pagó todo' if pagado >= p.monto - UNO else 'abono'
    if pagado >= p.monto - UNO:
        n = p.cuotas
    else:
        n = min(p.cuotas, int((pagado + UNO) / p.cuota)) if p.cuota > 0 else 0
    if n == 0:
        return 'abono'
    texto = f'cuota {n} de {p.cuotas}'
    return f'{texto} con atraso' if p.inicio + n - 1 < i else texto


def _que_vence(p, i, fila, dinero):
    k = i - p.inicio + 1
    if not p.cuotas:
        return 'pago único'
    if k < 1 or k > p.cuotas:
        return 'lo que quedó atrasado'
    texto = f'cuota {k} de {p.cuotas}'
    if fila['atrasado'] >= UNO:
        texto += f' + {dinero(fila["atrasado"])} atrasado'
    return texto


def _eventos(i, hoy, planes, dinero):
    filas = []

    def agregar(tipo, p, detalle, monto, tag):
        filas.append({'tipo': tipo, 'icono': ICONOS[tipo], 'nombre': p.persona.nombre,
                      'detalle': f'{p.prestamo.descripcion} · {detalle}', 'monto': dinero(monto),
                      'tag': tag, 'orden': float(monto)})

    for p in planes:
        if i <= hoy:
            if p.inicio == i:
                plan = f'{p.cuotas} cuotas de {dinero(p.cuota)}' if p.cuotas else 'pago único'
                agregar('presto', p, plan, p.monto, 'Le prestaste')
            pagado = p.pagado_en(i)
            if pagado > 0:
                agregar('pago', p, _que_pago(p, i), pagado, 'Llegó')
            if i < hoy:
                falta = min(p.vence_en(i), p.vence_hasta(i) - p.pagado_hasta(i))
                if falta >= UNO:
                    agregar('falta', p, f'cuota {i - p.inicio + 1} de {p.cuotas}', falta, 'No llegó')
        if i >= hoy:
            fila = p.filas[i]
            if fila['disp'] >= UNO:
                if fila['pago'] < fila['disp'] - UNO:
                    tag = f'de {dinero(fila["disp"])}'
                else:
                    tag = 'Falta este mes' if i == hoy else 'Esperado'
                agregar('proy', p, _que_vence(p, i, fila, dinero), fila['pago'], tag)
    filas.sort(key=lambda f: f['orden'], reverse=True)
    for f in filas:
        del f['orden']
    return filas


def _mes(i, hoy, planes, dinero):
    activos = [p for p in planes if p.inicio <= i]
    if i < hoy:
        tipo = 'real'
        saldo = _suma(p.pendiente_en(i) for p in activos)
        real = _suma(p.pagado_en(i) for p in planes)
        proy = CERO
        esperado = _suma(p.vence_en(i) for p in planes)
    elif i == hoy:
        tipo = 'hoy'
        saldo = _suma(p.pendiente_en(i) for p in activos)
        real = _suma(p.pagado_en(i) for p in planes)
        proy = _suma(p.filas[i]['pago'] for p in planes)
        esperado = real + _suma(p.filas[i]['disp'] for p in planes)
    else:
        tipo = 'proy'
        saldo = _suma(p.filas[i]['despues'] for p in activos)
        real = CERO
        proy = _suma(p.filas[i]['pago'] for p in planes)
        esperado = _suma(p.filas[i]['disp'] for p in planes)
    return {
        'corto': CORTOS[i % 12],
        'largo': _largo(i).capitalize(),
        'tipo': tipo,
        'saldo': float(saldo),
        'real': float(real),
        'proy': float(proy),
        'esperado': float(esperado),
        'saldo_txt': dinero(saldo),
        'real_txt': dinero(real),
        'proy_txt': dinero(proy),
        'esperado_txt': dinero(esperado),
        'eventos': _eventos(i, hoy, planes, dinero),
    }


def _resumen(hoy, hasta, planes, dinero, clave, n_personas):
    saldo = _suma(p.pendiente_en(hoy) for p in planes if p.inicio <= hoy)
    atraso = _suma(p.atraso_en(hoy) for p in planes)
    falta_mes = _suma(p.filas[hoy]['disp'] for p in planes)
    pago_mes = _suma(p.filas[hoy]['pago'] for p in planes)
    sin_fecha = _suma(p.pendiente_en(hoy) for p in planes if not p.cuotas)
    en_cuotas = [p for p in planes if p.cuotas]
    pendiente_cuotas = _suma(p.pendiente_en(hoy) for p in en_cuotas)

    hoy_sub = f'{n_personas} persona{"s" if n_personas != 1 else ""}'
    if atraso >= UNO:
        hoy_sub += f' · {dinero(atraso)} atrasado'

    if falta_mes < UNO:
        mes_sub = 'Ya llegó todo lo de este mes'
    elif clave == 'ritmo':
        mes_sub = f'De {dinero(falta_mes)} que vence'
    else:
        mes_sub = f'Incluye {dinero(atraso)} atrasado' if atraso >= UNO else 'Las cuotas de este mes'

    if pendiente_cuotas < UNO:
        cero_valor = 'Sin cuotas'
        cero_sub = f'{dinero(sin_fecha)} sin fecha de pago' if sin_fecha >= UNO else 'Nadie te debe'
    else:
        cero = next((i for i in range(hoy, hasta + 1)
                     if _suma(p.filas[i]['despues'] for p in en_cuotas) < UNO), None)
        if cero is None:
            cero_valor = 'Más de 6 meses'
            resto = _suma(p.filas[hasta]['despues'] for p in en_cuotas)
            cero_sub = f'Quedarían {dinero(resto)} en {_corto(hasta)}'
        else:
            cero_valor = _corto(cero).capitalize()
            cero_sub = f'Sin contar {dinero(sin_fecha)} sin fecha' if sin_fecha >= UNO else 'Con todas las cuotas pagadas'

    return {
        'hoy_total': dinero(saldo),
        'hoy_sub': hoy_sub,
        'mes_etq': f'Falta cobrar en {MESES_LARGOS[hoy % 12]}',
        'mes_valor': dinero(pago_mes),
        'mes_sub': mes_sub,
        'cero_valor': cero_valor,
        'cero_sub': cero_sub,
    }


def _sin_fecha_txt(hoy, planes, personas, dinero):
    por_persona = []
    for persona in personas:
        monto = _suma(p.pendiente_en(hoy) for p in planes if p.persona.id == persona.id and not p.cuotas)
        if monto >= UNO:
            por_persona.append((persona.nombre, monto))
    if not por_persona:
        return ''
    total = _suma(m for _, m in por_persona)
    if len(por_persona) == 1:
        return f'{por_persona[0][0]} te debe {dinero(total)} sin fecha de pago. No entra en la proyección.'
    nombres = [n for n, _ in por_persona]
    lista = ', '.join(nombres[:-1]) + f' y {nombres[-1]}'
    return f'{lista} te deben {dinero(total)} sin fecha de pago. No entra en la proyección.'


def por_mes(personas, hoy_fecha, simbolo='$'):
    personas = list(personas)
    planes = [Plan(p, persona) for persona in personas for p in persona.prestamos.all()]
    if not planes:
        return None

    def dinero(valor):
        return money(_d(valor), simbolo)

    hoy = indice(hoy_fecha)
    desde, hasta = hoy - ATRAS, hoy + ADELANTE
    ritmos = {persona.id: _ritmo([p for p in planes if p.persona.id == persona.id], hoy)
              for persona in personas}
    n_personas = len({p.persona.id for p in planes if p.pendiente_en(hoy) >= UNO})

    escenarios = {}
    for clave in ('aldia', 'ritmo'):
        for p in planes:
            vencidas, a_tiempo = ritmos[p.persona.id]
            factor = UNO if clave == 'aldia' or not vencidas else Decimal(a_tiempo) / Decimal(vencidas)
            p.filas = _proyectar(p, hoy, hasta, factor)
        escenarios[clave] = {
            'meses': [_mes(i, hoy, planes, dinero) for i in range(desde, hasta + 1)],
            'resumen': _resumen(hoy, hasta, planes, dinero, clave, n_personas),
        }

    return {
        'hoy': ATRAS,
        'sin_fecha_txt': _sin_fecha_txt(hoy, planes, personas, dinero),
        'escenarios': escenarios,
    }
