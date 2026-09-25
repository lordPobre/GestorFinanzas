import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone

from .. import exportar


@login_required(login_url='/login/')
def exportar_excel(request):
    hoy = timezone.localdate()
    cuenta = request.user.get_username()

    try:
        contenido = exportar.libro_excel(request.user, cuenta, hoy)
    except ImportError:
        return exportar_csv(request)

    response = HttpResponse(
        contenido,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    archivo = f'Rekon_movimientos_{hoy:%Y-%m-%d}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{archivo}"'
    return response

@login_required(login_url='/login/')
def exportar_csv(request):
    hoy = timezone.localdate()
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    archivo = f'Rekon_movimientos_{hoy:%Y-%m-%d}.csv'
    response['Content-Disposition'] = f'attachment; filename="{archivo}"'
    exportar.escribir_csv(csv.writer(response, delimiter=';'),
                          request.user, request.user.get_username(), hoy)
    return response
