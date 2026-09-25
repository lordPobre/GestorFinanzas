from datetime import date

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from ..almacenamiento import obtener_almacen


def _ruta_avatar(instance, filename):
    import uuid
    ext = (filename.rsplit('.', 1)[-1] or 'jpg').lower()[:5]
    return f'avatares/{instance.usuario_id}/{uuid.uuid4().hex[:8]}.{ext}'

SEGUNDOS_URL_FOTO_EN_CACHE = 5 * 60 * 60


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

    google_sub = models.CharField(max_length=64, null=True, blank=True, unique=True)

    foto = models.ImageField(
        upload_to=_ruta_avatar, storage=obtener_almacen, null=True, blank=True)

    aviso_mensual = models.BooleanField(default=True)
    aviso_dia     = models.IntegerField(default=20)
    aviso_ultimo_periodo = models.IntegerField(default=0)

    analisis_ia = models.BooleanField(default=True)

    correo_verificado = models.BooleanField(default=False)
    correo_verificado_en = models.DateTimeField(null=True, blank=True)

    politica_version  = models.CharField(max_length=20, blank=True)
    politica_aceptada = models.DateTimeField(null=True, blank=True)

    ultima_actividad = models.DateTimeField(null=True, blank=True)
    aviso_inactividad_enviado = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Perfil de {self.usuario.username}"

    def save(self, *args, **kwargs):
        anterior = None
        if self.pk:
            try:
                anterior = UserProfile.objects.only("foto").get(pk=self.pk).foto
            except UserProfile.DoesNotExist:
                anterior = None

        super().save(*args, **kwargs)

        if anterior and anterior.name and anterior.name != self.foto.name:
            try:
                anterior.delete(save=False)
            except Exception:
                pass

    @property
    def nombre_display(self):
        return self.nombre_completo or self.usuario.username

    @property
    def inicial(self):
        return (self.nombre_display or '?')[0].upper()

    @property
    def foto_url(self):
        if not self.foto:
            return None
        from django.core.cache import cache
        clave = f'foto-url:{self.foto.name}'
        url = cache.get(clave)
        if url:
            return url
        try:
            url = self.foto.url
        except ValueError:
            return None
        cache.set(clave, url, SEGUNDOS_URL_FOTO_EN_CACHE)
        return url

    @property
    def ubicacion(self):
        parts = [p for p in [self.ciudad, self.pais] if p]
        return ', '.join(parts) if parts else None

    @property
    def dia_aviso_efectivo(self):
        from calendar import monthrange
        hoy = date.today()
        _, ultimo = monthrange(hoy.year, hoy.month)
        return min(max(1, self.aviso_dia), ultimo)

@receiver(post_delete, sender=UserProfile)
def _borrar_avatar_al_eliminar_perfil(sender, instance, **kwargs):
    if instance.foto and instance.foto.name:
        try:
            instance.foto.delete(save=False)
        except Exception:
            pass
