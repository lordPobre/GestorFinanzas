# Deuda técnica

Lo que quedó identificado en la revisión de septiembre de 2026 y no se hizo
todavía, con el motivo y el siguiente paso. Se revisa cada vez que se cierra un
lote.

## 1. Lógica de negocio dentro de las vistas (resuelto 2026-09-25)

`views.py` ya no existe. Las vistas están en `finanzas/views/`, con un
archivo por pantalla, y los cálculos en `finanzas/servicios/` (`mes`,
`cuotas`, `pendientes`, `suscripciones`, `panel`).

Queda `contadores()` en `views/comun.py`: sigue armando en cada pantalla el
formulario de registro y la salud del mes. Partirlo es el punto 1 de
`ARQUITECTURA.md`.

## 2. Montos como `float` fuera de `resumen_mes`

`resumen_mes` suma con `Decimal` y expone los valores exactos en
`r['exacto']`. El resto de las pantallas sigue convirtiendo a `float` para
redondear y graficar. En pesos chilenos no hay diferencia visible porque son
enteros. Si algún día se usa una moneda con centavos, hay que llevar
`Decimal` hasta las plantillas y convertir recién al pasar datos a los
gráficos.

## 3. Cartolas procesadas dentro de la petición

La lectura de un PDF grande ocurre en la misma petición, con el límite de 60
segundos de gunicorn. Los topes de `cartolas/base.py` (80 páginas, 1,5 M de
caracteres, 2.000 movimientos) evitan que se cuelgue, pero una cartola cerca
del tope puede cortarse.

No se hizo porque exige infraestructura nueva: un proceso aparte que tome
trabajos de una cola. La opción más simple con lo que ya hay es
`django-q2` usando Postgres como cola, con un segundo servicio en Railway
que corra `python manage.py qcluster`. Conviene hacerlo cuando los registros
muestren cortes reales.

## 4. Reglas de estilo ampliadas

El CI corre `ruff` con las reglas de seguridad (`S`), errores típicos
(`B`), Django (`DJ`) y sintaxis moderna (`UP`) en modo informativo. Para
pasarlas a obligatorias:

1. Mirar el resumen del trabajo `estilo-ampliado` en GitHub Actions.
2. Corregir o anotar cada caso por familia.
3. Moverlas a `select` en `pyproject.toml`.

## 5. Cobertura

El mínimo está en 55 % (`pyproject.toml`). Después de la primera corrida,
subirlo al valor real redondeado hacia abajo, y de ahí 5 puntos por lote.
