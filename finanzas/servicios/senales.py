from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from ..models import AbonoPrestamo, Deuda, PagoCuota, Persona, Prestamo, Transaccion
from .mes import invalidar


def _usuario_de(instancia):
    uid = getattr(instancia, 'usuario_id', None)
    if uid is None and getattr(instancia, 'deuda_id', None):
        uid = Deuda.objects.filter(pk=instancia.deuda_id).values_list('usuario_id', flat=True).first()
    if uid is None and getattr(instancia, 'persona_id', None):
        uid = Persona.objects.filter(pk=instancia.persona_id).values_list('usuario_id', flat=True).first()
    if uid is None and getattr(instancia, 'prestamo_id', None):
        uid = (Prestamo.objects.filter(pk=instancia.prestamo_id)
               .values_list('persona__usuario_id', flat=True).first())
    return uid


@receiver(post_save, sender=Transaccion)
@receiver(post_delete, sender=Transaccion)
@receiver(post_save, sender=Deuda)
@receiver(post_delete, sender=Deuda)
@receiver(post_save, sender=PagoCuota)
@receiver(post_delete, sender=PagoCuota)
@receiver(post_save, sender=Persona)
@receiver(post_delete, sender=Persona)
@receiver(post_save, sender=Prestamo)
@receiver(post_delete, sender=Prestamo)
@receiver(post_save, sender=AbonoPrestamo)
@receiver(post_delete, sender=AbonoPrestamo)
def _al_cambiar(sender, instance, **kwargs):
    invalidar(_usuario_de(instance))
