import re
from decimal import Decimal

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

TRASPASOS = ('pago tarjeta', 'pago de tarjeta', 'traspaso', 'entre cuentas',
             'a cuenta propia', 'pac ahorro', 'deposito a plazo', 'fondo mutuo')

CUOTA_EXPLICITA = re.compile(r'cuotas?\s*:?\s*(\d{1,2})\s*(?:/|de)\s*(\d{1,2})', re.I)
CUOTA_AL_FINAL = re.compile(r'\b0?(\d{1,2})\s*/\s*(\d{1,2})\s*$')

RECURRENTE = re.compile(r'^\s*(pac|pat)\b', re.I)

MARCAS_RECURRENTES = (
    'netflix', 'spotify', 'disney', 'star+', 'prime video', 'youtube',
    'crunchyroll', 'paramount', 'directv', 'zapping', 'pluto',
    'apple.com', 'itunes', 'icloud', 'apple tv', 'google one',
    'microsoft', 'office 365', 'adobe', 'canva', 'dropbox', 'notion',
    'openai', 'chatgpt', 'anthropic', 'claude', 'github', 'zoom',
    'linkedin', 'playstation', 'xbox', 'nintendo', 'duolingo',
    'seguro', 'isapre', 'gimnasio', 'smartfit',
)

MARCAS_EXACTAS = re.compile(r'\b(max|hbo|plex|mubi|meli\+|spot)\b', re.I)


def _clave(desc):
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
    m = CUOTA_EXPLICITA.search(desc) or CUOTA_AL_FINAL.search(desc)
    if not m:
        return 0, 0
    actual, total = int(m.group(1)), int(m.group(2))
    if 2 <= total <= 48 and 1 <= actual <= total:
        return actual, total
    return 0, 0


def enriquecer(cartola, usuario):
    from finanzas.models import Transaccion

    movs = cartola.movimientos
    if not movs:
        return cartola

    desde, hasta = min(m.fecha for m in movs), max(m.fecha for m in movs)
    ya_en_base = {}
    for t in Transaccion.objects.filter(usuario=usuario, fecha__range=(desde, hasta)):
        k = (t.fecha, t.tipo, Decimal(t.monto), (t.descripcion or '').strip().lower())
        ya_en_base[k] = ya_en_base.get(k, 0) + 1

    meses_por_comercio = {}
    for t in Transaccion.objects.filter(
            usuario=usuario, tipo='EGRESO', fecha__lt=desde).order_by('-fecha')[:400]:
        k = _clave(t.descripcion or '')
        if k:
            meses_por_comercio.setdefault(k, set()).add((t.fecha.year, t.fecha.month))

    vistos_en_cartola = {}

    for m in movs:
        m.categoria = categoria_de(m.descripcion, m.tipo)
        if not m.cuota_total:
            m.cuota_actual, m.cuota_total = cuotas_de(m.descripcion)

        if m.es_cuota and m.categoria == 'Otros':
            m.categoria = 'Compras'

        if m.tipo == 'EGRESO':
            bajo_desc = m.descripcion.lower()
            m.es_suscripcion = not m.es_cuota and (
                bool(RECURRENTE.match(m.descripcion))
                or any(k in bajo_desc for k in MARCAS_RECURRENTES)
                or bool(MARCAS_EXACTAS.search(m.descripcion))
                or len(meses_por_comercio.get(_clave(m.descripcion), ())) >= 2
            )
            if m.es_suscripcion and m.categoria == 'Otros':
                m.categoria = 'Servicios'

        k = (m.fecha, m.tipo, m.monto, m.descripcion.strip().lower())
        vistos_en_cartola[k] = vistos_en_cartola.get(k, 0) + 1
        if vistos_en_cartola[k] <= ya_en_base.get(k, 0):
            m.ya_existe = True

        bajo = m.descripcion.lower()
        if not m.aviso and any(t in bajo for t in TRASPASOS):
            m.aviso = 'Parece plata que moviste entre tus propias cuentas.'

    return cartola
