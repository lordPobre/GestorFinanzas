from datetime import date

from dateutil.relativedelta import relativedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class MetaAhorro(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    monto_meta = models.DecimalField(max_digits=12, decimal_places=2)
    monto_actual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fecha_limite = models.DateField(null=True, blank=True, help_text="Fecha en que quieres lograr la meta (opcional)")

    def __str__(self):
        return self.nombre

    ICONOS_META = [
        ('emergencia', 'fa-shield-halved'),
        ('fondo', 'fa-piggy-bank'),
        ('ahorro', 'fa-piggy-bank'),
        ('viaje', 'fa-plane'),
        ('vacacion', 'fa-umbrella-beach'),
        ('auto', 'fa-car'),
        ('moto', 'fa-motorcycle'),
        ('bici', 'fa-bicycle'),
        ('casa', 'fa-house'),
        ('depart', 'fa-building'),
        ('arriendo', 'fa-key'),
        ('notebook', 'fa-laptop'),
        ('computad', 'fa-desktop'),
        ('pc', 'fa-desktop'),
        ('celular', 'fa-mobile-screen'),
        ('telefono', 'fa-mobile-screen'),
        ('iphone', 'fa-mobile-screen'),
        ('tv', 'fa-tv'),
        ('consola', 'fa-gamepad'),
        ('play', 'fa-gamepad'),
        ('estudio', 'fa-graduation-cap'),
        ('curso', 'fa-graduation-cap'),
        ('universidad', 'fa-graduation-cap'),
        ('matricula', 'fa-graduation-cap'),
        ('regalo', 'fa-gift'),
        ('navidad', 'fa-gift'),
        ('boda', 'fa-ring'),
        ('matrimonio', 'fa-ring'),
        ('salud', 'fa-kit-medical'),
        ('dentista', 'fa-tooth'),
        ('gym', 'fa-dumbbell'),
        ('gimnasio', 'fa-dumbbell'),
        ('mascota', 'fa-paw'),
        ('ropa', 'fa-shirt'),
        ('mueble', 'fa-couch'),
        ('negocio', 'fa-store'),
        ('inversion', 'fa-chart-line'),
        ('deuda', 'fa-credit-card'),
    ]

    COLORES_META = ['#4b8cff', '#f4626c', '#ffd54f', '#53d258',
                    '#818cf8', '#2fd8c8', '#c084fc', '#fb923c']

    @property
    def icono(self):
        nombre = (self.nombre or '').lower()
        for clave, ic in self.ICONOS_META:
            if clave in nombre:
                return ic
        return 'fa-bullseye'

    @property
    def color(self):
        return self.COLORES_META[(self.pk or 0) % len(self.COLORES_META)]

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

    @property
    def esta_completa(self):
        return self.monto_actual >= self.monto_meta

    @property
    def dias_restantes(self):
        if not self.fecha_limite:
            return None
        return (self.fecha_limite - date.today()).days

    @property
    def nota_plan(self):
        if self.esta_completa:
            return 'Meta cumplida.'
        sugerido = self.ahorro_mensual_sugerido
        if sugerido:
            meses = max(1, round(float(self.monto_faltante) / sugerido))
            return f'Aportando ${int(sugerido):,}'.replace(',', '.') + f' al mes lo logras en {meses} meses.'
        return f'Te faltan ${int(self.monto_faltante):,}'.replace(',', '.') + ' para llegar.'

class AporteMeta(models.Model):
    meta = models.ForeignKey(MetaAhorro, on_delete=models.CASCADE, related_name='aportes')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateField(default=timezone.now)
    nota = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f"Aporte {self.monto} a {self.meta.nombre}"
