# 03 · Modelo de datos

Todos los modelos viven en `finanzas/models/`, un archivo por tema, y se reexportan desde `finanzas/models/__init__.py`. La app tiene una sola aplicación Django (`finanzas`). Cada dato de negocio cuelga, directa o indirectamente, de `django.contrib.auth.models.User`. Por eso borrar el usuario borra todo en cascada.

Montos: `DecimalField` con 2 decimales. La moneda es una preferencia del perfil (`UserProfile.moneda`) y solo cambia cómo se muestra el monto. No hay conversión de moneda.

Meses: los cobros mensuales (cuotas y suscripciones) se identifican con un entero `periodo = año * 100 + mes`. Por ejemplo, septiembre de 2026 es `202609`.

## Diagrama

```
User ─┬─ 1:1 ─ UserProfile
      ├─ 1:1 ─ Presupuesto
      ├─ 1:1 ─ SegundoFactor
      ├─ 1:N ─ Transaccion ──┬─ 1:1 ← PagoCuota.transaccion
      │                      └─ 1:1 ← GastoPendiente.transaccion
      ├─ 1:N ─ Categoria
      ├─ 1:N ─ GastoPendiente
      ├─ 1:N ─ Deuda ─ 1:N ─ PagoCuota
      ├─ 1:N ─ Suscripcion ─ 1:N ─ PagoServicio
      ├─ 1:N ─ MetaAhorro ─ 1:N ─ AporteMeta
      ├─ 1:N ─ Persona ─ 1:N ─ Prestamo ─ 1:N ─ AbonoPrestamo
      ├─ 1:N ─ CodigoRespaldo
      ├─ 1:N ─ SesionActiva
      ├─ 1:N ─ Passkey
      ├─ 1:N ─ RespuestaEncuesta
      ├─ 1:N ─ SugerenciaDescartada
      └─ 0:N ─ EventoSeguridad (SET_NULL: sobrevive al borrado de la cuenta)
```

## Movimientos (`models/movimientos.py`)

### `Transaccion`

Es el registro base: cada ingreso o gasto que afecta al mes.

| Campo | Tipo | Notas |
| --- | --- | --- |
| `usuario` | FK User, CASCADE | |
| `tipo` | char(10) | `INGRESO` o `EGRESO` |
| `monto` | decimal(10,2) | Siempre positivo; el signo lo da `tipo` |
| `categoria` | char(50) | Clave de `CATEGORIAS` o `slug` de una `Categoria` propia. Por defecto `Otros` |
| `fecha` | date | Por defecto hoy |
| `descripcion` | char(200) | Libre. Prefijo `Suscripción: ` para los cobros generados por suscripciones |
| `es_cuota` | bool | `True` si la generó el pago de una cuota |
| `pagado` | bool | Por defecto `True`. `False` = gasto anotado pero aún sin pagar |
| `fecha_pago` | date, null | Cuándo se pagó de verdad, si fue otro día |
| `suscripcion` | FK `Suscripcion`, null | Si es el cobro de una suscripción (`related_name='cobros'`). Al borrar la suscripción, el movimiento queda sin vínculo |

Orden por defecto: `-fecha, -id`.

Categorías fijas de gasto: `Comida`, `Transporte`, `Servicios`, `Ocio`, `Salud`, `Tecnologia`, `Ropa`, `Hogar`, `Viajes`, `Compras`, `Educacion`, `Otros`. De ingreso: `Sueldo`, `Freelance`, `Negocio`, `Venta`, `Bono`, `Transferencia`, `Otros_Ingresos`. Cada una tiene color (`COLORES_CATEGORIA`) e ícono de Font Awesome (`ICONOS_CATEGORIA`). Hay además dos claves de solo lectura para colorear: `Suscripciones` y `Cuentas`.

Propiedades calculadas:

- `es_ingreso`, `es_gasto_unico` (gasto que no es cuota) y `por_pagar` (gasto único sin pagar).
- `texto_estado_pago`: “Pagado”, “Pagado el dd/mm” o “Sin pagar hace N días”.
- `clase_tono`: `ingreso`, `cuota`, `suscripcion` o `gasto`. Sirve para colorear la fila.
- `marca_suscripcion`: si la descripción empieza con `Suscripción: `, busca la marca en `Suscripcion.MARCAS` y devuelve ícono y color.
- `color_categoria` e `icono`.

### `Categoria`

Categorías propias del usuario, que se suman a las fijas.

| Campo | Tipo | Notas |
| --- | --- | --- |
| `usuario` | FK User, CASCADE | `related_name='categorias'` |
| `nombre` | char(40) | |
| `slug` | slug(50) | Se genera solo desde el nombre y es único por usuario (`categoria_unica_por_usuario`). Si choca, se agrega `-2`, `-3`… |
| `tipo` | char(10) | `EGRESO` o `INGRESO` |
| `color` | char(20) | De `PALETA` (9 colores) |
| `icono` | char(30) | De `ICONOS` (15 íconos) |
| `activa` | bool | Una categoría inactiva no aparece al anotar, pero conserva sus movimientos |

`Categoria.opciones(usuario, tipo)` devuelve las fijas más las propias activas, listas para un `<select>`. `Categoria.mapa(usuario)` devuelve `{slug: {label, color, icono, propia}}` con las fijas y todas las propias, y se usa para pintar cualquier movimiento.

La `Transaccion` guarda el slug como texto, no una FK. Por eso desactivar una categoría no rompe nada. Al borrarla, la vista pasa sus movimientos a `Otros` (u `Otros_Ingresos`) antes de eliminarla.

### `Presupuesto`

Uno por usuario (`OneToOne`). `limite_mensual` decimal(12,2), por defecto 500.000.

### `GastoPendiente`

Una cuenta por pagar con fecha de vencimiento: la luz, el arriendo, una multa.

| Campo | Tipo | Notas |
| --- | --- | --- |
| `usuario` | FK User, CASCADE | `related_name='gastos_pendientes'` |
| `nombre` | char(100) | |
| `monto` | decimal(12,2) | |
| `fecha_vencimiento` | date | |
| `categoria` | char(50) | Por defecto `Cuentas` |
| `pagado`, `fecha_pago` | bool, date | |
| `creado` | date | |
| `transaccion` | 1:1 Transaccion, SET_NULL | El egreso que se creó al pagarlo |

`urgencia` devuelve `pagado`, `vencido`, `hoy`, `proximo` (3 días o menos) o `normal`. `texto_urgencia` es el texto que se muestra.

## Cuotas (`models/cuotas.py`)

### `Deuda`

Una compra en cuotas. El nombre del modelo es histórico: en la interfaz se llama “compra en cuotas”.

| Campo | Tipo | Notas |
| --- | --- | --- |
| `usuario` | FK User, CASCADE | |
| `acreedor` | char(100) | Qué se compró o dónde (“Notebook”, “Falabella”) |
| `monto_total` | decimal(10,2) | |
| `categoria` | char(50) | De `CATEGORIAS_CUOTAS` (10 opciones) |
| `cuotas_totales` | int | Por defecto 12 |
| `cuotas_pagadas` | int | Cantidad de `pagos`. Lo actualiza una señal de `PagoCuota` al crear o borrar un pago |
| `fecha_inicio` | date | Fecha del primer cobro. Su día es el día de pago de todos los meses |

Cómo se calcula:

- `periodos_programados`: los `cuotas_totales` periodos desde `fecha_inicio`, uno por mes.
- `fecha_cobro_de(periodo)`: el día de `fecha_inicio` en ese mes, recortado al último día si el mes es más corto (una compra del 31 se cobra el 28 o 29 de febrero).
- `monto_cuota`: `monto_total / cuotas_totales`, redondeado al peso. `monto_cuota_de(periodo)` le carga la diferencia del redondeo a la última cuota, para que la suma cuadre exacto.
- `periodos_pagados`, `periodos_pendientes`, `periodo_a_pagar` (el pendiente más antiguo) y `periodos_atrasados` (los pendientes cuya fecha ya pasó).
- `urgencia`: `saldada`, `vencida`, `critica` (3 días o menos), `proxima` (7 días o menos) o `normal`.
- `rango_cuotas`: las marcas de la barra de cuotas, hasta 36, con estado `paid`, `next`, `late` o vacío.
- `monto_pagado` (suma de `pagos`) y `monto_restante`.

Siempre se paga el periodo más antiguo pendiente. No se puede pagar marzo si febrero está pendiente.

### `PagoCuota`

| Campo | Tipo | Notas |
| --- | --- | --- |
| `deuda` | FK Deuda, CASCADE | `related_name='pagos'` |
| `periodo` | int, índice | `año*100+mes` |
| `monto` | decimal(12,2) | |
| `fecha_pago` | date | Cuándo se pagó de verdad |
| `transaccion` | 1:1 Transaccion, SET_NULL | El egreso con `es_cuota=True` que se creó |

Restricción `pago_unico_por_mes`: `(deuda, periodo)` es único, así que un mes no se paga dos veces. `fue_atrasado` compara `fecha_pago` con la fecha de cobro del periodo.

## Suscripciones (`models/suscripciones.py`)

### `Suscripcion`

| Campo | Tipo | Notas |
| --- | --- | --- |
| `usuario` | FK User, CASCADE | `related_name='suscripciones'` |
| `nombre` | char(100) | |
| `monto` | decimal(12,2) | Por mes |
| `categoria` | char(50) | Por defecto `Suscripciones` |
| `dia_cobro` | int | 1 a 28 |
| `activa` | bool | Pausada = `False` |
| `fecha_inicio` | date | |
| `fecha_cancelada` | date, null | |
| `ultimo_mes_generado` | int | Último `periodo` para el que se creó el movimiento automático |

`MARCAS` es una lista de 38 entradas `(texto a buscar, ícono, color)`: Netflix, Spotify, YouTube, Disney, HBO/Max, Prime, Apple, Google, Microsoft, Xbox, PlayStation, Steam, ChatGPT, Claude, Notion, Duolingo, gimnasio, internet, seguro, etc. `marca` busca el texto dentro del nombre y, si no la reconoce, usa el ícono genérico en ámbar. Cuando el ícono es `None`, se dibuja la inicial sobre el color de la marca.

La lógica de periodos es la misma que en `Deuda`, pero sin fin: los periodos programados van desde `fecha_inicio` hasta hoy o hasta `fecha_cancelada`. `estado_mes` devuelve `pausada`, `atrasada`, `pagada` o `pendiente`. `total_pagado_historico` suma sus `cobros`.

### `PagoServicio`

`suscripcion` (FK, `related_name='pagos'`), `periodo`, `monto` y `fecha_pago`. La restricción `pago_servicio_unico_por_mes` hace único `(suscripcion, periodo)`.

### `SugerenciaDescartada`

En `models/sugerencias.py`. `usuario` (FK, `related_name='sugerencias_descartadas'`), `clave` y `creada`. La restricción `sugerencia_descartada_unica` hace único `(usuario, clave)`. Guarda las sugerencias de suscripción que la persona marcó con «No es».

## Metas (`models/metas.py`)

### `MetaAhorro`

`usuario`, `nombre`, `monto_meta`, `monto_actual` (acumulado) y `fecha_limite` (opcional).

- `icono`: se elige por palabra clave en el nombre (“viaje” → avión, “auto” → auto, “notebook” → laptop…), con 38 claves. Sin coincidencia usa una diana.
- `color`: rota entre 8 colores según el `pk`.
- `porcentaje` (con tope de 100), `monto_faltante` y `esta_completa`.
- `ahorro_mensual_sugerido`: lo que falta dividido por los meses enteros hasta `fecha_limite`.
- `nota_plan`: texto del tipo “Aportando $X al mes lo logras en N meses.”

### `AporteMeta`

`meta` (FK, `related_name='aportes'`), `monto`, `fecha` y `nota`.

## Préstamos (`models/prestamos.py`)

Registran la plata que el usuario prestó y le deben. No hay registro de lo que el usuario debe a otras personas.

### `Persona`

`usuario`, `nombre` (80), `contacto` (80, libre y opcional) y `creada`. Todo lo que muestra se calcula sobre sus préstamos: `total_prestado`, `total_abonado`, `total_pendiente`, `prestamos_activos`, `cobro_del_mes` (cuotas del mes más préstamos únicos pendientes).

### `Prestamo`

| Campo | Tipo | Notas |
| --- | --- | --- |
| `persona` | FK Persona, CASCADE | `related_name='prestamos'` |
| `descripcion` | char(120) | |
| `monto` | decimal(12,2) | |
| `tipo` | char(10) | `UNICO` o `CUOTAS` |
| `cuotas_totales` | int | 1 si es único |
| `fecha` | date | |

`monto_pendiente`, `porcentaje`, `esta_pagado`, `monto_cuota`, `cuotas_abonadas` (lo abonado dividido por la cuota) y `montos_sugeridos` (los botones rápidos del formulario de abono: “Una cuota”, “Dos cuotas”, “La mitad” y “Todo lo pendiente”).

Estos cálculos usan `Decimal`, como `Deuda`, y la cuota se redondea al peso.

### `AbonoPrestamo`

`prestamo` (FK, `related_name='abonos'`), `monto`, `fecha` y `nota`.

## Perfil (`models/perfil.py`)

### `UserProfile`

Uno por usuario (`related_name='profile'`). Se crea en el registro. Si falta, las vistas lo crean con `get_or_create_profile`.

| Grupo | Campos |
| --- | --- |
| Primeros pasos | `onboarding_completado`, `paso_onboarding` |
| Datos personales | `nombre_completo`, `email`, `telefono`, `pais`, `ciudad` (todos opcionales) |
| Preferencias | `moneda` (CLP, USD, EUR, ARS, MXN, COP, PEN o BRL; por defecto CLP) |
| Google | `google_sub` (único, null): el identificador estable de la cuenta de Google vinculada |
| Foto | `foto`: `ImageField` en `avatares/{usuario_id}/{8 hex}.{ext}`, sobre el almacenamiento de `almacenamiento.py` (disco o R2) |
| Aviso mensual | `aviso_mensual` (on por defecto), `aviso_dia` (20), `aviso_ultimo_periodo` |
| IA | `analisis_ia` (on por defecto) |
| Correo | `correo_verificado`, `correo_verificado_en` |
| Consentimiento | `politica_version`, `politica_aceptada` |
| Inactividad | `ultima_actividad`, `aviso_inactividad_enviado` |

Al cambiar la foto, `save()` borra la anterior del almacenamiento. Una señal `post_delete` borra la foto cuando se elimina el perfil. `foto_url` guarda en caché la URL firmada por 5 horas: la firma de R2 dura 6, así que la URL guardada nunca vence antes que la caché.

## Seguridad (`models/seguridad.py`)

### `SegundoFactor`

TOTP con `pyotp`. Tiene `secreto` (base32), `activo`, `ultimo_uso` y `ultimo_codigo`. `verificar()` acepta el código anterior o el siguiente (`valid_window=1`) y rechaza repetir el último código usado, lo que evita que un código se reutilice dentro de su ventana. El emisor que ve la app de autenticación es `Fintora`.

### `CodigoRespaldo`

Ocho códigos de 8 caracteres con el formato `XXXX-XXXX`, de un alfabeto sin caracteres ambiguos (sin 0, O, 1, I). Se guardan con hash (`make_password`) y son de un solo uso. `generar()` borra los anteriores.

### `SesionActiva`

Una fila por sesión abierta: `clave` (session key, única), `ip`, `agente`, `creada` y `ultima_vez`. Es lo que permite listar los aparatos y cerrar sesiones a distancia. `navegador`, `sistema`, `aparato` e `icono` se deducen del *user agent*.

### `Passkey`

Credenciales WebAuthn (Face ID, huella, llave de seguridad): `credencial_id` (única), `clave_publica`, `contador` de firmas, `nombre` que pone el usuario, `creada` y `ultimo_uso`. No se guarda ningún dato biométrico.

### `EventoSeguridad`

Registro de auditoría. Es de solo lectura en el admin: no se puede crear, editar ni borrar a mano.

| Campo | Notas |
| --- | --- |
| `creado` | Índice |
| `tipo` | Índice. 19 tipos: `acceso`, `acceso_fallido`, `salida`, `bloqueo`, `codigo_fallido`, `2fa_activada`, `2fa_desactivada`, `codigos_regenerados`, `codigo_respaldo_usado`, `passkey_agregada`, `passkey_quitada`, `passkey_fallida`, `contrasena_cambiada`, `recuperacion_pedida`, `contrasena_restablecida`, `sesiones_cerradas`, `datos_descargados`, `cuenta_eliminada`, `admin_denegado` |
| `usuario` | FK User, **SET_NULL**: el evento sobrevive al borrado de la cuenta |
| `referencia` | Nombre de usuario o correo escrito, con índice. Permite rastrear los eventos después del borrado |
| `ip`, `agente`, `detalle` | |

Se conserva 12 meses (ver [10 · Operación](10-OPERACION.md)).

## Encuesta (`models/encuesta.py`)

### `RespuestaEncuesta`

`usuario`, `creada`, `antiguedad`, `frecuencia`, `facilidad` (1–5), `secciones` (JSON: lista de las pantallas que usa), `notas` (JSON: nota por pantalla), los textos libres `gusta`, `molesta`, `agregar` y `sacar`, `recomienda` (0–10, NPS) y `razon`.

## Tablas que no son modelos

- **Caché** `cache_finapp`: con Postgres, la crea `createcachetable` (está en el `preDeployCommand` de Railway). Guarda los contadores de intentos fallidos, los topes de peticiones, el cupo diario del chat y las URL firmadas de las fotos.
- **Sesiones** de Django (`django_session`): 8 horas, renovadas en cada petición.

## Migraciones

35 migraciones en `finanzas/migrations/`. La numeración salta de `0016` a `0100` a propósito: la `0100_pagocuota` inició el modelo de pagos por periodo y marca un corte con el esquema original. Desde ahí se agrega una por cambio:

| Migración | Qué agrega |
| --- | --- |
| 0100 | `PagoCuota` (pagos por mes, reemplaza el contador) |
| 0101 | `PagoServicio` |
| 0102 | `Transaccion.pagado` y `fecha_pago` |
| 0103 | Categorías propias de cuotas |
| 0104 | `Categoria` |
| 0105–0108 | Foto de perfil y su almacenamiento |
| 0106 | `SegundoFactor` y `CodigoRespaldo` |
| 0109 | `UserProfile.google_sub` |
| 0110 | Aviso mensual |
| 0111 | Versión de política aceptada |
| 0112 | `SesionActiva` y verificación de correo |
| 0113 | `RespuestaEncuesta` |
| 0114 | `Passkey` |
| 0115 | `EventoSeguridad` |
| 0116 | `Transaccion.suscripcion` y vínculo de los cobros existentes por su descripción |
| 0117 | Crea los `PagoCuota` que faltaban en deudas importadas desde cartolas y recalcula `cuotas_pagadas` |
| 0118 | `SugerenciaDescartada` |

El CI corre `makemigrations --check`: un cambio de modelo sin su migración deja el build en rojo.
