from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from dateutil.relativedelta import relativedelta 
from datetime import date

# --- MODELO CATEGORIA ---
class Categoria(models.Model):
    nombre = models.CharField(max_length=50)
    icono = models.CharField(max_length=50, default='fa-tag')
    
    def __str__(self):
        return self.nombre

# --- MODELO TRANSACCION ---
class Transaccion(models.Model):
    TIPO_CHOICES = [
        ('INGRESO', 'Ingreso'),
        ('EGRESO', 'Egreso'),
    ]
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateField(default=timezone.now)
    descripcion = models.CharField(max_length=200, blank=True)

    CATEGORIAS = (
        ('Comida', 'Comida y Supermercado'),
        ('Transporte', 'Transporte y Gasolina'),
        ('Servicios', 'Luz, Agua, Internet'),
        ('Ocio', 'Entretenimiento y Salidas'),
        ('Salud', 'Salud y Farmacia'),
        ('Otros', 'Otros Gastos'),
    )
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default='Otros')

    def __str__(self):
        return f"{self.tipo} - {self.monto}"

# --- MODELO DEUDA ---
class Deuda(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    acreedor = models.CharField(max_length=100)
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Control de Cuotas
    cuotas_totales = models.IntegerField(default=12)
    cuotas_pagadas = models.IntegerField(default=0)
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2, default=0) # Agregado para evitar error en views
    
    # Fechas
    fecha_inicio = models.DateField(default=timezone.now, help_text="Fecha del primer pago")

    CATEGORIAS = (
        ('Comida', 'Comida y Supermercado'),
        ('Transporte', 'Transporte y Gasolina'),
        ('Servicios', 'Luz, Agua, Internet'),
        ('Ocio', 'Entretenimiento y Salidas'),
        ('Salud', 'Salud y Farmacia'),
        ('Otros', 'Otros Gastos'),
    )
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default='Otros')
    
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
        if self.cuotas_totales == 0: return 0
        return int((self.cuotas_pagadas / self.cuotas_totales) * 100)
    
    def __str__(self):
        return self.acreedor
    
    @property
    def monto_restante(self):
        """Calcula cuánto dinero falta por pagar"""
        return self.monto_total - self.monto_pagado
    
    @property
    def monto_cuota(self):
        """Calcula el valor de una sola cuota"""
        if self.cuotas_totales > 0:
            return self.monto_total / self.cuotas_totales
        return 0
    
    @property
    def dias_para_vencer(self):
        fecha_evaluar = self.proximo_vencimiento or self.fecha_inicio
        if fecha_evaluar:
            delta = fecha_evaluar - date.today()
            return delta.days
        return 999

class Presupuesto(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    limite_mensual = models.DecimalField(max_digits=12, decimal_places=2, default=500000) # Por defecto 500k

    def __str__(self):
        return f"Presupuesto de {self.usuario.username}: ${self.limite_mensual}"

class MetaAhorro(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100) # Ej: Viaje a la playa, PC Gamer...
    monto_meta = models.DecimalField(max_digits=12, decimal_places=2)
    monto_actual = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    @property
    def porcentaje(self):
        if self.monto_meta > 0:
            return min((self.monto_actual / self.monto_meta) * 100, 100)
        return 0

    def __str__(self):
        return self.nombre