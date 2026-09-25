from datetime import date

from dateutil.relativedelta import relativedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .movimientos import Transaccion


class Suscripcion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='suscripciones')
    nombre = models.CharField(max_length=100)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    categoria = models.CharField(max_length=50, blank=True, default='Suscripciones')
    dia_cobro = models.IntegerField(default=1, help_text='Día del mes en que se cobra (1-28)')
    activa = models.BooleanField(default=True)
    fecha_inicio = models.DateField(default=timezone.now)
    fecha_cancelada = models.DateField(null=True, blank=True)
    ultimo_mes_generado = models.IntegerField(default=0)

    class Meta:
        ordering = ['-activa', 'nombre']

    def __str__(self):
        return f"{self.nombre} — {self.monto}/mes"

    MARCAS = [
        ('netflix',      None,                  '#e50914'),
        ('spotify',      'fa-brands fa-spotify', '#1db954'),
        ('youtube',      'fa-brands fa-youtube', '#ff0000'),
        ('twitch',       'fa-brands fa-twitch',  '#9146ff'),
        ('disney',       None,                  '#1a3fd4'),
        ('star+',        None,                  '#1a3fd4'),
        ('hbo',          None,                  '#9b26f4'),
        ('max',          None,                  '#9b26f4'),
        ('prime',        'fa-brands fa-amazon',  '#ff9900'),
        ('amazon',       'fa-brands fa-amazon',  '#ff9900'),
        ('apple',        'fa-brands fa-apple',   '#f5f5f5'),
        ('icloud',       'fa-brands fa-apple',   '#f5f5f5'),
        ('itunes',       'fa-brands fa-apple',   '#f5f5f5'),
        ('google',       'fa-brands fa-google',  '#4285f4'),
        ('microsoft',    'fa-brands fa-microsoft', '#00a4ef'),
        ('office',       'fa-brands fa-microsoft', '#00a4ef'),
        ('xbox',         'fa-brands fa-xbox',    '#107c10'),
        ('playstation',  'fa-brands fa-playstation', '#0070d1'),
        ('steam',        'fa-brands fa-steam',   '#66c0f4'),
        ('discord',      'fa-brands fa-discord', '#5865f2'),
        ('dropbox',      'fa-brands fa-dropbox', '#0061ff'),
        ('figma',        'fa-brands fa-figma',   '#f24e1e'),
        ('deezer',       'fa-brands fa-deezer',  '#a238ff'),
        ('soundcloud',   'fa-brands fa-soundcloud', '#ff5500'),
        ('tidal',        None,                  '#00ffff'),
        ('crunchyroll',  None,                  '#f47521'),
        ('paramount',    None,                  '#0064ff'),
        ('canva',        None,                  '#00c4cc'),
        ('adobe',        None,                  '#ed2224'),
        ('chatgpt',      None,                  '#10a37f'),
        ('openai',       None,                  '#10a37f'),
        ('claude',       None,                  '#d97757'),
        ('notion',       None,                  '#f5f5f5'),
        ('duolingo',     None,                  '#58cc02'),
        ('gimnasio',     'fas fa-dumbbell',      '#53d258'),
        ('gym',          'fas fa-dumbbell',      '#53d258'),
        ('internet',     'fas fa-wifi',          '#4b8cff'),
        ('seguro',       'fas fa-shield-halved', '#4b8cff'),
    ]

    @property
    def marca(self):
        nombre = (self.nombre or "").lower()
        for clave, icono, color in self.MARCAS:
            if clave in nombre:
                return {
                    'icono': icono, 'color': color,
                    'usa_inicial': icono is None,
                    'reconocida': True,
                }
        return {
            'icono': 'fas fa-rotate', 'color': '#ffaa2c',
            'usa_inicial': False, 'reconocida': False,
        }

    @property
    def inicial(self):
        return (self.nombre or '?')[0].upper()

    @property
    def monto_anual(self):
        return float(self.monto) * 12

    @property
    def texto_cobro(self):
        if not self.activa:
            return 'Pausada'
        return f'Se cobra el {self.dia_cobro} de cada mes'

    @property
    def dias_para_cobro(self):
        if not self.activa:
            return None
        import calendar as _cal
        hoy = date.today()
        _, ultimo = _cal.monthrange(hoy.year, hoy.month)
        dia = min(self.dia_cobro, ultimo)
        if dia >= hoy.day:
            return dia - hoy.day
        siguiente = date(hoy.year, hoy.month, 1) + relativedelta(months=1)
        _, ultimo_sig = _cal.monthrange(siguiente.year, siguiente.month)
        objetivo = date(siguiente.year, siguiente.month, min(self.dia_cobro, ultimo_sig))
        return (objetivo - hoy).days

    @staticmethod
    def periodo_de(year, month):
        return year * 100 + month

    @property
    def periodos_programados(self):
        hoy = date.today()
        fin = self.fecha_cancelada or hoy
        salida = []
        cursor = date(self.fecha_inicio.year, self.fecha_inicio.month, 1)
        tope = self.periodo_de(min(fin, hoy).year, min(fin, hoy).month)
        while self.periodo_de(cursor.year, cursor.month) <= tope:
            salida.append(self.periodo_de(cursor.year, cursor.month))
            cursor = cursor + relativedelta(months=1)
        return salida

    def fecha_cobro_de(self, periodo):
        import calendar as _cal
        year, month = periodo // 100, periodo % 100
        _, ultimo = _cal.monthrange(year, month)
        return date(year, month, min(self.dia_cobro, ultimo))

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
        return self.monto * len(self.periodos_atrasados)

    @property
    def periodo_actual(self):
        hoy = date.today()
        return self.periodo_de(hoy.year, hoy.month)

    @property
    def pagada_este_mes(self):
        return self.esta_pagada_en(self.periodo_actual)

    @property
    def texto_a_pagar(self):
        p = self.periodo_a_pagar
        if p is None:
            return 'Al día'
        nombres = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
                   'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        etiqueta = f'{nombres[p % 100 - 1]} {p // 100}'
        n = len(self.periodos_atrasados)
        if n > 1:
            return f'Pagar {etiqueta} · {n} meses atrasados'
        return f'Pagar {etiqueta}'

    @property
    def estado_mes(self):
        if not self.activa:
            return 'pausada'
        if self.periodos_atrasados:
            return 'atrasada'
        if self.pagada_este_mes:
            return 'pagada'
        return 'pendiente'

    @property
    def texto_estado(self):
        if not self.activa:
            return 'Pausada'
        atrasados = len(self.periodos_atrasados)
        if atrasados > 1:
            return f'{atrasados} meses sin pagar'
        if atrasados == 1:
            return 'Mes atrasado'
        if self.pagada_este_mes:
            return 'Pagada este mes'
        d = self.dias_para_cobro
        if d == 0:
            return 'Se cobra hoy'
        return f'Se cobra en {d} día{"s" if d != 1 else ""}'

    @property
    def total_pagado_historico(self):
        return Transaccion.objects.filter(
            usuario=self.usuario, tipo='EGRESO',
            descripcion__startswith=f'Suscripción: {self.nombre}',
        ).aggregate(t=models.Sum('monto'))['t'] or 0

    @property
    def meses_activa(self):
        fin = self.fecha_cancelada or date.today()
        return (fin.year - self.fecha_inicio.year) * 12 + (fin.month - self.fecha_inicio.month) + 1

class PagoServicio(models.Model):
    suscripcion = models.ForeignKey('Suscripcion', on_delete=models.CASCADE, related_name='pagos')
    periodo = models.IntegerField(db_index=True, help_text='Mes al que corresponde: año*100+mes')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_pago = models.DateField(default=timezone.now)

    class Meta:
        ordering = ['-periodo']
        constraints = [
            models.UniqueConstraint(fields=['suscripcion', 'periodo'],
                                    name='pago_servicio_unico_por_mes'),
        ]

    def __str__(self):
        return f'{self.suscripcion.nombre} — {self.periodo}'

    @property
    def etiqueta_mes(self):
        nombres = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
                   'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        return f'{nombres[self.periodo % 100 - 1]} {self.periodo // 100}'
