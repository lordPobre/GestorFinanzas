"""Lo que se puede deducir de una descripción de cartola, sin IA.

Tres cosas, por orden de confianza:

1. Categoría — por palabra clave. Un comercio chileno se reconoce por su
   nombre: LIDER es comida, COPEC es transporte. Es un diccionario, no un
   modelo: se equivoca de forma predecible y se corrige agregando una línea.

2. Cuotas — por el patrón que el propio banco imprime: '03/12' al final de
   la descripción es la cuota 3 de 12.

3. Suscripciones — un PAC o PAT es recurrente por definición (así se llama
   el mandato de cobro automático). Y un comercio que ya cobró el mismo
   monto en meses anteriores lo es aunque no lleve PAC.

Todo esto se propone, no se aplica: la pantalla de revisión deja cambiarlo
antes de guardar.
"""
import re
from datetime import date
from decimal import Decimal

# Orden importante: gana la primera que calce, así que lo específico va
# antes que lo genérico ('uber eats' antes que 'uber').
REGLAS_EGRESO = [
    ('Comida',        ('lider', 'jumbo', 'santa isabel', 'tottus', 'unimarc',
                       'acuenta', 'mayorista', 'ekono', 'oxxo', 'pedidosya',
                       'uber eats', 'ubereats', 'rappi', 'justo', 'panaderia',
                       'carniceria', 'verduleria', 'feria', 'starbucks',
                       'provisiones', 'abarrotes', 'emporio', 'almacen',
                       'mcdonald', 'burger', 'doggis', 'juan maestro', 'sushi',
                       'restaurant', 'cafe ')),
    ('Transporte',    ('copec', 'shell', 'petrobras', 'aramco', 'terpel',
                       'uber', 'cabify', 'didi', 'beat', 'metro ', 'bip!',
                       'tag ', 'autopista', 'costanera norte', 'vespucio',
                       'peaje', 'estacionamiento', 'parking', 'rutapass',
                       'lubricantes', 'turbus',
                       'pullman', 'latam', 'sky airline', 'jetsmart')),
    ('Servicios',     ('enel', 'cge', 'saesa', 'frontel', 'chilquinta',
                       'aguas andinas', 'essbio', 'esval', 'nuevosur',
                       'aguas del valle', 'smapa', 'metrogas', 'lipigas',
                       'abastible', 'gasco', 'entel', 'movistar', 'wom',
                       'claro', 'vtr', 'mundo', 'gtd', 'servipag',
                       'sencillito', 'contribuciones', 'tesoreria',
                       'patente', 'permiso de circulacion')),
    # No hay categoría "Suscripciones" en Transaccion.CATEGORIAS, así que las
    # recurrentes se reparten entre las que sí existen: lo que se ve o se
    # escucha va a Ocio, las herramientas a Tecnología. La marca de "se repite
    # cada mes" la pone es_suscripcion, no la categoría.
    ('Ocio',          ('netflix', 'spotify', 'disney', 'star+', 'hbo', 'max ',
                       'prime video', 'youtube', 'crunchyroll', 'paramount',
                       'directv', 'apple tv')),
    ('Tecnologia',    ('apple.com', 'itunes', 'icloud', 'google', 'microsoft',
                       'office', 'adobe', 'canva', 'dropbox', 'notion',
                       'openai', 'chatgpt', 'anthropic', 'claude', 'github',
                       'zoom', 'linkedin')),
    ('Salud',         ('cruz verde', 'salcobrand', 'ahumada', 'farmacia',
                       'dr simi', 'isapre', 'fonasa', 'banmedica', 'consalud',
                       'cruz blanca', 'nueva masvida', 'clinica', 'hospital',
                       'integramedica', 'megasalud', 'dental', 'optica', 'europtica',
                       'laboratorio')),
    ('Compras',       ('falabella', 'ripley', 'paris', 'hites', 'la polar',
                       'abcdin', 'corona', 'tricot', 'sodimac', 'easy',
                       'construmart', 'imperial', 'pc factory', 'spdigital',
                       'mercadolibre', 'mercado libre', 'mercado pago',
                       'aliexpress', 'amazon', 'temu', 'shein', 'ebay',
                       'merpago', 'mp *', 'webpay', 'sumup', 'redgloba')),
    ('Ocio',          ('cinemark', 'cineplanet', 'cinehoyts', 'steam',
                       'playstation', 'xbox', 'nintendo', 'riot', 'epic games',
                       'ticketmaster', 'puntoticket', 'punto ticket', 'passline',
                       'zapping', 'gimnasio',
                       'smartfit', 'energy fitness', 'pub', 'bar ')),
    ('Educacion',     ('universidad', 'instituto', 'duoc', 'inacap', 'colegio',
                       'jardin infantil', 'preuniversitario', 'udemy',
                       'coursera', 'platzi', 'matricula', 'arancel')),
    ('Hogar',         ('homecenter', 'casaideas', 'ikea', 'rosen', 'cic',
                       'ferreteria', 'maderas',
                       'arriendo', 'gastos comunes', 'administracion edificio')),
    ('Ropa',          ('zara', 'h&m', 'forever', 'nike', 'adidas', 'puma',
                       'dafiti', 'lippi', 'doite', 'columbia')),
    ('Viajes',        ('booking', 'airbnb', 'despegar', 'expedia', 'hotel ',
                       'hostal', 'cabañas')),
    ('Tecnologia',    ('pcfactory', 'pc factory', 'winpy', 'solotodo',
                       'samsung', 'xiaomi', 'huawei', 'apple store')),
]

REGLAS_INGRESO = [
    ('Sueldo',        ('remuneracion', 'remuneraciones', 'sueldo', 'haberes',
                       'liquidacion', 'nomina')),
    ('Bono',          ('bono', 'aguinaldo', 'gratificacion', 'ips ', 'aporte fiscal')),
    ('Transferencia', ('transf. de', 'transf de', 'transferencia desde',
                       'transferencia de', 'abono por transferencia')),
    ('Venta',         ('venta', 'devolucion', 'reembolso', 'reverso')),
]

# Movimientos que no son ni gasto ni ingreso de verdad: mueven plata entre
# bolsillos del mismo dueño. Se importan igual, pero conviene avisar.
TRASPASOS = ('pago tarjeta', 'pago de tarjeta', 'traspaso', 'entre cuentas',
             'a cuenta propia', 'pac ahorro', 'deposito a plazo', 'fondo mutuo')

# La cuota que el banco imprime: 'C03/12', 'CUOTA 3 DE 12', '03/12'.
CUOTA_EXPLICITA = re.compile(r'cuotas?\s*:?\s*(\d{1,2})\s*(?:/|de)\s*(\d{1,2})', re.I)
CUOTA_AL_FINAL = re.compile(r'\b0?(\d{1,2})\s*/\s*(\d{1,2})\s*$')

# Mandato de cobro automático: PAC (cuentas) y PAT (tarjeta). Es la señal más
# fuerte, pero solo existe en cartolas de cuenta corriente: en un estado de
# cuenta de tarjeta las suscripciones llegan como una compra más.
RECURRENTE = re.compile(r'^\s*(pac|pat)\b', re.I)

# Por eso hace falta reconocerlas por la marca. Es la única señal disponible
# el primer mes, cuando todavía no hay historial contra el cual comparar.
MARCAS_RECURRENTES = (
    'netflix', 'spotify', 'disney', 'star+', 'prime video', 'youtube',
    'crunchyroll', 'paramount', 'directv', 'zapping', 'pluto',
    'apple.com', 'itunes', 'icloud', 'apple tv', 'google one',
    'microsoft', 'office 365', 'adobe', 'canva', 'dropbox', 'notion',
    'openai', 'chatgpt', 'anthropic', 'claude', 'github', 'zoom',
    'linkedin', 'playstation', 'xbox', 'nintendo', 'duolingo',
    'seguro', 'isapre', 'gimnasio', 'smartfit',
)

# Nombres cortos que solo valen como palabra entera: 'max' dentro de
# 'Maxi Market' no es HBO Max.
MARCAS_EXACTAS = re.compile(r'\b(max|hbo|plex|mubi|meli\+|spot)\b', re.I)


def _clave(desc):
    """Nombre del comercio, normalizado para poder compararlo entre meses.

    'REDCOMPRA LIDER 4521 SANTIAGO' y 'REDCOMPRA LIDER 8890 MAIPU' son el
    mismo comercio: sin quitar los números nunca se agruparían.
    """
    d = desc.lower()
    d = re.sub(r'\b(redcompra|compra|pago|pac|pat|internet|web|chl|cl)\b', ' ', d)
    d = re.sub(r'\d+', ' ', d)
    return ' '.join(d.split())[:40]


def categoria_de(desc, tipo):
    d = desc.lower()
    reglas = REGLAS_INGRESO if tipo == 'INGRESO' else REGLAS_EGRESO
    for categoria, claves in reglas:
        if any(k in d for k in claves):
            return categoria
    if tipo == 'EGRESO' and ('giro' in d or 'cajero' in d):
        return 'Otros'
    return 'Otros_Ingresos' if tipo == 'INGRESO' else 'Otros'


def cuotas_de(desc):
    """(cuota_actual, cuota_total) o (0, 0).

    Conservador a propósito: '03/12' también puede ser una fecha. Solo se
    acepta cuando la palabra 'cuota' está al lado, o cuando el patrón cierra
    la descripción — que es donde el banco lo imprime.
    """
    m = CUOTA_EXPLICITA.search(desc) or CUOTA_AL_FINAL.search(desc)
    if not m:
        return 0, 0
    actual, total = int(m.group(1)), int(m.group(2))
    if 2 <= total <= 48 and 1 <= actual <= total:
        return actual, total
    return 0, 0


def enriquecer(cartola, usuario):
    """Rellena categoría, cuotas, suscripción y duplicados. Modifica en sitio."""
    from finanzas.models import Transaccion

    movs = cartola.movimientos
    if not movs:
        return cartola

    # --- Duplicados -------------------------------------------------
    # Se compara contra lo que ya está en la base en el mismo rango de
    # fechas. Se cuenta en vez de solo preguntar si existe: dos
    # transferencias iguales el mismo día son dos movimientos reales, no
    # una repetida, y marcar la segunda como duplicada la haría desaparecer.
    desde, hasta = min(m.fecha for m in movs), max(m.fecha for m in movs)
    ya_en_base = {}
    for t in Transaccion.objects.filter(usuario=usuario, fecha__range=(desde, hasta)):
        k = (t.fecha, t.tipo, Decimal(t.monto), (t.descripcion or '').strip().lower())
        ya_en_base[k] = ya_en_base.get(k, 0) + 1

    # --- Recurrencia ------------------------------------------------
    # Un comercio que ya cobró antes de este período es una suscripción
    # aunque la línea no diga PAC.
    # Un comercio que cobró en dos meses distintos ya es recurrente, aunque el
    # monto cambie: las suscripciones suben de precio y comparar por monto
    # exacto las perdía justo el mes del alza.
    meses_por_comercio = {}
    for t in Transaccion.objects.filter(
            usuario=usuario, tipo='EGRESO', fecha__lt=desde).order_by('-fecha')[:400]:
        k = _clave(t.descripcion or '')
        if k:
            meses_por_comercio.setdefault(k, set()).add((t.fecha.year, t.fecha.month))

    vistos_en_cartola = {}

    for m in movs:
        m.categoria = categoria_de(m.descripcion, m.tipo)
        # Solo si el parser no las trajo ya. Un estado de cuenta de tarjeta
        # tiene la columna de cuotas impresa y es más fiable que adivinarla
        # desde el texto del comercio.
        if not m.cuota_total:
            m.cuota_actual, m.cuota_total = cuotas_de(m.descripcion)

        if m.es_cuota and m.categoria == 'Otros':
            m.categoria = 'Compras'

        if m.tipo == 'EGRESO':
            bajo_desc = m.descripcion.lower()
            m.es_suscripcion = not m.es_cuota and (
                # Cobro automático declarado por el banco.
                bool(RECURRENTE.match(m.descripcion))
                # O una marca que se paga todos los meses.
                or any(k in bajo_desc for k in MARCAS_RECURRENTES)
                or bool(MARCAS_EXACTAS.search(m.descripcion))
                # O ya cobró en dos meses anteriores distintos.
                or len(meses_por_comercio.get(_clave(m.descripcion), ())) >= 2
            )
            if m.es_suscripcion and m.categoria == 'Otros':
                m.categoria = 'Servicios'

        k = (m.fecha, m.tipo, m.monto, m.descripcion.strip().lower())
        vistos_en_cartola[k] = vistos_en_cartola.get(k, 0) + 1
        # Solo se marcan tantas repeticiones como ya haya en la base: si la
        # cartola trae dos y la base tiene una, la segunda entra.
        if vistos_en_cartola[k] <= ya_en_base.get(k, 0):
            m.ya_existe = True

        bajo = m.descripcion.lower()
        if not m.aviso and any(t in bajo for t in TRASPASOS):
            m.aviso = 'Parece plata que moviste entre tus propias cuentas.'

    return cartola
