from decimal import Decimal
from datetime import date

from dateutil.relativedelta import relativedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Deuda(models.Model):
    CATEGORIAS_CUOTAS = (
        ('Tecnologia', 'Tecnología y electrónica'),
        ('Compras', 'Compras online'),
        ('Ropa', 'Ropa y calzado'),
        ('Hogar', 'Hogar y muebles'),
        ('Ocio', 'Entretenimiento'),
        ('Viajes', 'Viajes y pasajes'),
        ('Educacion', 'Educación y cursos'),
        ('Salud', 'Salud y Farmacia'),
        ('Transporte', 'Transporte'),
        ('Otros', 'Otra cosa'),
    )

    CATEGORIAS_EGRESO = CATEGORIAS_CUOTAS
    CATEGORIAS = CATEGORIAS_CUOTAS

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    acreedor = models.CharField(max_length=100)
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS_CUOTAS,
                                 default='Tecnologia')
    cuotas_totales = models.IntegerField(default=12)
    cuotas_pagadas = models.IntegerField(default=0)
    fecha_inicio = models.DateField(default=timezone.now, help_text="Fecha del primer pago")

    class Meta:
        ordering = ['fecha_inicio', 'id']

    def __str__(self):
        return self.acreedor

    @property
    def fecha_fin_estimada(self):
        return self.fecha_inicio + relativedelta(months=self.cuotas_totales - 1)

    @property
    def proximo_vencimiento(self):
        p = self.periodo_a_pagar
        return self.fecha_cobro_de(p) if p else None

    @property
    def dia_pago(self):
        return self.fecha_inicio.day

    @property
    def dias_para_vencer(self):
        if self.cuotas_pagadas >= self.cuotas_totales:
            return None
        fecha_evaluar = self.proximo_vencimiento or self.fecha_inicio
        if fecha_evaluar:
            return (fecha_evaluar - date.today()).days
        return None

    @property
    def urgencia(self):
        if self.esta_saldada:
            return 'saldada'
        if self.periodos_atrasados:
            return 'vencida'
        d = self.dias_para_vencer
        if d is None:
            return 'normal'
        if d <= 3:
            return 'critica'
        if d <= 7:
            return 'proxima'
        return 'normal'

    @property
    def texto_urgencia(self):
        if self.esta_saldada:
            return 'Saldada'
        atrasados = self.periodos_atrasados
        if atrasados:
            n = len(atrasados)
            if n == 1:
                dias = (date.today() - self.fecha_cobro_de(atrasados[0])).days
                return f'Atrasada {dias} día{"s" if dias != 1 else ""}'
            return f'{n} cuotas atrasadas'
        d = self.dias_para_vencer
        if d is None:
            return f'Vence el {self.dia_pago}'
        if d == 0:
            return 'Vence hoy'
        return f'Vence el {self.dia_pago} · en {d} día{"s" if d != 1 else ""}'

    @staticmethod
    def periodo_de(year, month):
        return year * 100 + month

    @property
    def periodos_programados(self):
        salida = []
        for i in range(self.cuotas_totales):
            f = self.fecha_inicio + relativedelta(months=i)
            salida.append(self.periodo_de(f.year, f.month))
        return salida

    def fecha_cobro_de(self, periodo):
        import calendar as _cal
        year, month = periodo // 100, periodo % 100
        _, ultimo = _cal.monthrange(year, month)
        return date(year, month, min(self.fecha_inicio.day, ultimo))

    @property
    def periodos_pagados(self):
        return {p.periodo for p in self.pagos.all()}

    def esta_pagada_en(self, periodo):
        return periodo in self.periodos_pagados

    @property
    def periodos_pendientes(self):
        pagados = self.periodos_pagados
        return [p for p in self.periodos_programados if p not in pagados]

    @property
    def periodo_a_pagar(self):
        pendientes = self.periodos_pendientes
        return pendientes[0] if pendientes else None

    @property
    def periodos_atrasados(self):
        hoy = date.today()
        return [p for p in self.periodos_pendientes if self.fecha_cobro_de(p) < hoy]

    @property
    def monto_atrasado(self):
        return self.monto_cuota * len(self.periodos_atrasados)

    @property
    def texto_a_pagar(self):
        p = self.periodo_a_pagar
        if p is None:
            return 'Sin cuotas pendientes'
        nombres = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
                   'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        year, month = p // 100, p % 100
        etiqueta = f'{nombres[month - 1]} {year}'
        atrasados = len(self.periodos_atrasados)
        if atrasados > 1:
            return f'Pagar {etiqueta} · {atrasados} cuotas atrasadas'
        if atrasados == 1:
            return f'Pagar {etiqueta} · atrasada'
        return f'Pagar cuota de {etiqueta}'

    @property
    def esta_saldada(self):
        return self.cuotas_pagadas >= self.cuotas_totales

    @property
    def cuotas_restantes(self):
        return max(0, self.cuotas_totales - self.cuotas_pagadas)

    @property
    def cuota_actual(self):
        if self.esta_saldada:
            return None
        return self.cuotas_pagadas + 1

    @property
    def rango_cuotas(self):
        pagados = self.periodos_pagados
        siguiente = self.periodo_a_pagar
        hoy_p = self.periodo_de(date.today().year, date.today().month)
        marcas = []
        for i, p in enumerate(self.periodos_programados[:36]):
            if p in pagados:
                estado = 'paid'
            elif p == siguiente:
                estado = 'next'
            elif p < hoy_p:
                estado = 'late'
            else:
                estado = ''
            marcas.append({'indice': i + 1, 'periodo': p, 'clase': estado})
        return marcas

    @property
    def porcentaje(self):
        if self.cuotas_totales == 0:
            return 0
        return int((self.cuotas_pagadas / self.cuotas_totales) * 100)

    @property
    def monto_cuota(self):
        if self.cuotas_totales > 0:
            return (self.monto_total / self.cuotas_totales).quantize(Decimal('1'))
        return Decimal('0')

    def monto_cuota_de(self, periodo):
        programados = self.periodos_programados
        if programados and periodo == programados[-1]:
            return self.monto_total - self.monto_cuota * (self.cuotas_totales - 1)
        return self.monto_cuota

    @property
    def monto_pagado(self):
        return sum((p.monto for p in self.pagos.all()), Decimal('0'))

    @property
    def monto_restante(self):
        return self.monto_total - self.monto_pagado

class PagoCuota(models.Model):
    deuda = models.ForeignKey('Deuda', on_delete=models.CASCADE, related_name='pagos')
    periodo = models.IntegerField(db_index=True, help_text='Mes al que corresponde: año*100+mes')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_pago = models.DateField(default=timezone.now, help_text='Cuándo se pagó de verdad')
    transaccion = models.OneToOneField('Transaccion', on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='pago_cuota')

    class Meta:
        ordering = ['-periodo']
        constraints = [
            models.UniqueConstraint(fields=['deuda', 'periodo'], name='pago_unico_por_mes'),
        ]

    def __str__(self):
        return f'{self.deuda.acreedor} — {self.periodo}'

    @property
    def year(self):
        return self.periodo // 100

    @property
    def month(self):
        return self.periodo % 100

    @property
    def etiqueta_mes(self):
        nombres = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
                   'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        return f'{nombres[self.month - 1]} {self.year}'

    @property
    def fue_atrasado(self):
        return self.fecha_pago > self.deuda.fecha_cobro_de(self.periodo)
