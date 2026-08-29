"""Panel de administración.

Antes solo estaban registrados Transaccion y Deuda, así que los modelos
nuevos (pagos, préstamos, suscripciones) no se podían revisar ni corregir
desde el admin cuando algo salía mal en producción.
"""
from django.contrib import admin

from .models import (AbonoPrestamo, AporteMeta, Categoria, Deuda, GastoPendiente,
                     MetaAhorro, PagoCuota, PagoServicio, Persona, Prestamo,
                     Presupuesto, Suscripcion, Transaccion, UserProfile)


class PagoCuotaInline(admin.TabularInline):
    model = PagoCuota
    extra = 0
    fields = ('periodo', 'monto', 'fecha_pago', 'transaccion')
    ordering = ('periodo',)


@admin.register(Deuda)
class DeudaAdmin(admin.ModelAdmin):
    list_display = ('acreedor', 'usuario', 'monto_total', 'cuotas_pagadas',
                    'cuotas_totales', 'fecha_inicio', 'estado')
    list_filter = ('usuario', 'categoria', 'fecha_inicio')
    search_fields = ('acreedor',)
    inlines = [PagoCuotaInline]
    actions = ['sincronizar_contador']

    @admin.display(description='Estado')
    def estado(self, obj):
        if obj.esta_saldada:
            return 'Saldada'
        atrasadas = len(obj.periodos_atrasados)
        if atrasadas:
            return f'{atrasadas} atrasada(s)'
        return f'{obj.cuotas_restantes} por pagar'

    @admin.action(description='Recalcular cuotas_pagadas desde los pagos registrados')
    def sincronizar_contador(self, request, queryset):
        corregidas = 0
        for deuda in queryset:
            real = deuda.pagos.count()
            if deuda.cuotas_pagadas != real:
                deuda.cuotas_pagadas = real
                deuda.save(update_fields=['cuotas_pagadas'])
                corregidas += 1
        self.message_user(request, f'{corregidas} deuda(s) corregida(s).')


@admin.register(PagoCuota)
class PagoCuotaAdmin(admin.ModelAdmin):
    list_display = ('deuda', 'etiqueta_mes', 'monto', 'fecha_pago', 'fue_atrasado')
    list_filter = ('deuda__usuario', 'periodo')
    search_fields = ('deuda__acreedor',)


@admin.register(Transaccion)
class TransaccionAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'descripcion', 'monto', 'tipo', 'categoria',
                    'es_cuota', 'pagado', 'usuario')
    list_filter = ('tipo', 'es_cuota', 'pagado', 'categoria', 'usuario', 'fecha')
    search_fields = ('descripcion',)
    date_hierarchy = 'fecha'
    actions = ['marcar_pagado', 'marcar_sin_pagar']


    @admin.action(description='Marcar como pagado')
    def marcar_pagado(self, request, queryset):
        from django.utils import timezone
        n = queryset.filter(tipo='EGRESO', es_cuota=False).update(
            pagado=True, fecha_pago=timezone.localdate())
        self.message_user(request, f'{n} gasto(s) marcado(s) como pagados.')

    @admin.action(description='Marcar como NO pagado')
    def marcar_sin_pagar(self, request, queryset):
        n = queryset.filter(tipo='EGRESO', es_cuota=False).update(
            pagado=False, fecha_pago=None)
        self.message_user(request, f'{n} gasto(s) marcado(s) como no pagados.')


class PagoServicioInline(admin.TabularInline):
    model = PagoServicio
    extra = 0
    ordering = ('periodo',)


@admin.register(Suscripcion)
class SuscripcionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'monto', 'dia_cobro', 'activa',
                    'ultimo_mes_generado', 'estado_mes')
    list_filter = ('activa', 'usuario', 'categoria')
    search_fields = ('nombre',)
    inlines = [PagoServicioInline]


class PrestamoInline(admin.TabularInline):
    model = Prestamo
    extra = 0
    fields = ('descripcion', 'monto', 'tipo', 'cuotas_totales', 'fecha')


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'total_prestado', 'total_pendiente')
    list_filter = ('usuario',)
    search_fields = ('nombre', 'contacto')
    inlines = [PrestamoInline]


class AbonoInline(admin.TabularInline):
    model = AbonoPrestamo
    extra = 0


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'persona', 'monto', 'tipo',
                    'monto_pendiente', 'esta_pagado')
    list_filter = ('tipo', 'persona__usuario')
    search_fields = ('descripcion', 'persona__nombre')
    inlines = [AbonoInline]


@admin.register(GastoPendiente)
class GastoPendienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'monto', 'fecha_vencimiento', 'pagado')
    list_filter = ('pagado', 'usuario')
    search_fields = ('nombre',)


class AporteInline(admin.TabularInline):
    model = AporteMeta
    extra = 0


@admin.register(MetaAhorro)
class MetaAhorroAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'monto_actual', 'monto_meta', 'fecha_limite')
    list_filter = ('usuario',)
    inlines = [AporteInline]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'nombre_completo', 'moneda', 'onboarding_completado')
    list_filter = ('moneda', 'onboarding_completado')
    search_fields = ('usuario__username', 'nombre_completo')


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'usuario', 'tipo', 'slug', 'color', 'activa')
    list_filter = ('tipo', 'activa', 'usuario')
    search_fields = ('nombre', 'slug')
    prepopulated_fields = {'slug': ('nombre',)}


admin.site.register(Presupuesto)

admin.site.site_header = 'FinApp — administración'
admin.site.site_title = 'FinApp'
admin.site.index_title = 'Datos de la aplicación'
