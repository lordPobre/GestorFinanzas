from django import forms
from .models import Deuda, Transaccion, MetaAhorro

class DeudaForm(forms.ModelForm):
    class Meta:
        model = Deuda
        fields = ['acreedor', 'monto_total', 'categoria', 'cuotas_totales', 'fecha_inicio']
        widgets = {
            'acreedor': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500',
                'placeholder': 'Ej: Tarjeta Visa'
            }),
            'monto_total': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500',
                'placeholder': '150000'
            }),
            'categoria': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500'
            }),
            'cuotas_totales': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500',
                'placeholder': '12',
                'min': '1'
            }),
            'fecha_inicio': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500',
                'type': 'date'
            }),
        }


class TransaccionForm(forms.ModelForm):
    """Formulario unificado para ingresos Y egresos manuales"""
    fecha = forms.DateField(
        input_formats=['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'],
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500',
            'type': 'date'
        })
    )

    class Meta:
        model = Transaccion
        fields = ['tipo', 'monto', 'categoria', 'descripcion', 'fecha']
        widgets = {
            'tipo': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500'
            }),
            'monto': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500',
                'placeholder': 'Ej: 50000',
                'min': '0',
                'step': '1'
            }),
            'categoria': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500'
            }),
            'descripcion': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500',
                'placeholder': 'Ej: Sueldo enero, Supermercado...'
            }),
        }


# Mantenemos IngresoForm por compatibilidad (redirige a TransaccionForm pre-seleccionado)
class IngresoForm(forms.ModelForm):
    fecha = forms.DateField(
        input_formats=['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'],
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500',
            'type': 'date'
        })
    )

    class Meta:
        model = Transaccion
        fields = ['monto', 'descripcion', 'fecha']
        widgets = {
            'monto': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500',
                'placeholder': 'Ej: 1500000'
            }),
            'descripcion': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500',
                'placeholder': 'Ej: Sueldo Enero, Venta Freelance...'
            }),
        }


class MetaAhorroForm(forms.ModelForm):
    fecha_limite = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-pink-500',
            'type': 'date'
        })
    )

    class Meta:
        model = MetaAhorro
        fields = ['nombre', 'monto_meta', 'monto_actual', 'fecha_limite']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-pink-500',
                'placeholder': 'Ej: Fondo de Emergencia, PS5, Viaje...'
            }),
            'monto_meta': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-pink-500',
                'placeholder': 'Ej: 500000'
            }),
            'monto_actual': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-pink-500',
                'placeholder': 'Ej: 50000 (Opcional, con cuanto empiezas)'
            }),
        }
