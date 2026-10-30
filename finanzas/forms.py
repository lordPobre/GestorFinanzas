from datetime import timedelta
from decimal import Decimal

from django import forms
from django.db.models import F, Q

from . import fechas
from .models import Categoria, Deuda, MetaAhorro, Transaccion


class MontoInput(forms.NumberInput):
    def format_value(self, value):
        if isinstance(value, Decimal) and value == value.to_integral_value():
            value = value.quantize(Decimal('1'))
        return super().format_value(value)


class DeudaForm(forms.ModelForm):
    valor_cuota = forms.DecimalField(
        label='Valor de cada cuota',
        max_digits=10, decimal_places=2, min_value=Decimal('1'),
        help_text='Lo que te cobran cada mes, no el precio total.',
        widget=MontoInput(attrs={'placeholder': '12500', 'min': '1', 'step': '1'}),
    )

    categoria = forms.ChoiceField(label='Categoría')

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

    def __init__(self, *args, usuario=None, opciones=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].choices = (opciones if opciones is not None
                                            else (lambda: Categoria.opciones(usuario, 'EGRESO')))
        self.initial.setdefault('categoria', self.instance.categoria)
        if not self.instance.pk:
            self.fields['fecha_inicio'].initial = fechas.hoy()
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

    def _post_clean(self):
        super()._post_clean()
        if self.cleaned_data.get('categoria'):
            self.instance.categoria = self.cleaned_data['categoria']

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
        help_text='Días anteriores siempre. Un ingreso o un gasto que aún debes también puede ir a futuro.',
    )

    categoria = forms.ChoiceField(label='Categoría')

    DIAS_FUTURO_INGRESO = 366

    class Meta:
        model = Transaccion
        fields = ['tipo', 'monto', 'categoria', 'descripcion', 'fecha']
        labels = {'monto': 'Monto', 'categoria': 'Categoría', 'descripcion': 'Descripción'}
        widgets = {
            'monto': MontoInput(attrs={'placeholder': '50000', 'min': '1', 'step': '1'}),
            'descripcion': forms.TextInput(attrs={'placeholder': 'Ej: Supermercado, sueldo de agosto'}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['descripcion'].required = False
        if not self.instance.pk and not self.initial.get('fecha'):
            self.fields['fecha'].initial = fechas.hoy()

        self._usuario = usuario or getattr(self.instance, 'usuario_id', None) and self.instance.usuario
        dueno = self._usuario or None
        self.fields['categoria'].choices = lambda: Categoria.opciones(dueno)
        self.initial.setdefault('categoria', self.instance.categoria)

    def _post_clean(self):
        super()._post_clean()
        if self.cleaned_data.get('categoria'):
            self.instance.categoria = self.cleaned_data['categoria']

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

        cat = (Categoria.objects
               .filter(Q(usuario=self._usuario or None) | Q(usuario__isnull=True), slug=categoria)
               .order_by(F('usuario_id').asc(nulls_last=True)).first())
        if cat is None or cat.tipo == tipo:
            return datos

        if not cat.es_base:
            self.add_error('categoria', 'Esa categoría es de ' +
                           ('ingresos' if cat.tipo == 'INGRESO' else 'gastos') + '.')
        elif tipo == 'INGRESO':
            self.add_error('categoria', 'Esa categoría es de gastos. Elige de dónde viene el ingreso.')
        else:
            self.add_error('categoria', 'Esa categoría es de ingresos. Elige a qué gasto corresponde.')
        return datos

    def _queda_pendiente(self):
        return bool(self.data.get('es_pendiente') or self.data.get('sin_pagar'))

    def _validar_fecha(self, fecha, tipo):
        if not fecha or fecha <= fechas.hoy():
            return

        if tipo != 'INGRESO' and not self._queda_pendiente():
            self.add_error('fecha',
                           'Un gasto ya pagado no puede tener fecha futura. '
                           'Si lo pagas más adelante, marca «Aún la debo».')
            return

        if fecha > fechas.hoy() + timedelta(days=self.DIAS_FUTURO_INGRESO):
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
            'monto_meta': MontoInput(attrs={'placeholder': '500000', 'min': '1', 'step': '1'}),
            'monto_actual': MontoInput(attrs={'placeholder': '0', 'min': '0', 'step': '1'}),
        }

    def clean_monto_meta(self):
        monto = self.cleaned_data.get('monto_meta')
        if monto is None or monto <= 0:
            raise forms.ValidationError('La meta tiene que ser mayor que cero.')
        return monto

    def clean_fecha_limite(self):
        fecha = self.cleaned_data.get('fecha_limite')
        if fecha and fecha <= fechas.hoy():
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
