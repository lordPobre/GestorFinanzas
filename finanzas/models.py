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

    # Color por categoría — lo usa la dona de "En qué se va" y los chips.
    # Vive acá para que el template no tenga colores hardcodeados.
    COLORES_CATEGORIA = {
        'Comida': '#60a5fa',
        'Transporte': '#34d399',
        'Servicios': '#a78bfa',
        'Ocio': '#fbbf24',
        'Salud': '#22d3ee',
        'Suscripciones': '#fb923c',
        'Cuentas': '#f472b6',
        'Otros': 'rgba(241,240,255,.28)',
    }

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default='Otros')
    fecha = models.DateField(default=timezone.now)
    descripcion = models.CharField(max_length=200, blank=True)
    es_cuota = models.BooleanField(default=False)

    class Meta:
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f"{self.tipo} - {self.monto}"

    @property
    def es_ingreso(self):
        """Para elegir color y signo en el template sin comparar strings."""
        return self.tipo == 'INGRESO'

    @property
    def color_categoria(self):
        return self.COLORES_CATEGORIA.get(self.categoria, self.COLORES_CATEGORIA['Otros'])

    @property
    def icono(self):
        """Icono Font Awesome según la categoría."""
        iconos = {
            'Comida': 'fa-cart-shopping',
            'Transporte': 'fa-car',
            'Servicios': 'fa-bolt',
            'Ocio': 'fa-film',
            'Salud': 'fa-kit-medical',
            'Suscripciones': 'fa-rotate',
            'Cuentas': 'fa-file-invoice',
        }
        if self.es_ingreso:
            return 'fa-arrow-down'
        return iconos.get(self.categoria, 'fa-arrow-up')


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

    class Meta:
        ordering = ['fecha_inicio', 'id']

    def __str__(self):
        return self.acreedor

    # ---------- Plazos ----------

    @property
    def fecha_fin_estimada(self):
        return self.fecha_inicio + relativedelta(months=self.cuotas_totales - 1)

    @property
    def proximo_vencimiento(self):
        if self.cuotas_pagadas >= self.cuotas_totales:
            return None
        return self.fecha_inicio + relativedelta(months=self.cuotas_pagadas)

    @property
    def dia_pago(self):
        """Día del mes en que se cobra. Se deriva de fecha_inicio, así que no
        hay un campo nuevo que mantener."""
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
        """Sufijo de la clase CSS: .urg-<valor>.

        Antes devolvía None cuando la deuda estaba saldada, lo que dejaba el
        badge sin clase y sin color. Ahora devuelve 'saldada'.
        """
        if self.esta_saldada:
            return 'saldada'
        d = self.dias_para_vencer
        if d is None:
            return 'normal'
        if d < 0:
            return 'vencida'
        if d <= 3:
            return 'critica'
        if d <= 7:
            return 'proxima'
        return 'normal'

    @property
    def texto_urgencia(self):
        """Frase corta y en lenguaje plano para el badge de la tarjeta."""
        if self.esta_saldada:
            return 'Saldada'
        d = self.dias_para_vencer
        if d is None:
            return f'Vence el {self.dia_pago}'
        if d < 0:
            dias = abs(d)
            return f'Vencida hace {dias} día{"s" if dias != 1 else ""}'
        if d == 0:
            return 'Vence hoy'
        return f'Vence el {self.dia_pago} · en {d} día{"s" if d != 1 else ""}'

    # ---------- Cuotas ----------

    @property
    def esta_saldada(self):
        return self.cuotas_pagadas >= self.cuotas_totales

    @property
    def cuotas_restantes(self):
        return max(0, self.cuotas_totales - self.cuotas_pagadas)

    @property
    def cuota_actual(self):
        """Número de la cuota que toca pagar (1-based). None si está saldada."""
        if self.esta_saldada:
            return None
        return self.cuotas_pagadas + 1

    @property
    def rango_cuotas(self):
        """Una entrada por cuota, para dibujar la fila de marcas (.pip).
        Cada item ya trae su clase, así el template no calcula nada.
        Se corta en 36 marcas: más allá no se distinguen.
        """
        total = min(self.cuotas_totales, 36)
        marcas = []
        for i in range(total):
            if i < self.cuotas_pagadas:
                estado = 'paid'
            elif i == self.cuotas_pagadas:
                estado = 'next'
            else:
                estado = ''
            marcas.append({'indice': i + 1, 'clase': estado})
        return marcas

    @property
    def porcentaje(self):
        if self.cuotas_totales == 0:
            return 0
        return int((self.cuotas_pagadas / self.cuotas_totales) * 100)

    # ---------- Montos ----------

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

    def __str__(self):
        return self.nombre

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
        """La línea en lenguaje plano bajo la barra de la meta."""
        if self.esta_completa:
            return 'Meta cumplida.'
        sugerido = self.ahorro_mensual_sugerido
        if sugerido:
            meses = max(1, round(float(self.monto_faltante) / sugerido))
            return f'Aportando ${int(sugerido):,}'.replace(',', '.') + f' al mes lo logras en {meses} meses.'
        return f'Te faltan ${int(self.monto_faltante):,}'.replace(',', '.') + ' para llegar.'


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
    def inicial(self):
        """Letra del avatar en el sidebar y el perfil."""
        return (self.nombre_display or '?')[0].upper()

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
    def inicial(self):
        return (self.nombre or '?')[0].upper()

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
    def prestamos_activos(self):
        """Préstamos que aún no están saldados. Alimenta el contador del menú."""
        return [p for p in self.prestamos.all() if not p.esta_pagado]

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

    @property
    def resumen_meta(self):
        """Línea bajo el nombre en la lista de personas."""
        n = self.cantidad_prestamos
        if n == 0:
            return 'Sin préstamos'
        return f'{n} préstamo{"s" if n != 1 else ""}'


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
    def es_en_cuotas(self):
        return self.tipo == 'CUOTAS'

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

    @property
    def cuotas_pendientes(self):
        if self.tipo != 'CUOTAS':
            return 0
        return max(0, self.cuotas_totales - self.cuotas_abonadas)

    @property
    def detalle_plan(self):
        """La frase que explica el préstamo en la tarjeta. Es lo que hace que
        se entienda sin leer los números: 'Cuota de $60.000 · 1 de 3 abonadas'."""
        if self.tipo == 'CUOTAS':
            cuota = int(self.monto_cuota)
            return (f'Cuota de ${cuota:,}'.replace(',', '.')
                    + f' · {self.cuotas_abonadas} de {self.cuotas_totales} abonadas')
        if self.esta_pagado:
            return 'Devuelto completo'
        return 'Sin plazo definido'

    @property
    def montos_sugeridos(self):
        """Atajos del modal de abono: una cuota, dos, o todo lo pendiente.
        Evita que el usuario tenga que calcular a mano."""
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

    @property
    def texto_urgencia(self):
        if self.pagado:
            return 'Pagado'
        d = self.dias_para_vencer
        if d is None:
            return ''
        if d < 0:
            return f'Vencido hace {abs(d)} día{"s" if abs(d) != 1 else ""}'
        if d == 0:
            return 'Vence hoy'
        return f'En {d} día{"s" if d != 1 else ""}'


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
    def inicial(self):
        return (self.nombre or '?')[0].upper()

    @property
    def monto_anual(self):
        """Lo que cuesta al año. Es el número que hace reaccionar al usuario."""
        return float(self.monto) * 12

    @property
    def texto_cobro(self):
        if not self.activa:
            return 'Pausada'
        return f'Se cobra el {self.dia_cobro} de cada mes'

    @property
    def dias_para_cobro(self):
        """Días hasta el próximo cobro. None si está cancelada."""
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
