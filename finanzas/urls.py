from django.urls import path
from django.contrib.auth import views as auth_views
from . import google_login, legal
from .views import (analisis, cartola, categorias, cuenta, cuotas, descargas,
                    encuesta, estadisticas, metas, movimientos, panel, passkeys, prestamos, sistema, suscripciones)

urlpatterns = [
    path('', panel.dashboard, name='dashboard'),

    path('cuotas/', cuotas.deudas, name='deudas'),

    path('nueva-deuda/', cuotas.crear_deuda, name='crear_deuda'),
    path('editar-deuda/<int:deuda_id>/', cuotas.editar_deuda, name='editar_deuda'),
    path('pagar-cuota/<int:deuda_id>/', cuotas.pagar_cuota, name='pagar_cuota'),
    path('anular-cuota/<int:deuda_id>/', cuotas.anular_cuota, name='anular_cuota'),
    path('eliminar-deuda/<int:deuda_id>/', cuotas.eliminar_deuda, name='eliminar_deuda'),

    path('registrar/', movimientos.registrar_transaccion, name='registrar_transaccion'),
    path('registrar-ingreso/', movimientos.registrar_ingreso, name='registrar_ingreso'),
    path('editar-transaccion/<int:transaccion_id>/', movimientos.editar_transaccion, name='editar_transaccion'),
    path('eliminar-transaccion/<int:transaccion_id>/', movimientos.eliminar_transaccion, name='eliminar_transaccion'),

    path('gasto/pagar/<int:transaccion_id>/', movimientos.pagar_gasto, name='pagar_gasto'),
    path('gasto/anular-pago/<int:transaccion_id>/', movimientos.anular_pago_gasto, name='anular_pago_gasto'),

    path('metas/', metas.metas, name='metas'),
    path('meta/nueva/', metas.crear_meta, name='crear_meta'),
    path('meta/aportar/<int:meta_id>/', metas.aportar_meta, name='aportar_meta'),
    path('meta/editar/<int:meta_id>/', metas.editar_meta, name='editar_meta'),
    path('meta/eliminar/<int:meta_id>/', metas.eliminar_meta, name='eliminar_meta'),

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
    path('prestamos/abonar/<int:prestamo_id>/', prestamos.abonar_prestamo, name='abonar_prestamo'),
    path('prestamos/eliminar/<int:prestamo_id>/', prestamos.eliminar_prestamo, name='eliminar_prestamo'),

    path('analisis/', analisis.analisis_predictivo, name='analisis_predictivo'),
    path('analisis/ia/', analisis.analisis_ia, name='analisis_ia'),

    path('gasto-pendiente/nuevo/', movimientos.crear_gasto_pendiente, name='crear_gasto_pendiente'),
    path('gasto-pendiente/pagar/<int:gasto_id>/', movimientos.pagar_gasto_pendiente, name='pagar_gasto_pendiente'),
    path('gasto-pendiente/anular/<int:gasto_id>/', movimientos.anular_gasto_pendiente, name='anular_gasto_pendiente'),
    path('gasto-pendiente/eliminar/<int:gasto_id>/', movimientos.eliminar_gasto_pendiente, name='eliminar_gasto_pendiente'),

    path('exportar/', descargas.exportar_excel, name='exportar_excel'),
    path('exportar/csv/', descargas.exportar_csv, name='exportar_csv'),

    path('perfil/mis-datos/', cuenta.mis_datos, name='mis_datos'),
    path('perfil/eliminar-cuenta/', cuenta.eliminar_cuenta, name='eliminar_cuenta'),
    path('perfil/sesiones/', cuenta.sesiones_activas, name='sesiones_activas'),

    path('suscripciones/', suscripciones.suscripciones, name='suscripciones'),
    path('suscripciones/nueva/', suscripciones.crear_suscripcion, name='crear_suscripcion'),
    path('suscripciones/pagar/<int:sub_id>/', suscripciones.pagar_servicio, name='pagar_servicio'),
    path('suscripciones/anular-pago/<int:sub_id>/', suscripciones.anular_pago_servicio, name='anular_pago_servicio'),
    path('suscripciones/cancelar/<int:sub_id>/', suscripciones.cancelar_suscripcion, name='cancelar_suscripcion'),
    path('suscripciones/eliminar/<int:sub_id>/', suscripciones.eliminar_suscripcion, name='eliminar_suscripcion'),

    path('login/', cuenta.entrar, name='login'),

    path('entrar/google/', google_login.entrar_google, name='google_entrar'),
    path('entrar/google/listo/', google_login.google_listo, name='google_listo'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('verificar/', cuenta.verificar_codigo, name='verificar_codigo'),
    path('perfil/dos-pasos/', cuenta.configurar_2fa, name='configurar_2fa'),
    path('perfil/face-id/', passkeys.passkeys, name='passkeys'),
    path('perfil/face-id/opciones/', passkeys.registro_opciones, name='passkey_registro_opciones'),
    path('perfil/face-id/verificar/', passkeys.registro_verificar, name='passkey_registro_verificar'),
    path('entrar/face-id/opciones/', passkeys.entrar_opciones, name='passkey_entrar_opciones'),
    path('entrar/face-id/verificar/', passkeys.entrar_verificar, name='passkey_entrar_verificar'),
    path('registro/', cuenta.registro, name='registro'),

    path('registro/confirmar/<str:token>/', cuenta.verificar_correo,
         name='verificar_correo'),
    path('perfil/reenviar-confirmacion/', cuenta.reenviar_verificacion,
         name='reenviar_verificacion'),

    path('recuperar/', cuenta.recuperar, name='recuperar'),
    path('recuperar/<uidb64>/<token>/', cuenta.restablecer, name='restablecer'),

    path('cartola/', cartola.importar_cartola, name='importar_cartola'),
    path('cartola/revisar/', cartola.revisar_cartola, name='revisar_cartola'),
    path('cartola/confirmar/', cartola.confirmar_cartola, name='confirmar_cartola'),
    path('cartola/descartar/', cartola.descartar_cartola, name='descartar_cartola'),

    path('perfil/', cuenta.perfil, name='perfil'),

    path('bienvenido/', cuenta.onboarding, name='onboarding'),
    path('bienvenido/completar/', cuenta.completar_onboarding, name='completar_onboarding'),

    path('sw.js', sistema.service_worker, name='service_worker'),

    path('salud/', sistema.salud, name='salud'),

    path('encuesta/', encuesta.encuesta, name='encuesta'),
    path('encuesta/despues/', encuesta.encuesta_posponer, name='encuesta_posponer'),
    path('encuesta/resultados/', encuesta.encuesta_resultados, name='encuesta_resultados'),

    path('privacidad/', legal.privacidad, name='privacidad'),
    path('terminos/', legal.terminos, name='terminos'),
]
