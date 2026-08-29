from decimal import Decimal

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
        # Estas cuatro son las que se compran a plazo. Antes todas caían en
        # "Otros Gastos", así que la dona de categorías no distinguía un
        # televisor de una multa.
        ('Tecnologia', 'Tecnología y electrónica'),
        ('Ropa', 'Ropa y calzado'),
        ('Hogar', 'Hogar y muebles'),
        ('Viajes', 'Viajes y pasajes'),
        ('Compras', 'Compras online'),
        ('Educacion', 'Educación y cursos'),
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
        'Transporte': '#53d258',
        'Servicios': '#818cf8',
        'Ocio': '#fbbf24',
        'Salud': '#22d3ee',
        'Tecnologia': '#818cf8',
        'Ropa': '#f472b6',
        'Hogar': '#2dd4bf',
        'Viajes': '#38bdf8',
        'Compras': '#c084fc',
        'Educacion': '#facc15',
        'Suscripciones': '#fb923c',
        'Cuentas': '#e25c5c',
        'Otros': 'rgba(245,245,245,.28)',
    }

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default='Otros')
    fecha = models.DateField(default=timezone.now)
    descripcion = models.CharField(max_length=200, blank=True)
    es_cuota = models.BooleanField(default=False)

    # ¿Esta plata ya salió?
    #
    # Un gasto puede estar anotado sin estar pagado todavía: la cuenta que
    # llegó, lo que quedaste debiendo en el almacén, la compra que va con
    # transferencia pendiente. Antes no había forma de distinguirlo, así que
    # "ya gastaste" mezclaba plata que salió con plata que solo estaba
    # comprometida.
    #
    # Por defecto True: la mayoría de los gastos se anotan después de
    # pagarlos, y así todo lo que ya existe en la base queda como pagado.
    pagado = models.BooleanField(default=True)
    fecha_pago = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f"{self.tipo} - {self.monto}"

    @property
    def es_ingreso(self):
        """Para elegir color y signo en el template sin comparar strings."""
        return self.tipo == 'INGRESO'

    @property
    def es_gasto_unico(self):
        """Gasto del día a día: no es cuota ni ingreso. Son los que se pueden
        marcar como pagados a mano."""
        return self.tipo == 'EGRESO' and not self.es_cuota

    @property
    def por_pagar(self):
        return self.es_gasto_unico and not self.pagado

    @property
    def texto_estado_pago(self):
        if self.es_ingreso or not self.es_gasto_unico:
            return ''
        if self.pagado:
            if self.fecha_pago and self.fecha_pago != self.fecha:
                return f'Pagado el {self.fecha_pago.strftime("%d/%m")}'
            return 'Pagado'
        dias = (date.today() - self.fecha).days
        if dias > 0:
            return f'Sin pagar hace {dias} día{"s" if dias != 1 else ""}'
        return 'Sin pagar'

    @property
    def color_categoria(self):
        return self.COLORES_CATEGORIA.get(self.categoria, self.COLORES_CATEGORIA['Otros'])

    @property
    def marca_suscripcion(self):
        """Si el movimiento es el cobro de una suscripción, el icono y color
        de la plataforma. Así la lista de movimientos se lee de un vistazo en
        vez de mostrar la misma flecha para todo."""
        desc = self.descripcion or ''
        if not desc.startswith('Suscripción: '):
            return None
        nombre = desc[len('Suscripción: '):].lower()
        for clave, icono, color in Suscripcion.MARCAS:
            if clave in nombre:
                return {'icono': icono, 'color': color,
                        'usa_inicial': icono is None,
                        'inicial': (nombre or '?')[0].upper()}
        return None

    @property
    def icono(self):
        """Icono Font Awesome según la categoría."""
        iconos = {
            'Comida': 'fa-cart-shopping',
            'Transporte': 'fa-car',
            'Servicios': 'fa-bolt',
            'Ocio': 'fa-film',
            'Salud': 'fa-kit-medical',
            'Tecnologia': 'fa-laptop',
            'Ropa': 'fa-shirt',
            'Hogar': 'fa-couch',
            'Viajes': 'fa-plane',
            'Compras': 'fa-bag-shopping',
            'Educacion': 'fa-graduation-cap',
            'Suscripciones': 'fa-rotate',
            'Cuentas': 'fa-file-invoice',
        }
        if self.es_ingreso:
            return 'fa-arrow-down'
        return iconos.get(self.categoria, 'fa-arrow-up')


class Deuda(models.Model):
    # Las categorías de una compra a plazo no son las del día a día.
    #
    # ANTES esta lista era una copia de las de gasto corriente, encabezada
    # por "Comida y Supermercado" — que además salía preseleccionada. Nadie
    # compra el supermercado en 12 cuotas; lo que se compra a plazo es
    # tecnología, ropa, muebles y viajes. El orden importa: lo más probable
    # va primero, para que la mayoría no tenga que buscar.
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

    # Se mantienen los nombres viejos porque otro código los importa.
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

    # ---------- Plazos ----------

    @property
    def fecha_fin_estimada(self):
        return self.fecha_inicio + relativedelta(months=self.cuotas_totales - 1)

    @property
    def proximo_vencimiento(self):
        """La fecha del mes pendiente más antiguo. Antes era
        fecha_inicio + cuotas_pagadas meses, que da mal si hubo adelantos."""
        p = self.periodo_a_pagar
        return self.fecha_cobro_de(p) if p else None

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

        Sale de los pagos que faltan de verdad. Antes salía de comparar la
        fecha con un contador, así que una deuda con meses impagos podía
        verse 'normal' solo porque el contador iba al día.
        """
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
        """Frase corta y en lenguaje plano para el badge de la tarjeta."""
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

    # ---------- Periodos ----------
    #
    # Un "periodo" es el mes al que pertenece una cuota, guardado como
    # año*100+mes (2026*100+8 = 202608). Es un entero: se ordena, se compara
    # y se indexa sin trucos de fecha.
    #
    # Esto existe porque antes el estado de una cuota se DEDUCÍA del contador
    # cuotas_pagadas: "van 3 pagadas, entonces las tres primeras están
    # pagadas". Eso falla en cuanto alguien se adelanta o se atrasa. Ahora
    # cada pago dice a qué mes corresponde.

    @staticmethod
    def periodo_de(year, month):
        return year * 100 + month

    @property
    def periodos_programados(self):
        """Los meses en que esta compra cobra, en orden.
        Uno por cuota, desde fecha_inicio."""
        salida = []
        for i in range(self.cuotas_totales):
            f = self.fecha_inicio + relativedelta(months=i)
            salida.append(self.periodo_de(f.year, f.month))
        return salida

    def fecha_cobro_de(self, periodo):
        """El día concreto en que se cobra ese mes. Si la deuda empezó un 31
        y el mes tiene 30, cobra el 30."""
        import calendar as _cal
        year, month = periodo // 100, periodo % 100
        _, ultimo = _cal.monthrange(year, month)
        return date(year, month, min(self.fecha_inicio.day, ultimo))

    @property
    def periodos_pagados(self):
        return set(self.pagos.values_list('periodo', flat=True))

    def esta_pagada_en(self, periodo):
        return periodo in self.periodos_pagados

    @property
    def periodos_pendientes(self):
        """Meses programados que nadie pagó, del más antiguo al más nuevo."""
        pagados = self.periodos_pagados
        return [p for p in self.periodos_programados if p not in pagados]

    @property
    def periodo_a_pagar(self):
        """El mes que toca pagar: el pendiente más antiguo.

        Pagar siempre lo más viejo primero es lo que espera cualquiera que
        deba plata, y evita que queden huecos en el historial.
        """
        pendientes = self.periodos_pendientes
        return pendientes[0] if pendientes else None

    @property
    def periodos_atrasados(self):
        """Pendientes cuya fecha de cobro ya pasó. Esto es la deuda vencida
        de verdad, no una estimación."""
        hoy = date.today()
        return [p for p in self.periodos_pendientes if self.fecha_cobro_de(p) < hoy]

    @property
    def monto_atrasado(self):
        return self.monto_cuota * len(self.periodos_atrasados)

    @property
    def texto_a_pagar(self):
        """Qué mes se va a pagar al apretar el botón. Sin esto el usuario no
        sabe si está pagando el mes corriente o una cuota atrasada."""
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
        """Una marca (.pip) por cuota, en orden de mes.

        Antes las marcas se pintaban por posición: las primeras N verdes
        porque cuotas_pagadas era N. Si alguien se adelantaba, mentía. Ahora
        cada marca corresponde a SU mes y dice si ese mes está pagado,
        atrasado o por venir.
        """
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

    # ---------- Montos ----------

    @property
    def monto_cuota(self):
        """Cuota redondeada al peso. La diferencia por redondeo va en la
        última cuota (ver monto_cuota_de), así la suma da el total exacto."""
        if self.cuotas_totales > 0:
            return (self.monto_total / self.cuotas_totales).quantize(Decimal('1'))
        return Decimal('0')

    def monto_cuota_de(self, periodo):
        """La última cuota absorbe el residuo del redondeo. Sin esto,
        12 cuotas de $83.333 sobre $1.000.000 dejaban $4 sin cobrar."""
        programados = self.periodos_programados
        if programados and periodo == programados[-1]:
            return self.monto_total - self.monto_cuota * (self.cuotas_totales - 1)
        return self.monto_cuota

    @property
    def monto_pagado(self):
        """Lo abonado de verdad, sumando los pagos registrados."""
        return sum((p.monto for p in self.pagos.all()), Decimal('0'))

    @property
    def monto_restante(self):
        return self.monto_total - self.monto_pagado


class PagoCuota(models.Model):
    """Un pago de una cuota, atado al MES al que corresponde.

    Es la pieza que faltaba. Antes una deuda solo guardaba cuántas cuotas
    llevaba pagadas, sin decir cuáles: no se podía saber si el mes pasado
    quedó impago, ni fechar el gasto en el mes correcto, ni permitir que
    alguien se adelante sin desordenar todo el historial.

    'periodo' es año*100+mes (agosto 2026 = 202608). La combinación
    deuda + periodo es única: un mes no se puede pagar dos veces.
    """
    deuda = models.ForeignKey('Deuda', on_delete=models.CASCADE, related_name='pagos')
    periodo = models.IntegerField(db_index=True, help_text='Mes al que corresponde: año*100+mes')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_pago = models.DateField(default=timezone.now, help_text='Cuándo se pagó de verdad')
    # El movimiento que este pago generó. Al anular el pago se borra también.
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
        """Se pagó después de la fecha de cobro de su mes."""
        return self.fecha_pago > self.deuda.fecha_cobro_de(self.periodo)


class Categoria(models.Model):
    """Una categoría creada por el usuario.

    Las categorías base viven en las tuplas CATEGORIAS_* de Transaccion: son
    las mismas para todos y no se pueden borrar. Este modelo agrega las
    propias, que es lo que faltaba — si alguien gasta en "Mascotas" o
    "Gimnasio" antes tenía que meterlo todo en "Otros Gastos", y después la
    dona de categorías no le decía nada.

    Transaccion.categoria es un CharField con choices. Django solo valida
    choices en los formularios, no en la base, así que guardar un slug propio
    funciona sin cambiar la columna.
    """
    TIPOS = [('EGRESO', 'Gasto'), ('INGRESO', 'Ingreso')]

    PALETA = [
        ('#ffaa2c', 'Ámbar'), ('#53d258', 'Verde'), ('#4b8cff', 'Azul'),
        ('#e25c5c', 'Rojo'), ('#f4626c', 'Rosa'), ('#2fd8c8', 'Turquesa'),
        ('#ffd54f', 'Amarillo'), ('#818cf8', 'Lila'), ('#c084fc', 'Violeta'),
    ]

    ICONOS = [
        ('fa-tag', 'Etiqueta'), ('fa-cart-shopping', 'Compras'),
        ('fa-utensils', 'Comida'), ('fa-car', 'Auto'), ('fa-house', 'Casa'),
        ('fa-paw', 'Mascotas'), ('fa-dumbbell', 'Gimnasio'),
        ('fa-gift', 'Regalos'), ('fa-plane', 'Viajes'), ('fa-book', 'Estudios'),
        ('fa-mug-hot', 'Café'), ('fa-gamepad', 'Juegos'), ('fa-shirt', 'Ropa'),
        ('fa-heart', 'Salud'), ('fa-wallet', 'Dinero'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categorias')
    nombre = models.CharField(max_length=40)
    slug = models.SlugField(max_length=50)
    tipo = models.CharField(max_length=10, choices=TIPOS, default='EGRESO')
    color = models.CharField(max_length=20, default='#ffaa2c')
    icono = models.CharField(max_length=30, default='fa-tag')
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['tipo', 'nombre']
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'slug'],
                                    name='categoria_unica_por_usuario'),
        ]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        """Genera el slug y le agrega un sufijo si ya existe.

        Sin esto, dos categorías con el mismo nombre revientan la restricción
        única con un error de base de datos que el usuario no entiende.
        """
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.nombre)[:40] or 'categoria'
            slug, n = base, 2
            while True:
                choca = Categoria.objects.filter(usuario=self.usuario, slug=slug)
                if self.pk:
                    choca = choca.exclude(pk=self.pk)
                if not choca.exists():
                    break
                slug = base + '-' + str(n)
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def es_gasto(self):
        return self.tipo == 'EGRESO'

    @classmethod
    def opciones(cls, usuario, tipo=None):
        """Las categorías base más las del usuario, listas para un choices.

        Se usa en los formularios para que las propias aparezcan junto a las
        de siempre, no en una lista aparte.
        """
        base = []
        if tipo != 'INGRESO':
            base += list(Transaccion.CATEGORIAS_EGRESO)
        if tipo != 'EGRESO':
            base += list(Transaccion.CATEGORIAS_INGRESO)
        propias = cls.objects.filter(usuario=usuario, activa=True)
        if tipo:
            propias = propias.filter(tipo=tipo)
        return base + [(c.slug, c.nombre) for c in propias]

    @classmethod
    def mapa(cls, usuario):
        """slug → {label, color, icono}, para pintar cualquier categoría sin
        tener que preguntar de dónde viene."""
        salida = {}
        for slug, label in Transaccion.CATEGORIAS:
            salida[slug] = {
                'label': label,
                'color': Transaccion.COLORES_CATEGORIA.get(
                    slug, Transaccion.COLORES_CATEGORIA['Otros']),
                'icono': 'fa-tag', 'propia': False,
            }
        for c in cls.objects.filter(usuario=usuario):
            salida[c.slug] = {
                'label': c.nombre, 'color': c.color,
                'icono': c.icono, 'propia': True,
            }
        return salida


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


class PagoServicio(models.Model):
    """Un mes de una suscripción, marcado como pagado.

    Mismo criterio que PagoCuota: el mes se guarda en 'periodo'
    (año*100+mes) y la combinación suscripción + periodo es única, así un
    mes no se puede pagar dos veces.

    Ojo con la diferencia respecto a la transacción: el cobro se registra
    como gasto en cuanto llega el mes (lo hace generar_cobros_suscripciones),
    esté pagado o no. Este modelo dice si ese cobro ya salió de tu bolsillo.
    """
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

    # Marcas reconocidas: icono de Font Awesome y color oficial.
    #
    # Font Awesome trae los logos de algunas plataformas pero no de todas
    # (Netflix, Disney+, HBO y Max no existen como icono). Para esas se usa
    # la inicial sobre el color de la marca, que se reconoce igual de rápido
    # y no obliga a incrustar SVG de logos ajenos.
    #
    # El orden importa: se busca por subcadena, así que "apple tv" tiene que
    # ir antes que "apple".
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
        """Icono y color de la plataforma, si se reconoce por el nombre.

        Devuelve un dict listo para el template. Cuando no hay icono se
        marca usa_inicial y el template pinta la letra sobre el color.
        """
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

    # ---------- Periodos (mismo criterio que las cuotas) ----------
    #
    # Una suscripción cobra un mes tras otro. Antes solo se sabía que el
    # cobro se había GENERADO, no si se había pagado: la fila decía "$9.900
    # al mes" y nada más. Ahora cada mes se puede marcar como pagado, igual
    # que una cuota.

    @staticmethod
    def periodo_de(year, month):
        return year * 100 + month

    @property
    def periodos_programados(self):
        """Los meses que esta suscripción ha cobrado, desde que empezó hasta
        hoy (o hasta que se canceló). No incluye meses futuros: un servicio
        se paga cuando llega el cobro, no antes."""
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
        return set(self.pagos.values_list('periodo', flat=True))

    def esta_pagada_en(self, periodo):
        return periodo in self.periodos_pagados

    @property
    def periodos_pendientes(self):
        pagados = self.periodos_pagados
        return [p for p in self.periodos_programados if p not in pagados]

    @property
    def periodo_a_pagar(self):
        """El mes pendiente más antiguo."""
        pendientes = self.periodos_pendientes
        return pendientes[0] if pendientes else None

    @property
    def periodos_atrasados(self):
        """Meses pendientes cuya fecha de cobro ya pasó."""
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
        """Qué mes paga el botón. Sin esto no se sabe si estás pagando el mes
        corriente o poniéndote al día."""
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
        """Sufijo de clase y lectura rápida de la fila."""
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
