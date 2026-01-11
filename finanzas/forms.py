from django import forms
from .models import Deuda, Transaccion

class DeudaForm(forms.ModelForm):
    class Meta:
        model = Deuda
        fields = ['acreedor', 'monto_total', 'cuotas_totales', 'fecha_inicio']
        
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
        fields = ['monto', 'descripcion', 'fecha'] # No pedimos 'tipo' ni 'usuario', eso lo ponemos nosotros
        
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