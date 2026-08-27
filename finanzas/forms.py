"""Formularios de la app.

Los widgets NO llevan clases: el CSS estiliza por elemento
(`input`, `select`, `textarea`). Antes traían clases de Tailwind
(`w-full px-4 py-2 border rounded-lg focus:border-indigo-500`) que no existen
en este proyecto, así que los campos se veían sin estilo — el navegador les
daba su apariencia por defecto sobre un fondo oscuro.
"""
from datetime import date

from django import forms

from .models import Deuda, MetaAhorro, Transaccion


class DeudaForm(forms.ModelForm):
    """Una compra en cuotas."""

    class Meta:
        model = Deuda
        fields = ['acreedor', 'monto_total', 'categoria', 'cuotas_totales', 'fecha_inicio']
        labels = {
            'acreedor': '¿A quién le pagas?',
            'monto_total': 'Monto total de la compra',
            'cuotas_totales': '¿En cuántas cuotas?',
            'fecha_inicio': 'Fecha del primer pago',
        }
        help_texts = {
            'monto_total': 'El precio completo, no el valor de la cuota.',
            'fecha_inicio': 'El día del mes se toma de acá para todos los cobros.',
        }
        widgets = {
            'acreedor': forms.TextInput(attrs={'placeholder': 'Ej: Tarjeta Visa, Falabella'}),
            'monto_total': forms.NumberInput(attrs={'placeholder': '150000', 'min': '1', 'step': '1'}),
            'cuotas_totales': forms.NumberInput(attrs={'placeholder': '12', 'min': '1', 'max': '120'}),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo lo que se compra a plazo, y en ese orden.
        self.fields['categoria'].choices = Deuda.CATEGORIAS_CUOTAS
        if not self.instance.pk:
            self.fields['fecha_inicio'].initial = date.today()

    def clean_monto_total(self):
        monto = self.cleaned_data.get('monto_total')
        if monto is None or monto <= 0:
            raise forms.ValidationError('El monto tiene que ser mayor que cero.')
        return monto

    def clean_cuotas_totales(self):
        """cuotas_totales es un IntegerField sin validadores en el modelo, así
        que aceptaba 0 y negativos. Con 0 cuotas la deuda quedaba invisible:
        no generaba ningún mes de cobro."""
        n = self.cleaned_data.get('cuotas_totales')
        if n is None or n < 1:
            raise forms.ValidationError('Tiene que ser al menos 1 cuota.')
        if n > 120:
            raise forms.ValidationError('Máximo 120 cuotas (10 años).')
        return n

    def clean(self):
        datos = super().clean()
        monto = datos.get('monto_total')
        cuotas = datos.get('cuotas_totales')
        # Una cuota que no llega a $1 significa que los datos están al revés
        # (por ejemplo el monto de la cuota puesto como total).
        if monto and cuotas and monto / cuotas < 1:
            self.add_error('cuotas_totales',
                           'Con ese monto, cada cuota sería menos de $1. Revisa los datos.')
        return datos


class TransaccionForm(forms.ModelForm):
    """Un ingreso o un gasto del día a día."""

    fecha = forms.DateField(
        label='Fecha',
        input_formats=['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'],
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        help_text='Puedes anotar movimientos de días anteriores.',
    )

    class Meta:
        model = Transaccion
        fields = ['tipo', 'monto', 'categoria', 'descripcion', 'fecha']
        labels = {'monto': 'Monto', 'categoria': 'Categoría', 'descripcion': 'Descripción'}
        widgets = {
            'monto': forms.NumberInput(attrs={'placeholder': '50000', 'min': '1', 'step': '1'}),
            'descripcion': forms.TextInput(attrs={'placeholder': 'Ej: Supermercado, sueldo de agosto'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['descripcion'].required = False
        if not self.instance.pk and not self.initial.get('fecha'):
            self.fields['fecha'].initial = date.today()

    def clean_monto(self):
        monto = self.cleaned_data.get('monto')
        # min:0 en el widget dejaba pasar un gasto de $0, que no dice nada y
        # ensucia los promedios y la dona de categorías.
        if monto is None or monto <= 0:
            raise forms.ValidationError('El monto tiene que ser mayor que cero.')
        return monto

    def clean_fecha(self):
        fecha = self.cleaned_data.get('fecha')
        # Una fecha futura descuadra "lo que te queda este mes": el gasto
        # aparece contado en un mes que todavía no llega.
        if fecha and fecha > date.today():
            raise forms.ValidationError(
                'No puedes anotar un movimiento con fecha futura. '
                'Si es una cuenta por pagar, regístrala como gasto pendiente.')
        return fecha

    def clean(self):
        """Impide cruzar tipo y categoría.

        Antes se podía guardar un EGRESO con categoría 'Sueldo': la dona de
        gastos mostraba "Sueldo" como si fuera un gasto, y las estadísticas
        por categoría quedaban sin sentido.
        """
        datos = super().clean()
        tipo = datos.get('tipo')
        categoria = datos.get('categoria')
        if not tipo or not categoria:
            return datos

        de_ingreso = {c[0] for c in Transaccion.CATEGORIAS_INGRESO}
        de_egreso = {c[0] for c in Transaccion.CATEGORIAS_EGRESO}

        if tipo == 'INGRESO' and categoria in de_egreso:
            self.add_error('categoria', 'Esa categoría es de gastos. Elige de dónde viene el ingreso.')
        elif tipo == 'EGRESO' and categoria in de_ingreso:
            self.add_error('categoria', 'Esa categoría es de ingresos. Elige a qué gasto corresponde.')
        return datos


class MetaAhorroForm(forms.ModelForm):
    """Una meta de ahorro."""

    fecha_limite = forms.DateField(
        required=False,
        label='¿Para cuándo?',
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        help_text='Opcional. Con esto calculamos cuánto aportar al mes.',
    )

    class Meta:
        model = MetaAhorro
        fields = ['nombre', 'monto_meta', 'monto_actual', 'fecha_limite']
        labels = {
            'nombre': '¿Para qué ahorras?',
            'monto_meta': '¿Cuánto necesitas juntar?',
            'monto_actual': '¿Cuánto tienes ya?',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Fondo de emergencia, viaje'}),
            'monto_meta': forms.NumberInput(attrs={'placeholder': '500000', 'min': '1', 'step': '1'}),
            'monto_actual': forms.NumberInput(attrs={'placeholder': '0', 'min': '0', 'step': '1'}),
        }

    def clean_monto_meta(self):
        monto = self.cleaned_data.get('monto_meta')
        if monto is None or monto <= 0:
            raise forms.ValidationError('La meta tiene que ser mayor que cero.')
        return monto

    def clean_fecha_limite(self):
        fecha = self.cleaned_data.get('fecha_limite')
        if fecha and fecha <= date.today():
            raise forms.ValidationError('La fecha tiene que ser futura.')
        return fecha

    def clean(self):
        """Antes se podía tener $600.000 ahorrados sobre una meta de $500.000:
        la barra pasaba del 100% y el "te faltan" daba negativo."""
        datos = super().clean()
        meta = datos.get('monto_meta')
        actual = datos.get('monto_actual') or 0
        if meta and actual > meta:
            self.add_error('monto_actual',
                           'Ya tienes más que la meta. Sube la meta o baja este monto.')
        return datos
