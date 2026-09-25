from django.contrib.auth import views as auth_views
from django.http import HttpResponseRedirect
from django.urls import path, reverse

from . import google_login, legal
from .views import (analisis, cartola, categorias, cuenta, cuotas, descargas,
                    encuesta, estadisticas, metas, movimientos, panel, passkeys, prestamos, sistema, suscripciones)


class RedireccionPermanente(HttpResponseRedirect):
    status_code = 308


def ruta_antigua(nombre):
    def vista(request, **kwargs):
        destino = reverse(nombre, kwargs=kwargs)
        consulta = request.META.get('QUERY_STRING', '')
        return RedireccionPermanente(f'{destino}?{consulta}' if consulta else destino)
    return vista


urlpatterns = [
    path('', panel.dashboard, name='dashboard'),

    path('cuotas/', cuotas.deudas, name='deudas'),
    path('cuotas/nueva/', cuotas.crear_deuda, name='crear_deuda'),
    path('cuotas/<int:deuda_id>/editar/', cuotas.editar_deuda, name='editar_deuda'),
    path('cuotas/<int:deuda_id>/pagar/', cuotas.pagar_cuota, name='pagar_cuota'),
    path('cuotas/<int:deuda_id>/anular-pago/', cuotas.anular_cuota, name='anular_cuota'),
    path('cuotas/<int:deuda_id>/eliminar/', cuotas.eliminar_deuda, name='eliminar_deuda'),

    path('movimientos/nuevo/', movimientos.registrar_transaccion, name='registrar_transaccion'),
    path('movimientos/nuevo-ingreso/', movimientos.registrar_ingreso, name='registrar_ingreso'),
    path('movimientos/<int:transaccion_id>/editar/', movimientos.editar_transaccion, name='editar_transaccion'),
    path('movimientos/<int:transaccion_id>/eliminar/', movimientos.eliminar_transaccion, name='eliminar_transaccion'),
    path('movimientos/<int:transaccion_id>/pagar/', movimientos.pagar_gasto, name='pagar_gasto'),
    path('movimientos/<int:transaccion_id>/anular-pago/', movimientos.anular_pago_gasto, name='anular_pago_gasto'),

    path('metas/', metas.metas, name='metas'),
    path('metas/nueva/', metas.crear_meta, name='crear_meta'),
    path('metas/<int:meta_id>/aportar/', metas.aportar_meta, name='aportar_meta'),
    path('metas/<int:meta_id>/editar/', metas.editar_meta, name='editar_meta'),
    path('metas/<int:meta_id>/eliminar/', metas.eliminar_meta, name='eliminar_meta'),

    path('categorias/', categorias.categorias, name='categorias'),
    path('categorias/nueva/', categorias.crear_categoria, name='crear_categoria'),
    path('categorias/<int:cat_id>/editar/', categorias.editar_categoria, name='editar_categoria'),
    path('categorias/<int:cat_id>/eliminar/', categorias.eliminar_categoria, name='eliminar_categoria'),

    path('estadisticas/', estadisticas.estadisticas, name='estadisticas'),

    path('prestamos/', prestamos.prestamos, name='prestamos'),
    path('prestamos/persona/nueva/', prestamos.crear_persona, name='crear_persona'),
    path('prestamos/persona/<int:persona_id>/', prestamos.detalle_persona, name='detalle_persona'),
    path('prestamos/persona/<int:persona_id>/eliminar/', prestamos.eliminar_persona, name='eliminar_persona'),
    path('prestamos/persona/<int:persona_id>/nuevo/', prestamos.crear_prestamo, name='crear_prestamo'),
    path('prestamos/<int:prestamo_id>/abonar/', prestamos.abonar_prestamo, name='abonar_prestamo'),
    path('prestamos/<int:prestamo_id>/eliminar/', prestamos.eliminar_prestamo, name='eliminar_prestamo'),

    path('analisis/', analisis.analisis_predictivo, name='analisis_predictivo'),
    path('analisis/ia/', analisis.analisis_ia, name='analisis_ia'),

    path('cuentas-por-pagar/nueva/', movimientos.crear_gasto_pendiente, name='crear_gasto_pendiente'),
    path('cuentas-por-pagar/<int:gasto_id>/pagar/', movimientos.pagar_gasto_pendiente, name='pagar_gasto_pendiente'),
    path('cuentas-por-pagar/<int:gasto_id>/anular-pago/', movimientos.anular_gasto_pendiente, name='anular_gasto_pendiente'),
    path('cuentas-por-pagar/<int:gasto_id>/eliminar/', movimientos.eliminar_gasto_pendiente, name='eliminar_gasto_pendiente'),

    path('exportar/', descargas.exportar_excel, name='exportar_excel'),
    path('exportar/csv/', descargas.exportar_csv, name='exportar_csv'),

    path('perfil/', cuenta.perfil, name='perfil'),
    path('perfil/mis-datos/', cuenta.mis_datos, name='mis_datos'),
    path('perfil/eliminar-cuenta/', cuenta.eliminar_cuenta, name='eliminar_cuenta'),
    path('perfil/sesiones/', cuenta.sesiones_activas, name='sesiones_activas'),
    path('perfil/dos-pasos/', cuenta.configurar_2fa, name='configurar_2fa'),
    path('perfil/face-id/', passkeys.passkeys, name='passkeys'),
    path('perfil/face-id/opciones/', passkeys.registro_opciones, name='passkey_registro_opciones'),
    path('perfil/face-id/verificar/', passkeys.registro_verificar, name='passkey_registro_verificar'),
    path('perfil/reenviar-confirmacion/', cuenta.reenviar_verificacion, name='reenviar_verificacion'),

    path('suscripciones/', suscripciones.suscripciones, name='suscripciones'),
    path('suscripciones/nueva/', suscripciones.crear_suscripcion, name='crear_suscripcion'),
    path('suscripciones/<int:sub_id>/pagar/', suscripciones.pagar_servicio, name='pagar_servicio'),
    path('suscripciones/<int:sub_id>/anular-pago/', suscripciones.anular_pago_servicio, name='anular_pago_servicio'),
    path('suscripciones/<int:sub_id>/cancelar/', suscripciones.cancelar_suscripcion, name='cancelar_suscripcion'),
    path('suscripciones/<int:sub_id>/eliminar/', suscripciones.eliminar_suscripcion, name='eliminar_suscripcion'),

    path('login/', cuenta.entrar, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('verificar/', cuenta.verificar_codigo, name='verificar_codigo'),
    path('entrar/google/', google_login.entrar_google, name='google_entrar'),
    path('entrar/google/listo/', google_login.google_listo, name='google_listo'),
    path('entrar/face-id/opciones/', passkeys.entrar_opciones, name='passkey_entrar_opciones'),
    path('entrar/face-id/verificar/', passkeys.entrar_verificar, name='passkey_entrar_verificar'),
    path('registro/', cuenta.registro, name='registro'),
    path('registro/confirmar/<str:token>/', cuenta.verificar_correo, name='verificar_correo'),
    path('recuperar/', cuenta.recuperar, name='recuperar'),
    path('recuperar/<uidb64>/<token>/', cuenta.restablecer, name='restablecer'),

    path('cartola/', cartola.importar_cartola, name='importar_cartola'),
    path('cartola/revisar/', cartola.revisar_cartola, name='revisar_cartola'),
    path('cartola/confirmar/', cartola.confirmar_cartola, name='confirmar_cartola'),
    path('cartola/descartar/', cartola.descartar_cartola, name='descartar_cartola'),

    path('bienvenido/', cuenta.onboarding, name='onboarding'),
    path('bienvenido/completar/', cuenta.completar_onboarding, name='completar_onboarding'),

    path('encuesta/', encuesta.encuesta, name='encuesta'),
    path('encuesta/despues/', encuesta.encuesta_posponer, name='encuesta_posponer'),
    path('encuesta/resultados/', encuesta.encuesta_resultados, name='encuesta_resultados'),

    path('privacidad/', legal.privacidad, name='privacidad'),
    path('terminos/', legal.terminos, name='terminos'),

    path('sw.js', sistema.service_worker, name='service_worker'),
    path('salud/', sistema.salud, name='salud'),
]

RUTAS_ANTIGUAS = [
    ('nueva-deuda/', 'crear_deuda'),
    ('editar-deuda/<int:deuda_id>/', 'editar_deuda'),
    ('pagar-cuota/<int:deuda_id>/', 'pagar_cuota'),
    ('anular-cuota/<int:deuda_id>/', 'anular_cuota'),
    ('eliminar-deuda/<int:deuda_id>/', 'eliminar_deuda'),

    ('registrar/', 'registrar_transaccion'),
    ('registrar-ingreso/', 'registrar_ingreso'),
    ('editar-transaccion/<int:transaccion_id>/', 'editar_transaccion'),
    ('eliminar-transaccion/<int:transaccion_id>/', 'eliminar_transaccion'),
    ('gasto/pagar/<int:transaccion_id>/', 'pagar_gasto'),
    ('gasto/anular-pago/<int:transaccion_id>/', 'anular_pago_gasto'),

    ('meta/nueva/', 'crear_meta'),
    ('meta/aportar/<int:meta_id>/', 'aportar_meta'),
    ('meta/editar/<int:meta_id>/', 'editar_meta'),
    ('meta/eliminar/<int:meta_id>/', 'eliminar_meta'),

    ('prestamos/abonar/<int:prestamo_id>/', 'abonar_prestamo'),
    ('prestamos/eliminar/<int:prestamo_id>/', 'eliminar_prestamo'),

    ('gasto-pendiente/nuevo/', 'crear_gasto_pendiente'),
    ('gasto-pendiente/pagar/<int:gasto_id>/', 'pagar_gasto_pendiente'),
    ('gasto-pendiente/anular/<int:gasto_id>/', 'anular_gasto_pendiente'),
    ('gasto-pendiente/eliminar/<int:gasto_id>/', 'eliminar_gasto_pendiente'),

    ('suscripciones/pagar/<int:sub_id>/', 'pagar_servicio'),
    ('suscripciones/anular-pago/<int:sub_id>/', 'anular_pago_servicio'),
    ('suscripciones/cancelar/<int:sub_id>/', 'cancelar_suscripcion'),
    ('suscripciones/eliminar/<int:sub_id>/', 'eliminar_suscripcion'),
]

urlpatterns += [path(ruta, ruta_antigua(nombre)) for ruta, nombre in RUTAS_ANTIGUAS]
