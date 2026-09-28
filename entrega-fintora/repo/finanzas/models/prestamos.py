from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

CERO = Decimal('0')


def _d(valor):
    return valor if isinstance(valor, Decimal) else Decimal(str(valor or 0))


class Persona(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='personas')
    nombre = models.CharField(max_length=80)
    contacto = models.CharField(max_length=80, blank=True, help_text='Teléfono, email o nota (opcional)')
    creada = models.DateField(default=timezone.now)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

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
