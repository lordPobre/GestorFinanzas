from django.template.loaders import cached

PLANTILLAS = {
    'finanzas/base.html': 'finanzas/base_2c.html',
    'finanzas/prestamos.html': 'finanzas/prestamos_2c.html',
    'finanzas/metas.html': 'finanzas/metas_2c.html',
    'finanzas/plan.html': 'finanzas/plan_2c.html',
    'finanzas/estadisticas.html': 'finanzas/estadisticas_2c.html',
    'finanzas/analisis.html': 'finanzas/analisis_2c.html',
    'finanzas/perfil.html': 'finanzas/perfil_2c.html',
    'finanzas/categorias.html': 'finanzas/categorias_2c.html',
    'finanzas/importar_cartola.html': 'finanzas/importar_cartola_2c.html',
    'finanzas/clave_api.html': 'finanzas/clave_api_2c.html',
    'finanzas/form_transaccion.html': 'finanzas/form_transaccion_2c.html',
    'finanzas/form_suscripcion.html': 'finanzas/form_suscripcion_2c.html',
    'finanzas/editar_suscripcion.html': 'finanzas/editar_suscripcion_2c.html',
    'finanzas/onboarding.html': 'finanzas/onboarding_2c.html',
    'finanzas/repetidos.html': 'finanzas/repetidos_2c.html',
    'finanzas/landing.html': 'finanzas/landing_2c.html',
    'registration/login.html': 'registration/login_2c.html',
    'registration/auth_base.html': 'registration/auth_base_2c.html',
}


def plantilla(nombre):
    return PLANTILLAS.get(nombre, nombre)


class Cargador(cached.Loader):
    def get_template(self, template_name, skip=None):
        return super().get_template(plantilla(template_name), skip)
