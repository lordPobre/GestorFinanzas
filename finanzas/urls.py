from django.urls import path
from django.contrib.auth import views as auth_views
from . import google_login, views, views_cartola, views_cuenta, views_encuesta
from . import legal

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    path('cuotas/', views.deudas, name='deudas'),

    path('nueva-deuda/', views.crear_deuda, name='crear_deuda'),
    path('editar-deuda/<int:deuda_id>/', views.editar_deuda, name='editar_deuda'),
    path('pagar-cuota/<int:deuda_id>/', views.pagar_cuota, name='pagar_cuota'),
    path('anular-cuota/<int:deuda_id>/', views.anular_cuota, name='anular_cuota'),
    path('eliminar-deuda/<int:deuda_id>/', views.eliminar_deuda, name='eliminar_deuda'),

    path('registrar/', views.registrar_transaccion, name='registrar_transaccion'),
    path('registrar-ingreso/', views.registrar_ingreso, name='registrar_ingreso'),
    path('editar-transaccion/<int:transaccion_id>/', views.editar_transaccion, name='editar_transaccion'),
    path('eliminar-transaccion/<int:transaccion_id>/', views.eliminar_transaccion, name='eliminar_transaccion'),

    path('gasto/pagar/<int:transaccion_id>/', views.pagar_gasto, name='pagar_gasto'),
    path('gasto/anular-pago/<int:transaccion_id>/', views.anular_pago_gasto, name='anular_pago_gasto'),

    path('metas/', views.metas, name='metas'),
    path('meta/nueva/', views.crear_meta, name='crear_meta'),
    path('meta/aportar/<int:meta_id>/', views.aportar_meta, name='aportar_meta'),
    path('meta/editar/<int:meta_id>/', views.editar_meta, name='editar_meta'),
    path('meta/eliminar/<int:meta_id>/', views.eliminar_meta, name='eliminar_meta'),

    path('categorias/', views.categorias, name='categorias'),
    path('categorias/nueva/', views.crear_categoria, name='crear_categoria'),
    path('categorias/<int:cat_id>/editar/', views.editar_categoria, name='editar_categoria'),
    path('categorias/<int:cat_id>/eliminar/', views.eliminar_categoria, name='eliminar_categoria'),

    path('estadisticas/', views.estadisticas, name='estadisticas'),

    path('prestamos/', views.prestamos, name='prestamos'),
    path('prestamos/persona/nueva/', views.crear_persona, name='crear_persona'),
    path('prestamos/persona/<int:persona_id>/', views.detalle_persona, name='detalle_persona'),
    path('prestamos/persona/<int:persona_id>/eliminar/', views.eliminar_persona, name='eliminar_persona'),
    path('prestamos/persona/<int:persona_id>/nuevo/', views.crear_prestamo, name='crear_prestamo'),
    path('prestamos/abonar/<int:prestamo_id>/', views.abonar_prestamo, name='abonar_prestamo'),
    path('prestamos/eliminar/<int:prestamo_id>/', views.eliminar_prestamo, name='eliminar_prestamo'),

    path('analisis/', views.analisis_predictivo, name='analisis_predictivo'),
    path('analisis/ia/', views.analisis_ia, name='analisis_ia'),

    path('gasto-pendiente/nuevo/', views.crear_gasto_pendiente, name='crear_gasto_pendiente'),
    path('gasto-pendiente/pagar/<int:gasto_id>/', views.pagar_gasto_pendiente, name='pagar_gasto_pendiente'),
    path('gasto-pendiente/anular/<int:gasto_id>/', views.anular_gasto_pendiente, name='anular_gasto_pendiente'),
    path('gasto-pendiente/eliminar/<int:gasto_id>/', views.eliminar_gasto_pendiente, name='eliminar_gasto_pendiente'),

    path('exportar/', views.exportar_excel, name='exportar_excel'),
    path('exportar/csv/', views.exportar_csv, name='exportar_csv'),

    path('perfil/mis-datos/', views_cuenta.mis_datos, name='mis_datos'),
    path('perfil/eliminar-cuenta/', views_cuenta.eliminar_cuenta, name='eliminar_cuenta'),
    path('perfil/sesiones/', views_cuenta.sesiones_activas, name='sesiones_activas'),

    path('suscripciones/', views.suscripciones, name='suscripciones'),
    path('suscripciones/nueva/', views.crear_suscripcion, name='crear_suscripcion'),
    path('suscripciones/pagar/<int:sub_id>/', views.pagar_servicio, name='pagar_servicio'),
    path('suscripciones/anular-pago/<int:sub_id>/', views.anular_pago_servicio, name='anular_pago_servicio'),
    path('suscripciones/cancelar/<int:sub_id>/', views.cancelar_suscripcion, name='cancelar_suscripcion'),
    path('suscripciones/eliminar/<int:sub_id>/', views.eliminar_suscripcion, name='eliminar_suscripcion'),

    path('login/', views_cuenta.entrar, name='login'),

    path('entrar/google/', google_login.entrar_google, name='google_entrar'),
    path('entrar/google/listo/', google_login.google_listo, name='google_listo'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('verificar/', views_cuenta.verificar_codigo, name='verificar_codigo'),
    path('perfil/dos-pasos/', views_cuenta.configurar_2fa, name='configurar_2fa'),
    path('registro/', views_cuenta.registro, name='registro'),

    path('registro/confirmar/<str:token>/', views_cuenta.verificar_correo,
         name='verificar_correo'),
    path('perfil/reenviar-confirmacion/', views_cuenta.reenviar_verificacion,
         name='reenviar_verificacion'),

    path('recuperar/', views_cuenta.recuperar, name='recuperar'),
    path('recuperar/<uidb64>/<token>/', views_cuenta.restablecer, name='restablecer'),

    path('cartola/', views_cartola.importar_cartola, name='importar_cartola'),
    path('cartola/revisar/', views_cartola.revisar_cartola, name='revisar_cartola'),
    path('cartola/confirmar/', views_cartola.confirmar_cartola, name='confirmar_cartola'),
    path('cartola/descartar/', views_cartola.descartar_cartola, name='descartar_cartola'),

    path('perfil/', views_cuenta.perfil, name='perfil'),

    path('bienvenido/', views_cuenta.onboarding, name='onboarding'),
    path('bienvenido/completar/', views_cuenta.completar_onboarding, name='completar_onboarding'),

    path('sw.js', views.service_worker, name='service_worker'),

    path('salud/', views.salud, name='salud'),

    path('encuesta/', views_encuesta.encuesta, name='encuesta'),
    path('encuesta/despues/', views_encuesta.encuesta_posponer, name='encuesta_posponer'),
    path('encuesta/resultados/', views_encuesta.encuesta_resultados, name='encuesta_resultados'),

    path('privacidad/', legal.privacidad, name='privacidad'),
    path('terminos/', legal.terminos, name='terminos'),
]
