from django.contrib import admin

from .models import EventoSeguridad


@admin.register(EventoSeguridad)
class EventoSeguridadAdmin(admin.ModelAdmin):
    list_display = ('creado', 'tipo', 'referencia', 'ip', 'detalle')
    list_filter = ('tipo',)
    search_fields = ('referencia', 'ip')
    date_hierarchy = 'creado'
    readonly_fields = [f.name for f in EventoSeguridad._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
