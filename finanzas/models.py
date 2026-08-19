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
        # Si la deuda ya está pagada por completo, no hay vencimiento
        if self.cuotas_pagadas >= self.cuotas_totales:
            return None
        fecha_evaluar = self.proximo_vencimiento or self.fecha_inicio
        if fecha_evaluar:
            delta = fecha_evaluar - date.today()
            return delta.days
        return None

    @property
    def urgencia(self):
        # Nivel de urgencia del próximo pago: para alertas visuales
        d = self.dias_para_vencer
        if d is None:
            return None
        if d < 0:
            return 'vencida'      # ya pasó la fecha
        if d <= 3:
            return 'critica'      # vence en 3 días o menos
        if d <= 7:
            return 'proxima'      # vence esta semana
        return 'normal'

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

    @property
    def esta_completa(self):
        return self.monto_actual >= self.monto_meta

    @property
    def dias_restantes(self):
        if not self.fecha_limite:
            return None
        return (self.fecha_limite - date.today()).days


class AporteMeta(models.Model):
    """Registro de cada aporte hecho a una meta de ahorro.
    Permite historial y actualiza monto_actual automáticamente."""
    meta = models.ForeignKey(MetaAhorro, on_delete=models.CASCADE, related_name='aportes')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateField(default=timezone.now)
    nota = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f"Aporte {self.monto} a {self.meta.nombre}"


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


# ============================================================
#  PRÉSTAMOS POR COBRAR (quién me debe)
# ============================================================

class Persona(models.Model):
    """Alguien que me debe dinero. Agrupa uno o varios préstamos."""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='personas')
    nombre = models.CharField(max_length=80)
    contacto = models.CharField(max_length=80, blank=True, help_text='Teléfono, email o nota (opcional)')
    creada = models.DateField(default=timezone.now)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    @property
    def total_prestado(self):
        """Suma de todos los préstamos activos de esta persona."""
        return sum(float(p.monto) for p in self.prestamos.all())

    @property
    def total_abonado(self):
        """Suma de todo lo que esta persona ya me pagó."""
        return sum(float(p.total_abonado) for p in self.prestamos.all())

    @property
    def total_pendiente(self):
        """Lo que todavía me debe en total."""
        return self.total_prestado - self.total_abonado

    @property
    def tiene_deuda(self):
        return self.total_pendiente > 0

    @property
    def cantidad_prestamos(self):
        return self.prestamos.count()

    @property
    def cuotas_del_mes(self):
        """Suma de las cuotas mensuales de los préstamos EN CUOTAS que aún
        no están saldados. Es lo que la persona debería pagarme al mes."""
        total = 0.0
        for p in self.prestamos.all():
            if p.tipo == 'CUOTAS' and not p.esta_pagado:
                total += float(p.monto_cuota)
        return total

    @property
    def unicos_pendientes(self):
        """Suma de los pagos ÚNICOS que aún no me pagan. No tienen plazo
        mensual, así que siguen pendientes hasta que se salden."""
        total = 0.0
        for p in self.prestamos.all():
            if p.tipo == 'UNICO' and not p.esta_pagado:
                total += float(p.monto_pendiente)
        return total


class Prestamo(models.Model):
    """Un préstamo individual hecho a una persona.
    Puede ser pago único o dividido en cuotas."""
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
    def monto_cuota(self):
        """Solo aplica si es en cuotas."""
        if self.tipo == 'CUOTAS' and self.cuotas_totales > 0:
            return float(self.monto) / self.cuotas_totales
        return float(self.monto)

    @property
    def cuotas_abonadas(self):
        """Cuántas cuotas equivalen a lo ya abonado (aproximado)."""
        if self.tipo == 'CUOTAS' and self.monto_cuota > 0:
            return int(self.total_abonado / self.monto_cuota)
        return 1 if self.esta_pagado else 0


class AbonoPrestamo(models.Model):
    """Cada pago que la persona me hace para saldar un préstamo."""
    prestamo = models.ForeignKey(Prestamo, on_delete=models.CASCADE, related_name='abonos')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateField(default=timezone.now)
    nota = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f"Abono {self.monto} — {self.prestamo.descripcion}"


class GastoPendiente(models.Model):
    """Un gasto puntual pendiente (ej: una cuenta que llega).
    Cuenta como gasto del mes desde que se crea (con fecha = vencimiento).
    Marcarlo pagado solo cambia su estado; no vuelve a sumar."""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gastos_pendientes')
    nombre = models.CharField(max_length=100)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_vencimiento = models.DateField()
    categoria = models.CharField(max_length=50, blank=True, default='Cuentas')
    pagado = models.BooleanField(default=False)
    fecha_pago = models.DateField(null=True, blank=True)
    creado = models.DateField(default=timezone.now)
    # Transacción de gasto asociada (creada al crear el gasto pendiente).
    # Así cuenta en el mes de vencimiento sin doble conteo al pagar.
    transaccion = models.OneToOneField('Transaccion', on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='gasto_pendiente')

    class Meta:
        ordering = ['fecha_vencimiento', 'id']

    def __str__(self):
        return f"{self.nombre} — {self.monto}"

    @property
    def dias_para_vencer(self):
        """Días hasta el vencimiento. Negativo si ya venció. None si está pagado."""
        if self.pagado:
            return None
        return (self.fecha_vencimiento - date.today()).days

    @property
    def urgencia(self):
        """Estado de urgencia para el aviso visual."""
        if self.pagado:
            return 'pagado'
        d = self.dias_para_vencer
        if d is None:
            return 'normal'
        if d < 0:
            return 'vencido'
        if d == 0:
            return 'hoy'
        if d <= 3:
            return 'proximo'
        return 'normal'


class Suscripcion(models.Model):
    """Suscripción recurrente (Netflix, Spotify, etc.).
    Genera un gasto automáticamente cada mes hasta que se cancela."""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='suscripciones')
    nombre = models.CharField(max_length=100)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    categoria = models.CharField(max_length=50, blank=True, default='Suscripciones')
    dia_cobro = models.IntegerField(default=1, help_text='Día del mes en que se cobra (1-28)')
    activa = models.BooleanField(default=True)
    fecha_inicio = models.DateField(default=timezone.now)
    fecha_cancelada = models.DateField(null=True, blank=True)
    # Hasta qué mes ya se generó el cobro (para no duplicar). Formato: año*100+mes
    ultimo_mes_generado = models.IntegerField(default=0)

    class Meta:
        ordering = ['-activa', 'nombre']

    def __str__(self):
        return f"{self.nombre} — {self.monto}/mes"

    @property
    def total_pagado_historico(self):
        """Cuánto se ha gastado en total en esta suscripción."""
        return Transaccion.objects.filter(
            usuario=self.usuario, tipo='EGRESO',
            descripcion__startswith=f'Suscripción: {self.nombre}',
        ).aggregate(t=models.Sum('monto'))['t'] or 0

    @property
    def meses_activa(self):
        """Cuántos meses lleva activa (aproximado)."""
        fin = self.fecha_cancelada or date.today()
        return (fin.year - self.fecha_inicio.year) * 12 + (fin.month - self.fecha_inicio.month) + 1
