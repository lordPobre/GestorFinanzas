from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from dateutil.relativedelta import relativedelta 

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