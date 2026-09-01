"""Cifrado de campos de texto en la base de datos.

POR QUÉ NO SE CIFRAN LOS MONTOS

Un campo cifrado es opaco para la base: no se puede sumar, ordenar ni
filtrar por rango. Toda esta app se apoya en eso:

    Transaccion.objects.filter(...).aggregate(t=Sum("monto"))

Con el monto cifrado, esa consulta no existe. Habría que traer TODAS las
filas del mes a Python, descifrarlas una por una y sumar ahí. Con unos
cientos de movimientos ya se nota; con miles, cada carga del panel tarda
segundos. Y se pierden los índices, el filtro por rango de montos y el
orden por importe.

El costo es enorme y la protección menor de lo que parece: la clave tiene
que vivir en el mismo servidor que la app, así que quien pueda leer la base
normalmente también puede leer la clave.

QUÉ SÍ PROTEGE, Y ESTÁ AQUÍ

Los campos de TEXTO LIBRE. Nunca se suman ni se ordenan, y son los que
revelan cosas privadas: "Préstamo para el abogado del divorcio", el
teléfono de alguien, la nota de un abono. Un monto suelto dice poco; una
descripción dice mucho.

Para los montos, la protección correcta es cifrado en reposo a nivel de
motor (ver SEGURIDAD-AVANZADA.md): protege el archivo entero sin que la app
pierda la capacidad de consultar.
"""
import base64
import os

from django.core.exceptions import ImproperlyConfigured
from django.db import models


def _clave():
    """La clave de cifrado, desde el entorno.

    Se genera una vez con:

        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    y se guarda en FIELD_ENCRYPTION_KEY. Si se pierde, los datos cifrados
    NO se recuperan: no hay puerta trasera. Guárdala donde guardes las
    copias de seguridad, pero no en el mismo sitio que la base.
    """
    bruta = os.environ.get("FIELD_ENCRYPTION_KEY", "").strip()
    if not bruta:
        raise ImproperlyConfigured(
            "Falta FIELD_ENCRYPTION_KEY. Sin ella los campos cifrados no se "
            "pueden leer ni escribir."
        )
    return bruta.encode()


def _cifrador():
    """Se construye una vez y se reutiliza: crear un Fernet en cada campo de
    cada fila es caro cuando se listan cien movimientos."""
    global _CACHE
    try:
        return _CACHE
    except NameError:
        pass
    from cryptography.fernet import Fernet
    _CACHE = Fernet(_clave())
    return _CACHE


class TextoCifrado(models.TextField):
    """TextField que se guarda cifrado y se lee en claro.

    Es transparente para el resto del código: se asigna y se lee como
    cualquier texto. Lo que NO se puede es filtrar por él
    (`filter(descripcion__icontains="…")` no encuentra nada, porque en la
    base hay una cadena cifrada distinta cada vez).

    Por eso la búsqueda de la app filtra en el navegador sobre lo ya
    cargado, no en la base — que es como estaba hecha desde el principio.
    """

    # Marca para reconocer lo ya cifrado y no cifrarlo dos veces al migrar.
    PREFIJO = "enc1:"

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        texto = str(value)
        if texto.startswith(self.PREFIJO):
            return texto   # ya venía cifrado
        token = _cifrador().encrypt(texto.encode("utf-8"))
        return self.PREFIJO + token.decode("ascii")

    def from_db_value(self, value, expression, connection):
        return self._descifrar(value)

    def to_python(self, value):
        return self._descifrar(value)

    def _descifrar(self, value):
        if value is None or value == "":
            return value
        texto = str(value)
        if not texto.startswith(self.PREFIJO):
            # Texto en claro de antes de cifrar el campo. Se devuelve tal
            # cual: si no, los datos anteriores a la migración se verían
            # como basura.
            return texto
        from cryptography.fernet import InvalidToken
        try:
            return _cifrador().decrypt(texto[len(self.PREFIJO):].encode()).decode("utf-8")
        except (InvalidToken, Exception):
            # Clave equivocada o dato corrupto. Se avisa en vez de reventar
            # la página entera: un campo ilegible no debe tumbar la lista.
            return "[no se pudo descifrar]"
