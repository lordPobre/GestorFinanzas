from django.conf import settings
from django_q.models import Task
from django_q.tasks import async_task, fetch


def encolar(ruta, *args, **kwargs):
    return async_task(ruta, *args, **kwargs)


def resultado(tarea_id):
    tarea = fetch(tarea_id)
    if tarea is None:
        return {'listo': False}
    return {'listo': True, 'ok': tarea.success, 'resultado': tarea.result if tarea.success else None}



def recoger(tarea_id):
    estado = resultado(tarea_id)
    if estado['listo']:
        Task.objects.filter(id=tarea_id).delete()
    return estado


def sincronica():
    return bool(settings.Q_CLUSTER.get('sync'))


def latido():
    return 'ok'
