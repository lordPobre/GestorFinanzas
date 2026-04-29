from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from datetime import date

# --- MODELO TRANSACCION ---
class Transaccion(models.Model):
    TIPO_CHOICES = [
        ('INGRESO', 'Ingreso'),
        ('EGRESO', 'Egreso'),
    ]

    CATEGORIAS = (
        ('Comida', 'Comida y Supermercado'),
        ('Transporte', 'Transporte y Gasolina'),
        ('Servicios', 'Luz, Agua, Internet'),
        ('Ocio', 'Entretenimiento y Salidas'),
        ('Salud', 'Salud y Farmacia'),
        ('Otros', 'Otros Gastos'),
    )

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    # FIX: campo categoria duplicado eliminado — solo queda CharField
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default='Otros')
    fecha = models.DateField(default=timezone.now)
    descripcion = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.tipo} - {self.monto}"


# --- MODELO DEUDA ---
class Deuda(models.Model):
    CATEGORIAS = (
        ('Comida', 'Comida y Supermercado'),
        ('Transporte', 'Transporte y Gasolina'),
        ('Servicios', 'Luz, Agua, Internet'),
        ('Ocio', 'Entretenimiento y Salidas'),
        ('Salud', 'Salud y Farmacia'),
        ('Otros', 'Otros Gastos'),
    )

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    acreedor = models.CharField(max_length=100)
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default='Otros')

    # Control de Cuotas
    cuotas_totales = models.IntegerField(default=12)
    cuotas_pagadas = models.IntegerField(default=0)

    # Fechas
    fecha_inicio = models.DateField(default=timezone.now, help_text="Fecha del primer pago")

    # --- PROPIEDADES ---
    @property
    def fecha_fin_estimada(self):
        return self.fecha_inicio + relativedelta(months=self.cuotas_totales - 1)

    @property
    def proximo_vencimiento(self):
        if self.cuotas_pagadas >= self.cuotas_totales:
            return None
        return self.fecha_inicio + relativedelta(months=self.cuotas_pagadas)

    @property
    def porcentaje(self):
        if self.cuotas_totales == 0:
            return 0
        return int((self.cuotas_pagadas / self.cuotas_totales) * 100)

    @property
    def monto_cuota(self):
        """Calcula el valor de una sola cuota"""
        if self.cuotas_totales > 0:
            return self.monto_total / self.cuotas_totales
        return 0

    @property
    def monto_pagado(self):
        # FIX: calculado desde cuotas_pagadas para evitar desincronizacion por redondeo
        return self.monto_cuota * self.cuotas_pagadas

    @property
    def monto_restante(self):
        """Calcula cuanto dinero falta por pagar"""
        return self.monto_total - self.monto_pagado

    @property
    def dias_para_vencer(self):
        fecha_evaluar = self.proximo_vencimiento or self.fecha_inicio
        if fecha_evaluar:
            delta = fecha_evaluar - date.today()
            return delta.days
        return 999

    def __str__(self):
        return self.acreedor


class Presupuesto(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    limite_mensual = models.DecimalField(max_digits=12, decimal_places=2, default=500000)

    def __str__(self):
        return f"Presupuesto de {self.usuario.username}: ${self.limite_mensual}"


class MetaAhorro(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    monto_meta = models.DecimalField(max_digits=12, decimal_places=2)
    monto_actual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # NUEVO: fecha limite opcional para calcular cuanto ahorrar por mes
    fecha_limite = models.DateField(null=True, blank=True, help_text="Fecha en que quieres lograr la meta (opcional)")

    @property
    def porcentaje(self):
        if self.monto_meta > 0:
            return min((self.monto_actual / self.monto_meta) * 100, 100)
        return 0

    @property
    def monto_faltante(self):
        return max(self.monto_meta - self.monto_actual, 0)

    @property
    def ahorro_mensual_sugerido(self):
        """Calcula cuanto ahorrar por mes para llegar a la meta a tiempo"""
        if not self.fecha_limite or self.monto_faltante <= 0:
            return None
        hoy = date.today()
        if self.fecha_limite <= hoy:
            return None
        delta = relativedelta(self.fecha_limite, hoy)
        meses = delta.years * 12 + delta.months
        if meses <= 0:
            return None
        return round(float(self.monto_faltante) / meses, 0)

    def __str__(self):
        return self.nombre
