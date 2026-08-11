from django.contrib import admin
from .models import Transaccion, Deuda

@admin.action(description='Marcar seleccionados como CUOTA (es_cuota = True)')
def marcar_como_cuota(modeladmin, request, queryset):
    # Esto actualiza todos los seleccionados de golpe en la base de datos
    queryset.update(es_cuota=True)

# Opcional: Creamos la función inversa por si te equivocas
@admin.action(description='Desmarcar como CUOTA (es_cuota = False)')
def desmarcar_como_cuota(modeladmin, request, queryset):
    queryset.update(es_cuota=False)

@admin.register(Transaccion)
class TransaccionAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'monto', 'tipo', 'fecha', 'es_cuota')
    list_filter = ('es_cuota', 'tipo', 'fecha')
    search_fields = ('descripcion',) # Añadimos buscador para encontrar rápido "Cuota"
    
    # 2. Registramos las acciones en el panel
    actions = [marcar_como_cuota, desmarcar_como_cuota]

admin.site.register(Deuda)