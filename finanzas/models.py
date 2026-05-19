from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from datetime import date

class Transaccion(models.Model):
    TIPO_CHOICES = [
        ('INGRESO', 'Ingreso'),
        ('EGRESO', 'Egreso'),
    ]

    CATEGORIAS_EGRESO = (
        ('Comida', 'Comida y Supermercado'),
        ('Transporte', 'Transporte y Gasolina'),
        ('Servicios', 'Luz, Agua, Internet'),
        ('Ocio', 'Entretenimiento y Salidas'),
        ('Salud', 'Salud y Farmacia'),
        ('Otros', 'Otros Gastos'),
    )

    CATEGORIAS_INGRESO = (
        ('Sueldo', 'Sueldo o salario'),
        ('Freelance', 'Trabajo freelance'),
        ('Negocio', 'Negocio o emprendimiento'),
        ('Venta', 'Venta de algo'),
        ('Bono', 'Bono o aguinaldo'),
        ('Transferencia', 'Transferencia recibida'),
        ('Otros_Ingresos', 'Otros ingresos'),
    )

    CATEGORIAS = CATEGORIAS_EGRESO + CATEGORIAS_INGRESO

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default='Otros')
    fecha = models.DateField(default=timezone.now)
    descripcion = models.CharField(max_length=200, blank=True)
    es_cuota = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.tipo} - {self.monto}"

class Deuda(models.Model):
    CATEGORIAS_EGRESO = (
        ('Comida', 'Comida y Supermercado'),
        ('Transporte', 'Transporte y Gasolina'),
        ('Servicios', 'Luz, Agua, Internet'),
        ('Ocio', 'Entretenimiento y Salidas'),
        ('Salud', 'Salud y Farmacia'),
        ('Otros', 'Otros Gastos'),
    )

    CATEGORIAS_INGRESO = (
        ('Sueldo', 'Sueldo o salario'),
        ('Freelance', 'Trabajo freelance'),
        ('Negocio', 'Negocio o emprendimiento'),
        ('Venta', 'Venta de algo'),
        ('Bono', 'Bono o aguinaldo'),
        ('Transferencia', 'Transferencia recibida'),
        ('Otros_Ingresos', 'Otros ingresos'),
    )

    CATEGORIAS = CATEGORIAS_EGRESO + CATEGORIAS_INGRESO

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    acreedor = models.CharField(max_length=100)
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default='Otros')
    cuotas_totales = models.IntegerField(default=12)
    cuotas_pagadas = models.IntegerField(default=0)
    fecha_inicio = models.DateField(default=timezone.now, help_text="Fecha del primer pago")

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
        if self.cuotas_totales > 0:
            return self.monto_total / self.cuotas_totales
        return 0

    @property
    def monto_pagado(self):
        return self.monto_cuota * self.cuotas_pagadas

    @property
    def monto_restante(self):
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


class UserProfile(models.Model):
    MONEDAS = [
        ('CLP', 'Peso Chileno ($)'),
        ('USD', 'Dólar Americano (USD)'),
        ('EUR', 'Euro (EUR)'),
        ('ARS', 'Peso Argentino ($)'),
        ('MXN', 'Peso Mexicano ($)'),
        ('COP', 'Peso Colombiano ($)'),
        ('PEN', 'Sol Peruano (S/)'),
        ('BRL', 'Real Brasileño (R$)'),
    ]

    usuario               = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    onboarding_completado = models.BooleanField(default=False)
    paso_onboarding       = models.IntegerField(default=1)
    nombre_completo = models.CharField(max_length=100, blank=True)
    email           = models.EmailField(blank=True)
    telefono        = models.CharField(max_length=20, blank=True)
    pais            = models.CharField(max_length=60, blank=True)
    ciudad          = models.CharField(max_length=60, blank=True)
    moneda          = models.CharField(max_length=5, choices=MONEDAS, default='CLP')

    def __str__(self):
        return f"Perfil de {self.usuario.username}"

    @property
    def nombre_display(self):
        return self.nombre_completo or self.usuario.username

    @property
    def ubicacion(self):
        parts = [p for p in [self.ciudad, self.pais] if p]
        return ', '.join(parts) if parts else None
