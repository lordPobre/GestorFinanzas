# Análisis de arquitectura — GestorFinanzas (revisión de código real)

Contrasté el documento que trajiste (puntuación 7.5/10, hecho sobre una lectura general) contra el código real del repo (`lordPobre/GestorFinanzas`, rama `main`). El documento tiene razón en el diagnóstico de fondo — vistas sobrecargadas, lógica dispersa, acoplamiento directo — pero se queda corto en la magnitud: subestima el tamaño de `views.py` y no ve el patrón concreto que lo está empeorando ahora mismo: `contadores()`.

## Lo que el documento dice bien

- **MVT con capas claras**, tracking por periodo (`año*100+mes`) en `Deuda`/`Suscripcion`, middleware CSP separado de negocio, `ia.py` desacoplado con fallback — todo confirmado leyendo el código. Son decisiones sólidas y no las tocaría.
- El diagnóstico central — **vistas con demasiadas responsabilidades** y **lógica de negocio distribuida** entre `views.py`, `models.py` e `ia.py` — es correcto.

## Lo que el documento no vio (o subestimó)

**`views.py` tiene ~2560 líneas, no ~1200.** Es más del doble. `dashboard()` sola ocupa ~310 líneas (566-875): calendario del mes, serie de 6 meses, desglose por categoría, próximo pago, "mis cuotas", insights, variación vs. mes anterior. Once bloques de lógica distinta en una función.

**El problema real de contexto no es "el panel carga todo" — es `contadores()`.** Cada vista (16 de 20+ funciones que renderizan HTML) termina con `context.update(contadores(request.user))`. Esa función, en cada carga de página sin excepción:

1. Cuenta deudas activas y arma `prestamos_activos` recorriendo `Persona` con `prefetch_related('prestamos__abonos')`.
2. Llama a `Categoria.opciones()` **cuatro veces** — dos de ellas literalmente duplicadas en el diccionario (`cats_egreso_json` y `cats_ingreso_json` se calculan dos veces cada una; la segunda pisa a la primera, así que dos de las cuatro llamadas son trabajo tirado).
3. Instancia un `TransaccionForm` completo — construye el form de Django entero — aunque la pantalla no vaya a mostrar el panel de registro más que un botón.
4. Llama a `salud_financiera()`, que llama a `resumen_mes()` del mes actual: dos agregaciones (`Sum`) sobre `Transaccion`, un `prefetch_related` de todas las `Deuda` con sus pagos, y un `prefetch_related` de todas las `Suscripcion` con sus pagos.
5. Recalcula `subs_pendientes` iterando cada suscripción activa y llamando `.pagada_este_mes` (otra vuelta sobre `periodos_programados`).

Entrar a **Cuotas** a ver el detalle de una compra corre todo esto — incluida la agregación completa del mes y el form de registro — para pintar un badge en el sidebar. Eso es lo que el documento llamó "acoplamiento entre capas": en la práctica es una función que mezcla contexto de UI global con cálculo financiero pesado, ejecutada en cada request.

**`dashboard()` duplica trabajo dentro de sí misma.** `Persona.objects.filter(...).prefetch_related('prestamos__abonos')` se ejecuta una vez dentro de `contadores()` (para `prestamos_activos`) y otra vez en el cuerpo de `dashboard()` (para `total_por_cobrar`) — dos queries idénticas por request. La serie de 6 meses llama `resumen_mes()` seis veces, cada una con sus propios `prefetch_related` de `Deuda` y `Suscripcion` — nada se cachea entre iteraciones aunque el conjunto de deudas del usuario no cambia entre meses.

**Sobre `UserProfile.saldo_disponible`:** no existe en el modelo actual. Ya no es un campo — `disponible` se calcula siempre al vuelo dentro de `resumen_mes()`. Ese problema, si existió, está resuelto; no lo vas a encontrar en el código de hoy.

**Confirmado y no mencionado en el documento:** `finanzas/tests.py` tiene 60 bytes — cero cobertura real sobre una app que mueve dinero y calcula saldos.

## Prioridad de arreglo

No en orden de "gravedad teórica" sino de **qué se siente primero** al usar la app y qué tan barato es arreglarlo sin romper nada.

**1. Partir `contadores()` en piezas que cada vista pide a propósito.**
Hoy es todo o nada. La solución no es "más context processors" (eso repite el problema a nivel de Django) — es que cada vista pida explícitamente lo que su plantilla usa: un helper `datos_sidebar(usuario)` liviano (badges + perfil, sin form ni salud) para las pantallas que no son el dashboard, y que `salud_financiera` + el form de registro solo se calculen en las pantallas que de verdad los muestran. Elimina las dos llamadas duplicadas a `Categoria.opciones()` de una vez.
Riesgo: bajo. No toca modelos ni URLs, solo `contadores()` y los `context.update()` de cada vista.

**2. Cachear `resumen_mes()` por (usuario, año, mes) en la request.**
`dashboard()` lo llama 8 veces por carga (actual, 6 meses de serie, mes anterior) y `salud_financiera()` una vez más. Un cache simple en memoria de proceso (`functools.lru_cache` con clave usuario+periodo, o el `CACHES` de locmem que ya está configurado en `settings.py`) corta esa repetición sin cambiar ninguna fórmula.
Riesgo: bajo. Es una capa encima de una función pura, no una reescritura.

**3. Extraer la lógica de `dashboard()` en funciones con nombre.**
No hace falta una "capa de servicios" formal todavía — con separar los once bloques (calendario, serie, categorías, insights, proyecciones) en funciones de 15-20 líneas cada una, testeables por separado, se resuelve el 80% del "God Object" que señala el documento. Encaja con el estilo que ya usa el código (`resumen_mes`, `salud_financiera`, `serie_cuotas` ya son ese patrón — falta aplicarlo dentro de `dashboard()` mismo).
Riesgo: bajo-medio. Es refactor puro, sin cambio de comportamiento; se valida comparando el HTML antes/después.

**4. Tests sobre lo que no puede fallar en silencio.**
No una suite completa — los cálculos de dinero: `monto_cuota_de` (el redondeo de la última cuota), `periodo_a_pagar`/`periodos_atrasados`, `resumen_mes` con montos conocidos. Si alguien toca una fórmula, un test roto avisa antes que un usuario viendo mal su saldo.
Riesgo: ninguno — son archivos nuevos, no tocan código existente.

## Lo que NO tocaría todavía

- El middleware CSP custom: está bien razonado y documentado, cambiarlo por `django-csp` no resuelve nada que tengas hoy.
- El patrón de periodos (`año*100+mes`): es la pieza más sólida del proyecto, no es deuda técnica.
- Repository/CQRS/Event Sourcing (recomendaciones "largo plazo" del documento): sobra para el tamaño actual de la app. Añadirían capas sin un problema real que resuelvan hoy.

## Decisión que necesito de ti

¿Empiezo por el punto 1 (partir `contadores()`) — es el que se siente en cada clic y el de menor riesgo — o prefieres que ataque primero el punto 3 (dashboard) porque es donde piensas seguir agregando features?
