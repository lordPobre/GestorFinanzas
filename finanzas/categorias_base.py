BASE = (
    ('Comida', 'Comida y Supermercado', 'EGRESO', '#60a5fa', 'fa-cart-shopping'),
    ('Transporte', 'Transporte y Gasolina', 'EGRESO', '#53d258', 'fa-car'),
    ('Servicios', 'Luz, Agua, Internet', 'EGRESO', '#818cf8', 'fa-bolt'),
    ('Ocio', 'Entretenimiento y Salidas', 'EGRESO', '#fbbf24', 'fa-film'),
    ('Salud', 'Salud y Farmacia', 'EGRESO', '#22d3ee', 'fa-kit-medical'),
    ('Tecnologia', 'Tecnología y electrónica', 'EGRESO', '#818cf8', 'fa-laptop'),
    ('Ropa', 'Ropa y calzado', 'EGRESO', '#f472b6', 'fa-shirt'),
    ('Hogar', 'Hogar y muebles', 'EGRESO', '#2dd4bf', 'fa-couch'),
    ('Viajes', 'Viajes y pasajes', 'EGRESO', '#38bdf8', 'fa-plane'),
    ('Compras', 'Compras online', 'EGRESO', '#c084fc', 'fa-bag-shopping'),
    ('Educacion', 'Educación y cursos', 'EGRESO', '#facc15', 'fa-graduation-cap'),
    ('Otros', 'Otros Gastos', 'EGRESO', '#8b8b96', 'fa-ellipsis'),
    ('Suscripciones', 'Suscripciones', 'EGRESO', '#fb923c', 'fa-rotate'),
    ('Cuentas', 'Cuentas', 'EGRESO', '#e25c5c', 'fa-file-invoice'),
    ('Sueldo', 'Sueldo o salario', 'INGRESO', '#53d258', 'fa-money-check-dollar'),
    ('Freelance', 'Trabajo freelance', 'INGRESO', '#2fd8c8', 'fa-laptop-code'),
    ('Negocio', 'Negocio o emprendimiento', 'INGRESO', '#4b8cff', 'fa-store'),
    ('Venta', 'Venta de algo', 'INGRESO', '#a3e635', 'fa-tag'),
    ('Bono', 'Bono o aguinaldo', 'INGRESO', '#ffd54f', 'fa-gift'),
    ('Transferencia', 'Transferencia recibida', 'INGRESO', '#38bdf8', 'fa-right-left'),
    ('Otros_Ingresos', 'Otros ingresos', 'INGRESO', '#8b8b96', 'fa-ellipsis'),
)

COLOR_OTROS = '#8b8b96'

SLUGS_BASE = frozenset(fila[0] for fila in BASE)
