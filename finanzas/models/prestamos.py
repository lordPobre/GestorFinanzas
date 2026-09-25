from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


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
        return sum(float(p.monto) for p in self.prestamos.all())

    @property
    def total_abonado(self):
        return sum(float(p.total_abonado) for p in self.prestamos.all())

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
        total = 0.0
        for p in self.prestamos.all():
            if p.tipo == 'CUOTAS' and not p.esta_pagado:
                total += float(p.monto_cuota)
        return total

    @property
    def unicos_pendientes(self):
        total = 0.0
        for p in self.prestamos.all():
            if p.tipo == 'UNICO' and not p.esta_pagado:
                total += float(p.monto_pendiente)
        return total

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
        return sum(float(a.monto) for a in self.abonos.all())

    @property
    def monto_pendiente(self):
        return float(self.monto) - self.total_abonado

    @property
    def porcentaje(self):
        if float(self.monto) <= 0:
            return 100
        return min(100, round((self.total_abonado / float(self.monto)) * 100))

    @property
    def esta_pagado(self):
        return self.monto_pendiente <= 0

    @property
    def es_en_cuotas(self):
        return self.tipo == 'CUOTAS'

    @property
    def monto_cuota(self):
        if self.tipo == 'CUOTAS' and self.cuotas_totales > 0:
            return float(self.monto) / self.cuotas_totales
        return float(self.monto)

    @property
    def cuotas_abonadas(self):
        if self.tipo == 'CUOTAS' and self.monto_cuota > 0:
            return int(self.total_abonado / self.monto_cuota)
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
