import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
         'octubre', 'noviembre', 'diciembre')


def periodo_de(fecha):
    return fecha.year * 100 + fecha.month


def nombre_periodo(periodo):
    return MESES[periodo % 100 - 1]


def sumar_meses(periodo, cuantos):
    total = (periodo // 100) * 12 + (periodo % 100 - 1) + cuantos
    return (total // 12) * 100 + total % 12 + 1


class IngresoFijo(models.Model):
    ULTIMO_HABIL = 0

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ingreso_fijo')
    nombre = models.CharField(max_length=80, blank=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    dia_pago = models.PositiveSmallIntegerField(default=30)
    inicio = models.IntegerField()
    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Sueldo de {self.usuario_id}: {self.monto}'

    @property
    def titulo(self):
        return f'Tu sueldo · {self.nombre}' if self.nombre else 'Tu sueldo'

    @property
    def descripcion(self):
        return f'Sueldo · {self.nombre}' if self.nombre else 'Sueldo'

    @property
    def texto_dia(self):
        if self.dia_pago == self.ULTIMO_HABIL:
            return 'el último día hábil'
        return f'el {self.dia_pago}'

    @property
    def paga_tarde(self):
        return self.dia_pago == self.ULTIMO_HABIL or self.dia_pago >= 25

    @property
    def paga_temprano(self):
        return 1 <= self.dia_pago <= 5

    def fecha_pago(self, periodo):
        year, month = divmod(periodo, 100)
        ultimo = calendar.monthrange(year, month)[1]
        if self.dia_pago == self.ULTIMO_HABIL:
            dia = date(year, month, ultimo)
            while dia.weekday() >= 5:
                dia -= timedelta(days=1)
            return dia
        return date(year, month, min(self.dia_pago, ultimo))


class IngresoMes(models.Model):
    ingreso = models.ForeignKey(IngresoFijo, on_delete=models.CASCADE, related_name='meses')
    periodo = models.IntegerField()
    monto = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    extra = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    nota = models.CharField(max_length=80, blank=True)
    recibido = models.DateField(null=True, blank=True)
    monto_recibido = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    por_cartola = models.BooleanField(default=False)
    anotado_aqui = models.BooleanField(default=False)
    transaccion = models.OneToOneField('Transaccion', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='ingreso_mes')

    class Meta:
        ordering = ['periodo']
        constraints = [
            models.UniqueConstraint(fields=['ingreso', 'periodo'], name='ingreso_mes_unico'),
        ]

    def __str__(self):
        return f'{self.ingreso_id} · {self.periodo}'

    @property
    def llego(self):
        return self.recibido is not None and self.transaccion_id is not None
