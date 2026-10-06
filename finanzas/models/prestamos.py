import calendar
import re
from datetime import date
from decimal import Decimal
from urllib.parse import quote

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

CERO = Decimal('0')


def _d(valor):
    return valor if isinstance(valor, Decimal) else Decimal(str(valor or 0))


def _pesos(valor):
    return '$' + f'{int(round(_d(valor))):,}'.replace(',', '.')


def normalizar_telefono(texto):
    texto = (texto or '').strip()
    if not texto or not re.fullmatch(r'[\d\s+\-().]+', texto):
        return None
    digitos = re.sub(r'\D', '', texto)
    if digitos.startswith('00'):
        digitos = digitos[2:]
    if len(digitos) == 9 and digitos.startswith('9'):
        digitos = '56' + digitos
    elif len(digitos) == 8:
        digitos = '569' + digitos
    return digitos if 10 <= len(digitos) <= 15 else None


class Persona(models.Model):
    LADOS = [
        ('ME_DEBE', 'Me debe'),
        ('LE_DEBO', 'Le debo'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='personas')
    lado = models.CharField(max_length=8, choices=LADOS, default='ME_DEBE', db_index=True)
    nombre = models.CharField(max_length=80)
    contacto = models.CharField(max_length=80, blank=True, help_text='Teléfono, email o nota (opcional)')
    creada = models.DateField(default=timezone.now)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    @property
    def le_debo(self):
        return self.lado == 'LE_DEBO'

    @property
    def inicial(self):
        return (self.nombre or '?')[0].upper()

    @property
    def total_prestado(self):
        return sum((_d(p.monto) for p in self.prestamos.all()), CERO)

    @property
    def total_abonado(self):
        return sum((p.total_abonado for p in self.prestamos.all()), CERO)

    @property
    def total_pendiente(self):
        return self.total_prestado - self.total_abonado

    @property
    def tiene_deuda(self):
        return self.total_pendiente > 0

    @property
    def cantidad_prestamos(self):
        return len(self.prestamos.all())

    @property
    def prestamos_activos(self):
        return [p for p in self.prestamos.all() if not p.esta_pagado]

    @property
    def cuotas_del_mes(self):
        return sum((p.monto_cuota for p in self.prestamos.all()
                    if p.tipo == 'CUOTAS' and not p.esta_pagado), CERO)

    @property
    def unicos_pendientes(self):
        return sum((p.monto_pendiente for p in self.prestamos.all()
                    if p.tipo == 'UNICO' and not p.esta_pagado), CERO)

    @property
    def cobro_del_mes(self):
        return self.cuotas_del_mes + self.unicos_pendientes

    @property
    def telefono_whatsapp(self):
        return normalizar_telefono(self.contacto)

    @property
    def mensaje_whatsapp(self):
        lineas = [f'Hola {self.nombre}, te escribo para recordarte lo que tienes pendiente conmigo:', '']
        for p in self.prestamos_activos:
            linea = f'- {p.descripcion}: {_pesos(p.monto_pendiente)}'
            if p.tipo == 'CUOTAS':
                linea += f' (cuota de {_pesos(p.monto_cuota)}, van {p.cuotas_abonadas} de {p.cuotas_totales})'
            lineas.append(linea)
        lineas += ['', f'Total pendiente: {_pesos(self.total_pendiente)}']
        if self.cuotas_del_mes and self.cobro_del_mes != self.total_pendiente:
            lineas.append(f'Para este mes: {_pesos(self.cobro_del_mes)}')
        lineas += ['', 'Gracias.']
        return '\n'.join(lineas)

    @property
    def enlace_whatsapp(self):
        telefono = self.telefono_whatsapp
        if self.le_debo or not telefono or not self.tiene_deuda:
            return ''
        return f'https://wa.me/{telefono}?text={quote(self.mensaje_whatsapp)}'

    @property
    def resumen_meta(self):
        n = self.cantidad_prestamos
        if n == 0:
            return 'Sin préstamos'
        return f'{n} préstamo{"s" if n != 1 else ""}'

class Prestamo(models.Model):
    TIPO_CHOICES = [
        ('UNICO', 'Pago único'),
        ('CUOTAS', 'En cuotas'),
    ]

    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name='prestamos')
    descripcion = models.CharField(max_length=120)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='UNICO')
    cuotas_totales = models.IntegerField(default=1)
    fecha = models.DateField(default=timezone.now)

    class Meta:
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f"{self.descripcion} — {self.persona.nombre}"

    @property
    def total_abonado(self):
        return sum((_d(a.monto) for a in self.abonos.all()), CERO)

    @property
    def monto_pendiente(self):
        return _d(self.monto) - self.total_abonado

    @property
    def porcentaje(self):
        monto = _d(self.monto)
        if monto <= 0:
            return 100
        return min(100, round(self.total_abonado / monto * 100))

    @property
    def esta_pagado(self):
        return self.monto_pendiente <= 0

    @property
    def es_en_cuotas(self):
        return self.tipo == 'CUOTAS'

    @property
    def monto_cuota(self):
        monto = _d(self.monto)
        if self.tipo == 'CUOTAS' and self.cuotas_totales > 0:
            return (monto / self.cuotas_totales).quantize(Decimal('1'))
        return monto

    @property
    def cuotas_abonadas(self):
        if self.tipo == 'CUOTAS' and self.monto_cuota > 0:
            if self.esta_pagado:
                return self.cuotas_totales
            return min(self.cuotas_totales, int(self.total_abonado / self.monto_cuota))
        return 1 if self.esta_pagado else 0

    @property
    def cuotas_pendientes(self):
        if self.tipo != 'CUOTAS':
            return 0
        return max(0, self.cuotas_totales - self.cuotas_abonadas)

    @property
    def detalle_plan(self):
        if self.tipo == 'CUOTAS':
            cuota = int(self.monto_cuota)
            return (f'Cuota de ${cuota:,}'.replace(',', '.')
                    + f' · {self.cuotas_abonadas} de {self.cuotas_totales} abonadas')
        if self.esta_pagado:
            return 'Devuelto completo'
        return 'Sin plazo definido'

    def abonado_en(self, year, month):
        return sum((_d(a.monto) for a in self.abonos.all()
                    if a.fecha.year == year and a.fecha.month == month), CERO)

    def compromiso_del_mes(self, year, month):
        abonado = self.abonado_en(year, month)
        if self.tipo == 'CUOTAS':
            return max(abonado, min(self.monto_cuota, abonado + self.monto_pendiente))
        return abonado + max(CERO, self.monto_pendiente)

    def falta_este_mes(self, year, month):
        return max(CERO, self.compromiso_del_mes(year, month) - self.abonado_en(year, month))

    def dia_de_pago(self, year, month):
        ultimo = calendar.monthrange(year, month)[1]
        if self.tipo != 'CUOTAS':
            return date(year, month, ultimo)
        return date(year, month, min(self.fecha.day, ultimo))

    @property
    def montos_sugeridos(self):
        if self.esta_pagado:
            return []
        pendiente = self.monto_pendiente
        opciones = []
        if self.tipo == 'CUOTAS':
            cuota = self.monto_cuota
            opciones.append({'label': 'Una cuota', 'monto': round(min(cuota, pendiente))})
            if cuota * 2 < pendiente:
                opciones.append({'label': 'Dos cuotas', 'monto': round(cuota * 2)})
        else:
            opciones.append({'label': 'La mitad', 'monto': round(pendiente / 2)})
        opciones.append({'label': 'Todo lo pendiente', 'monto': round(pendiente)})
        return opciones

class AbonoPrestamo(models.Model):
    prestamo = models.ForeignKey(Prestamo, on_delete=models.CASCADE, related_name='abonos')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateField(default=timezone.now)
    nota = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f"Abono {self.monto} — {self.prestamo.descripcion}"
