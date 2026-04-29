from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('nueva-deuda/', views.crear_deuda, name='crear_deuda'),
    path('editar-deuda/<int:deuda_id>/', views.editar_deuda, name='editar_deuda'),
    path('pagar-cuota/<int:deuda_id>/', views.pagar_cuota, name='pagar_cuota'),
    path('eliminar-deuda/<int:deuda_id>/', views.eliminar_deuda, name='eliminar_deuda'),
    path('registrar/', views.registrar_transaccion, name='registrar_transaccion'),
    path('registrar-ingreso/', views.registrar_ingreso, name='registrar_ingreso'),  # compatibilidad
    path('editar-transaccion/<int:transaccion_id>/', views.editar_transaccion, name='editar_transaccion'),
    path('eliminar-transaccion/<int:transaccion_id>/', views.eliminar_transaccion, name='eliminar_transaccion'),
    path('meta/nueva/', views.crear_meta, name='crear_meta'),
    path('meta/editar/<int:meta_id>/', views.editar_meta, name='editar_meta'),
    path('meta/eliminar/<int:meta_id>/', views.eliminar_meta, name='eliminar_meta'),
    path('estadisticas/', views.estadisticas, name='estadisticas'),
    path('exportar/', views.exportar_excel, name='exportar_excel'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('registro/', views.registro, name='registro'),
]
