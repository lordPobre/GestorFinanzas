from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class SegundoFactor(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE,
                                   related_name="segundo_factor")
    secreto = models.CharField(max_length=64)
    activo = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)
    ultimo_uso = models.DateTimeField(null=True, blank=True)

    ultimo_codigo = models.CharField(max_length=6, blank=True)

    class Meta:
        verbose_name = "Segundo factor"
        verbose_name_plural = "Segundos factores"

    def __str__(self):
        return f"2FA de {self.usuario.username}"

    @staticmethod
    def generar_secreto():
        import pyotp
        return pyotp.random_base32()

    def uri(self):
        import pyotp
        return pyotp.TOTP(self.secreto).provisioning_uri(
            name=self.usuario.email or self.usuario.username,
            issuer_name="Rekon",
        )

    def verificar(self, codigo):
        import pyotp
        codigo = (codigo or "").strip().replace(" ", "")
        if not codigo.isdigit() or len(codigo) != 6:
            return False
        if codigo == self.ultimo_codigo:
            return False
        if pyotp.TOTP(self.secreto).verify(codigo, valid_window=1):
            from django.utils import timezone as _tz
            self.ultimo_codigo = codigo
            self.ultimo_uso = _tz.now()
            self.save(update_fields=["ultimo_codigo", "ultimo_uso"])
            return True
        return False

class CodigoRespaldo(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE,
                                related_name="codigos_respaldo")
    codigo_hash = models.CharField(max_length=128)
    usado = models.BooleanField(default=False)
    usado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Código de respaldo"
        verbose_name_plural = "Códigos de respaldo"

    @classmethod
    def generar(cls, usuario, cantidad=8):
        import secrets
        from django.contrib.auth.hashers import make_password

        cls.objects.filter(usuario=usuario).delete()
        codigos = []
        for _ in range(cantidad):
            alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
            crudo = "".join(secrets.choice(alfabeto) for _ in range(8))
            codigos.append(crudo[:4] + "-" + crudo[4:])
            cls.objects.create(usuario=usuario, codigo_hash=make_password(crudo))
        return codigos

    @classmethod
    def consumir(cls, usuario, codigo):
        from django.contrib.auth.hashers import check_password
        from django.utils import timezone as _tz

        limpio = (codigo or "").strip().upper().replace("-", "").replace(" ", "")
        if len(limpio) != 8:
            return False
        for c in cls.objects.filter(usuario=usuario, usado=False):
            if check_password(limpio, c.codigo_hash):
                c.usado = True
                c.usado_en = _tz.now()
                c.save(update_fields=["usado", "usado_en"])
                return True
        return False

class SesionActiva(models.Model):

    NAVEGADORES = [('Edg', 'Edge'), ('OPR', 'Opera'), ('Chrome', 'Chrome'),
                   ('Firefox', 'Firefox'), ('Safari', 'Safari')]
    SISTEMAS = [('iPhone', 'iPhone'), ('iPad', 'iPad'), ('Android', 'Android'),
                ('Windows', 'Windows'), ('Mac OS', 'Mac'), ('Linux', 'Linux')]
    MOVILES = {'iPhone', 'iPad', 'Android'}

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sesiones')
    clave = models.CharField(max_length=40, unique=True, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    agente = models.CharField(max_length=300, blank=True)
    creada = models.DateTimeField(default=timezone.now)
    ultima_vez = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-ultima_vez']
        verbose_name = 'Sesión activa'
        verbose_name_plural = 'Sesiones activas'

    def __str__(self):
        return f'{self.usuario.username} — {self.aparato}'

    def _buscar(self, pares):
        for clave, nombre in pares:
            if clave.lower() in (self.agente or '').lower():
                return nombre
        return ''

    @property
    def navegador(self):
        return self._buscar(self.NAVEGADORES)

    @property
    def sistema(self):
        return self._buscar(self.SISTEMAS)

    @property
    def es_movil(self):
        return self.sistema in self.MOVILES

    @property
    def icono(self):
        if self.sistema in ('iPhone', 'Android'):
            return 'fa-mobile-screen'
        if self.sistema == 'iPad':
            return 'fa-tablet-screen-button'
        return 'fa-desktop'

    @property
    def aparato(self):
        nav, sis = self.navegador, self.sistema
        if nav and sis:
            return f'{nav} en {sis}'
        return nav or sis or 'Aparato desconocido'


class Passkey(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='passkeys')
    credencial_id = models.CharField(max_length=512, unique=True)
    clave_publica = models.TextField()
    contador = models.PositiveBigIntegerField(default=0)
    nombre = models.CharField(max_length=60)
    creada = models.DateTimeField(auto_now_add=True)
    ultimo_uso = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creada']
        verbose_name = 'Acceso con Face ID o huella'
        verbose_name_plural = 'Accesos con Face ID o huella'

    def __str__(self):
        return f'{self.nombre} de {self.usuario.username}'


class EventoSeguridad(models.Model):
    TIPOS = [
        ('acceso', 'Acceso'),
        ('acceso_fallido', 'Acceso fallido'),
        ('salida', 'Salida'),
        ('bloqueo', 'Bloqueo por intentos'),
        ('codigo_fallido', 'Código de verificación incorrecto'),
        ('2fa_activada', 'Verificación en dos pasos activada'),
        ('2fa_desactivada', 'Verificación en dos pasos desactivada'),
        ('codigos_regenerados', 'Códigos de respaldo regenerados'),
        ('codigo_respaldo_usado', 'Código de respaldo usado'),
        ('passkey_agregada', 'Face ID o huella vinculado'),
        ('passkey_quitada', 'Face ID o huella quitado'),
        ('passkey_fallida', 'Face ID o huella rechazado'),
        ('contrasena_cambiada', 'Contraseña cambiada'),
        ('recuperacion_pedida', 'Recuperación de contraseña pedida'),
        ('contrasena_restablecida', 'Contraseña restablecida'),
        ('sesiones_cerradas', 'Sesiones cerradas a distancia'),
        ('datos_descargados', 'Descarga de datos personales'),
        ('cuenta_eliminada', 'Cuenta eliminada'),
        ('admin_denegado', 'Acceso al panel denegado'),
    ]

    creado = models.DateTimeField(auto_now_add=True, db_index=True)
    tipo = models.CharField(max_length=30, choices=TIPOS, db_index=True)
    usuario = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='eventos_seguridad')
    referencia = models.CharField(max_length=150, blank=True, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    agente = models.CharField(max_length=300, blank=True)
    detalle = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['-creado']
        verbose_name = 'Evento de seguridad'
        verbose_name_plural = 'Eventos de seguridad'

    def __str__(self):
        return f'{self.get_tipo_display()} · {self.referencia or "-"} · {self.creado:%Y-%m-%d %H:%M}'
