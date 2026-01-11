from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('nueva-deuda/', views.crear_deuda, name='crear_deuda'),
    path('pagar-cuota/<int:deuda_id>/', views.pagar_cuota, name='pagar_cuota'),
    path('eliminar-deuda/<int:deuda_id>/', views.eliminar_deuda, name='eliminar_deuda'),
    path('registrar-ingreso/', views.registrar_ingreso, name='registrar_ingreso'),
    path('estadisticas/', views.estadisticas, name='estadisticas'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('registro/', views.registro, name='registro'),
]