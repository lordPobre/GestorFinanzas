from datetime import date

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


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
        'Otros': '#8b8b96',

        'Sueldo': '#53d258',
        'Freelance': '#2fd8c8',
        'Negocio': '#4b8cff',
        'Venta': '#a3e635',
        'Bono': '#ffd54f',
        'Transferencia': '#38bdf8',
        'Otros_Ingresos': '#8b8b96',
    }

    ICONOS_CATEGORIA = {
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
        'Otros': 'fa-ellipsis',
        'Sueldo': 'fa-money-check-dollar',
        'Freelance': 'fa-laptop-code',
        'Negocio': 'fa-store',
        'Venta': 'fa-tag',
        'Bono': 'fa-gift',
        'Transferencia': 'fa-right-left',
        'Otros_Ingresos': 'fa-ellipsis',
    }

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default='Otros')
    fecha = models.DateField(default=timezone.now)
    descripcion = models.CharField(max_length=200, blank=True)
    es_cuota = models.BooleanField(default=False)

    pagado = models.BooleanField(default=True)
    fecha_pago = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha', '-id']

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
        dias = (date.today() - self.fecha).days
        if dias > 0:
            return f'Sin pagar hace {dias} día{"s" if dias != 1 else ""}'
        return 'Sin pagar'

    @property
    def color_categoria(self):
        return self.COLORES_CATEGORIA.get(self.categoria, self.COLORES_CATEGORIA['Otros'])

    @property
    def clase_tono(self):
        if self.es_ingreso:
            return 'ingreso'
        if self.es_cuota:
            return 'cuota'
        if (self.descripcion or '').startswith('Suscripción: '):
            return 'suscripcion'
        return 'gasto'

    @property
    def marca_suscripcion(self):
        from .suscripciones import Suscripcion

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
        if self.es_ingreso:
            return self.ICONOS_CATEGORIA.get(self.categoria, 'fa-arrow-down')
        return self.ICONOS_CATEGORIA.get(self.categoria, 'fa-arrow-up')

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
        salida = {}
        for slug, label in Transaccion.CATEGORIAS:
            salida[slug] = {
                'label': label,
                'color': Transaccion.COLORES_CATEGORIA.get(
                    slug, Transaccion.COLORES_CATEGORIA['Otros']),
                'icono': Transaccion.ICONOS_CATEGORIA.get(slug, 'fa-tag'),
                'propia': False,
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

class GastoPendiente(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gastos_pendientes')
    nombre = models.CharField(max_length=100)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_vencimiento = models.DateField()
    categoria = models.CharField(max_length=50, blank=True, default='Cuentas')
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
        return (self.fecha_vencimiento - date.today()).days

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
