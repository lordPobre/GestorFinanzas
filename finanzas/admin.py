from django.contrib import admin
from .models import Transaccion, Deuda

admin.site.register(Transaccion)
admin.site.register(Deuda)