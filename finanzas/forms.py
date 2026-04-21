from django import forms
from .models import Deuda, Transaccion, MetaAhorro

class DeudaForm(forms.ModelForm):
    class Meta:
        model = Deuda
        # 1. Agregamos 'categoria' a la lista de fields
        fields = ['acreedor', 'monto_total', 'categoria', 'cuotas_totales', 'fecha_inicio']
        
        # Aquí le damos el estilo moderno a los inputs
        widgets = {
            'acreedor': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500', 
                'placeholder': 'Ej: Tarjeta Visa'
            }),
            'monto_total': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500',
                'placeholder': '150000'
            }),
            # 2. Agregamos el widget (diseño) para el menú desplegable de categoría
            'categoria': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500'
            }),
            'cuotas_totales': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500',
                'placeholder': '12'
            }),
            'fecha_inicio': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500',
                'type': 'date' # Esto activa el selector de calendario
            }),
        }


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
                'placeholder': 'Ej: 1500.00'
            }),
            'descripcion': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:border-indigo-500',
                'placeholder': 'Ej: Sueldo Enero, Venta Freelance...'
            }),
        }

class MetaAhorroForm(forms.ModelForm):
    class Meta:
        model = MetaAhorro
        fields = ['nombre', 'monto_meta', 'monto_actual']
        
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
                'placeholder': 'Ej: 50000 (Opcional, con cuánto empiezas)'
            }),
        }