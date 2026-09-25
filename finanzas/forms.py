from datetime import date, timedelta
from decimal import Decimal

from django import forms

from .models import Categoria, Deuda, MetaAhorro, Transaccion

class DeudaForm(forms.ModelForm):
    valor_cuota = forms.DecimalField(
        label='Valor de cada cuota',
        max_digits=10, decimal_places=2, min_value=Decimal('1'),
        help_text='Lo que te cobran cada mes, no el precio total.',
        widget=forms.NumberInput(attrs={'placeholder': '12500', 'min': '1', 'step': '1'}),
    )

    field_order = ['acreedor', 'valor_cuota', 'cuotas_totales', 'fecha_inicio', 'categoria']

    class Meta:
        model = Deuda
        fields = ['acreedor', 'categoria', 'cuotas_totales', 'fecha_inicio']
        labels = {
            'acreedor': '¿A quién le pagas?',
            'cuotas_totales': '¿En cuántas cuotas?',
            'fecha_inicio': 'Fecha del primer pago',
        }
        help_texts = {
            'fecha_inicio': 'El día del mes se toma de acá para todos los cobros.',
        }
        widgets = {
            'acreedor': forms.TextInput(attrs={'placeholder': 'Ej: Tarjeta Visa, Falabella'}),
            'cuotas_totales': forms.NumberInput(attrs={'placeholder': '12', 'min': '1', 'max': '120'}),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    TOTAL_MAXIMO = Decimal('99999999')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].choices = Deuda.CATEGORIAS_CUOTAS
        if not self.instance.pk:
            self.fields['fecha_inicio'].initial = date.today()
        else:
            self.fields['valor_cuota'].initial = self.instance.monto_cuota

    def clean_valor_cuota(self):
        cuota = self.cleaned_data.get('valor_cuota')
        if cuota is None or cuota <= 0:
            raise forms.ValidationError('La cuota tiene que ser mayor que cero.')
        return cuota

    def clean_cuotas_totales(self):
        n = self.cleaned_data.get('cuotas_totales')
        if n is None or n < 1:
            raise forms.ValidationError('Tiene que ser al menos 1 cuota.')
        if n > 120:
            raise forms.ValidationError('Máximo 120 cuotas (10 años).')
        return n

    def clean(self):
        datos = super().clean()
        cuota = datos.get('valor_cuota')
        cuotas = datos.get('cuotas_totales')
        if cuota and cuotas:
            total = (cuota * cuotas).quantize(Decimal('1'))
            if total > self.TOTAL_MAXIMO:
                self.add_error('valor_cuota',
                               'Ese total es demasiado grande. Revisa la cuota y las cuotas.')
            else:
                datos['monto_total'] = total
        return datos

    def save(self, commit=True):
        deuda = super().save(commit=False)
        deuda.monto_total = (
            self.cleaned_data['valor_cuota'] * self.cleaned_data['cuotas_totales']
        ).quantize(Decimal('1'))
        if commit:
            deuda.save()
        return deuda

class TransaccionForm(forms.ModelForm):
    fecha = forms.DateField(
        label='Fecha',
        input_formats=['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'],
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        help_text='Días anteriores siempre. Un ingreso también puede ir a futuro.',
    )

    DIAS_FUTURO_INGRESO = 366

    class Meta:
        model = Transaccion
        fields = ['tipo', 'monto', 'categoria', 'descripcion', 'fecha']
        labels = {'monto': 'Monto', 'categoria': 'Categoría', 'descripcion': 'Descripción'}
        widgets = {
            'monto': forms.NumberInput(attrs={'placeholder': '50000', 'min': '1', 'step': '1'}),
            'descripcion': forms.TextInput(attrs={'placeholder': 'Ej: Supermercado, sueldo de agosto'}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['descripcion'].required = False
        if not self.instance.pk and not self.initial.get('fecha'):
            self.fields['fecha'].initial = date.today()

        self._usuario = usuario or getattr(self.instance, 'usuario_id', None) and self.instance.usuario
        if self._usuario:
            self.fields['categoria'].choices = Categoria.opciones(self._usuario)

    def clean_monto(self):
        monto = self.cleaned_data.get('monto')
        if monto is None or monto <= 0:
            raise forms.ValidationError('El monto tiene que ser mayor que cero.')
        return monto

    def clean(self):
        datos = super().clean()
        tipo = datos.get('tipo')
        categoria = datos.get('categoria')

        self._validar_fecha(datos.get('fecha'), tipo)

        if not tipo or not categoria:
            return datos

        de_ingreso = {c[0] for c in Transaccion.CATEGORIAS_INGRESO}
        de_egreso = {c[0] for c in Transaccion.CATEGORIAS_EGRESO}

        if getattr(self, '_usuario', None):
            propia = Categoria.objects.filter(
                usuario=self._usuario, slug=categoria).first()
            if propia:
                if propia.tipo != tipo:
                    self.add_error('categoria',
                                   'Esa categoría es de ' +
                                   ('ingresos' if propia.tipo == 'INGRESO' else 'gastos') + '.')
                return datos

        if tipo == 'INGRESO' and categoria in de_egreso:
            self.add_error('categoria', 'Esa categoría es de gastos. Elige de dónde viene el ingreso.')
        elif tipo == 'EGRESO' and categoria in de_ingreso:
            self.add_error('categoria', 'Esa categoría es de ingresos. Elige a qué gasto corresponde.')
        return datos

    def _validar_fecha(self, fecha, tipo):
        if not fecha or fecha <= date.today():
            return

        if tipo != 'INGRESO':
            self.add_error('fecha',
                           'Un gasto no se puede anotar con fecha futura. '
                           'Si es una cuenta por pagar, regístrala como gasto pendiente.')
            return

        if fecha > date.today() + timedelta(days=self.DIAS_FUTURO_INGRESO):
            self.add_error('fecha', 'Como máximo un año hacia adelante.')

class MetaAhorroForm(forms.ModelForm):
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
        datos = super().clean()
        meta = datos.get('monto_meta')
        actual = datos.get('monto_actual') or 0
        if meta and actual > meta:
            self.add_error('monto_actual',
                           'Ya tienes más que la meta. Sube la meta o baja este monto.')
        return datos
