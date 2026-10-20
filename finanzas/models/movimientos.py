
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from .. import fechas
from ..categorias_base import COLOR_OTROS


class VinculoCategoria(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        campos = kwargs.get('update_fields')
        if campos is None or 'categoria' in campos:
            al_dia = self.categoria_ref_id and getattr(self, '_categoria_vinculada', None) == self.categoria
            if not al_dia:
                self.categoria_ref_id = Categoria.id_de(self.usuario_id, self.categoria)
                if campos is not None:
                    kwargs['update_fields'] = [*campos, 'categoria_ref']
            self._categoria_vinculada = self.categoria
        super().save(*args, **kwargs)

    @classmethod
    def from_db(cls, db, field_names, values):
        obj = super().from_db(db, field_names, values)
        obj._categoria_vinculada = obj.__dict__.get('categoria')
        return obj

    @property
    def nombre_categoria(self):
        ref = self.categoria_ref
        return ref.nombre if ref else self.categoria

    @property
    def color_categoria(self):
        ref = self.categoria_ref
        return ref.color if ref else COLOR_OTROS

    @property
    def icono_categoria(self):
        ref = self.categoria_ref
        return ref.icono if ref else None


class ConCategoria(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related('categoria_ref')


class Transaccion(VinculoCategoria):
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

    MANUAL = 'manual'
    SUSCRIPCION = 'suscripcion'
    PENDIENTE = 'pendiente'
    CUOTA = 'cuota'
    CARTOLA = 'cartola'
    ORIGENES = [
        (MANUAL, 'Anotado a mano'),
        (SUSCRIPCION, 'Cobro de suscripción'),
        (PENDIENTE, 'Cuenta por pagar'),
        (CUOTA, 'Pago de cuota'),
        (CARTOLA, 'Cartola'),
    ]
    PREFIJOS = {SUSCRIPCION: 'Suscripción: ', PENDIENTE: 'Pendiente: '}

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default='Otros')
    categoria_ref = models.ForeignKey('Categoria', on_delete=models.RESTRICT, null=True, blank=True,
                                      editable=False, related_name='movimientos')
    fecha = models.DateField(default=timezone.now)
    descripcion = models.CharField(max_length=200, blank=True)
    es_cuota = models.BooleanField(default=False)

    pagado = models.BooleanField(default=True)
    fecha_pago = models.DateField(null=True, blank=True)
    suscripcion = models.ForeignKey('Suscripcion', on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name='cobros')
    origen = models.CharField(max_length=12, choices=ORIGENES, default=MANUAL, editable=False)
    periodo_cobro = models.IntegerField(null=True, blank=True, editable=False)

    objects = ConCategoria()

    class Meta:
        ordering = ['-fecha', '-id']
        indexes = [
            models.Index(fields=['usuario', 'fecha'], name='trans_usuario_fecha'),
            models.Index(fields=['usuario', 'tipo', 'fecha'], name='trans_usuario_tipo_fecha'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['suscripcion', 'periodo_cobro'],
                condition=models.Q(suscripcion__isnull=False, periodo_cobro__isnull=False),
                name='cobro_suscripcion_unico_por_mes'),
        ]

    def __str__(self):
        return f"{self.tipo} - {self.monto}"

    @property
    def es_ingreso(self):
        return self.tipo == 'INGRESO'

    @property
    def es_gasto_unico(self):
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
        dias = (fechas.hoy() - self.fecha).days
        if dias > 0:
            return f'Sin pagar hace {dias} día{"s" if dias != 1 else ""}'
        return 'Sin pagar'

    @property
    def es_cobro_suscripcion(self):
        return self.origen == self.SUSCRIPCION or self.suscripcion_id is not None

    @property
    def es_cuenta_pendiente(self):
        return self.origen == self.PENDIENTE

    @property
    def nombre_sin_prefijo(self):
        desc = (self.descripcion or '').strip()
        clave = self.SUSCRIPCION if self.es_cobro_suscripcion else self.origen
        prefijo = self.PREFIJOS.get(clave)
        if prefijo and desc.startswith(prefijo):
            return desc[len(prefijo):].strip()
        return desc

    @classmethod
    def q_vinculados(cls):
        return (models.Q(origen__in=[cls.SUSCRIPCION, cls.PENDIENTE])
                | models.Q(suscripcion__isnull=False)
                | models.Q(gasto_pendiente__isnull=False))

    @property
    def clase_tono(self):
        if self.es_ingreso:
            return 'ingreso'
        if self.es_cuota:
            return 'cuota'
        if self.es_cobro_suscripcion:
            return 'suscripcion'
        return 'gasto'

    @property
    def marca_suscripcion(self):
        from .suscripciones import Suscripcion

        if not self.es_cobro_suscripcion:
            return None
        nombre = self.nombre_sin_prefijo.lower()
        for clave, icono, color in Suscripcion.MARCAS:
            if clave in nombre:
                return {'icono': icono, 'color': color,
                        'usa_inicial': icono is None,
                        'inicial': (nombre or '?')[0].upper()}
        return None

    @property
    def icono(self):
        return self.icono_categoria or ('fa-arrow-down' if self.es_ingreso else 'fa-arrow-up')

class Categoria(models.Model):
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

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categorias',
                                null=True, blank=True)
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
            models.UniqueConstraint(fields=['slug'], condition=models.Q(usuario__isnull=True),
                                    name='categoria_base_unica'),
        ]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
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

    @property
    def es_base(self):
        return self.usuario_id is None

    @classmethod
    def id_de(cls, usuario_id, texto):
        if not texto:
            return None
        return (cls.objects
                .filter(models.Q(usuario_id=usuario_id) | models.Q(usuario__isnull=True), slug=texto)
                .order_by(models.F('usuario_id').asc(nulls_last=True))
                .values_list('id', flat=True).first())

    @classmethod
    def opciones(cls, usuario, tipo=None):
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
        filas = (cls.objects.filter(models.Q(usuario=usuario) | models.Q(usuario__isnull=True))
                 .order_by(models.F('usuario_id').asc(nulls_first=True), 'id'))
        return {c.slug: {'label': c.nombre, 'color': c.color, 'icono': c.icono, 'propia': not c.es_base}
                for c in filas}

class Presupuesto(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    limite_mensual = models.DecimalField(max_digits=12, decimal_places=2, default=500000)

    def __str__(self):
        return f"Presupuesto de {self.usuario.username}: ${self.limite_mensual}"

class TopeCategoria(VinculoCategoria):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='topes')
    categoria = models.CharField(max_length=50)
    categoria_ref = models.ForeignKey('Categoria', on_delete=models.RESTRICT, null=True, blank=True,
                                      editable=False, related_name='topes')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    avisar = models.BooleanField(default=True)
    aviso_periodo = models.IntegerField(default=0)
    aviso_nivel = models.IntegerField(default=0)

    class Meta:
        ordering = ['categoria']
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'categoria'],
                                    name='tope_unico_por_categoria'),
        ]

    def __str__(self):
        return f'Tope de {self.categoria}: {self.monto}'

class GastoPendiente(VinculoCategoria):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gastos_pendientes')
    nombre = models.CharField(max_length=100)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_vencimiento = models.DateField()
    categoria = models.CharField(max_length=50, blank=True, default='Cuentas')
    categoria_ref = models.ForeignKey('Categoria', on_delete=models.RESTRICT, null=True, blank=True,
                                      editable=False, related_name='gastos_pendientes')
    pagado = models.BooleanField(default=False)
    fecha_pago = models.DateField(null=True, blank=True)
    creado = models.DateField(default=timezone.now)
    transaccion = models.OneToOneField('Transaccion', on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='gasto_pendiente')

    class Meta:
        ordering = ['fecha_vencimiento', 'id']

    def __str__(self):
        return f"{self.nombre} — {self.monto}"

    @property
    def dias_para_vencer(self):
        if self.pagado:
            return None
        return (self.fecha_vencimiento - fechas.hoy()).days

    @property
    def urgencia(self):
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
