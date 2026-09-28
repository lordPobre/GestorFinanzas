# 13 · Deuda técnica y hoja de ruta

Lo que queda por mejorar y lo que resolvió la entrega de arreglos del 28 de septiembre de 2026. Todo sale de la lectura del código de `main` de esa fecha.

## Resuelto en la entrega de arreglos

| # | Qué era | Cómo quedó |
| --- | --- | --- |
| E1 | Reactivar una suscripción en enero daba error 500 | El mes anterior se calcula con `relativedelta` |
| E2 | La cuota importada desde una cartola quedaba pendiente y se duplicaba al pagarla | Se crea su `PagoCuota` vinculado al movimiento importado. La migración 0117 repara las deudas que ya estaban descuadradas |
| E3 | Los meses generados como pagados no tenían `PagoServicio` | Se crea junto con el cobro |
| E4 | Una cuenta solo con Google no podía desactivar la verificación en dos pasos | Confirma con un código de la app |
| E5 | Las categorías propias salían con el *slug* y el color de `Otros` | Inicio y estadísticas usan `Categoria.mapa` |
| E6 | Borrar la cuenta no tenía bloqueo real | Se bloquea después de 5 intentos fallidos |
| E7 | La página sin conexión estaba en voseo | Tutea |
| E8 | El texto llamaba público al bucket de las fotos | Corregido en el comando y en `docs/RESPALDOS.md` |
| S1 | Google vinculaba por correo sin verificar | Solo entra a una cuenta existente si su correo está confirmado |
| S2 | La pantalla de sesiones enviaba la clave de las otras sesiones | Envía el número de `SesionActiva` |
| S3 | `limitar` alargaba la ventana en cada petición | Guarda el vencimiento con el contador |
| S4 | Color, icono y tipo de categoría sin validar | Se validan contra `PALETA`, `ICONOS` y `TIPOS` |
| S5 | La cartola aceptaba cualquier categoría | Se valida contra las categorías del usuario |
| C1 | La política no decía que lo leído de una cartola queda en la sesión | Lo dice, con el plazo de 8 horas |
| C2 | `legal.VERSION` seguía en 1.2 | 1.3, vigente desde el 8 de octubre de 2026. Se despliega el 1 de octubre con el correo de aviso |
| C3 | El registro de tratamientos no tenía el chat ni el formulario | Agregados en la entrega de documentación |
| I1 | El manifiesto pedía íconos de 192 y 512 px que no existían. Los demás archivos que se daban por faltantes sí estaban en `main` | Íconos agregados en `static/img/` |
| I2 | Faltaban las configuraciones de las tareas programadas de Railway | `railway/avisos.json`, `inactivas.json` y `avatares.json` |
| I3 | Restos del nombre anterior | CI y respaldos de Postgres con `fintora`. Siguen a propósito `cache_finapp`, el prefijo `finapp-` de SQLite y del *service worker* y las claves de `localStorage` (ver [12 · Decisiones](12-DECISIONES.md)) |
| I4 | CI contra Postgres 17 | Postgres 18, igual que producción |
| D1 | El cobro de una suscripción se encontraba por el texto de su descripción | FK `Transaccion.suscripcion` (`related_name='cobros'`). La migración 0116 vincula los cobros existentes |
| D2 | No se podía editar una suscripción | `/suscripciones/<id>/editar/`. Renombra sus cobros y ajusta el del mes si no está pagado |
| D3 | `Prestamo` y `Persona` calculaban con `float` | `Decimal`, con la cuota redondeada al peso como en `Deuda` |
| D4 | `Deuda.cuotas_pagadas` se mantenía a mano en cada vista | Lo actualiza una señal de `PagoCuota` |

## Pendiente

| # | Qué | Por qué importa |
| --- | --- | --- |
| D5 | `resumen_mes` y varias pantallas recorren en Python todas las compras en cuotas y suscripciones del usuario | Correcto y sin consultas por fila, pero crece con el historial. Filtrar en la base las compras que tienen cobro en el mes |
| D6 | La IA y el correo se llaman dentro de la petición | Si Anthropic o Resend tardan, ocupan uno de los 8 hilos. Con más usuarios, pasarlos a una cola |
| D7 | No hay pruebas de JavaScript | Ver [11 · Pruebas](11-PRUEBAS.md#qué-no-tiene-pruebas-hoy) |
| D8 | `comun.contadores()` corre en casi todas las pantallas: arma el formulario de registro, lista las categorías y calcula `salud_financiera`, que llama a `resumen_mes` del mes en curso | `base.html` dibuja el panel de registro y la salud del mes en todas las pantallas. Partirlo exige cambiar primero la plantilla base: mostrar la salud solo en el inicio y cargar el panel de registro al abrirlo |
| D9 | La lectura de una cartola ocurre dentro de la petición, con el límite de 60 s de gunicorn | Los topes evitan que se cuelgue, pero una cartola cerca del tope puede cortarse. Pasarla a una cola (`django-q2` sobre Postgres, con un segundo servicio que corra `qcluster`) cuando los registros muestren cortes reales |
| D10 | Las reglas ampliadas de `ruff` (S, B, DJ, UP) solo informan | Revisar el resumen del trabajo `estilo-ampliado`, corregir por familia y moverlas a `select` en `pyproject.toml` |
| D11 | La cobertura mínima está en 55 % | Subirla al valor real, redondeado hacia abajo, y después 5 puntos por lote |
| D12 | `finapp.css` (unos 165 KB) tiene los ajustes de teléfono de varias pantallas agrupados en la sección de la barra inferior | Funciona, pero mover reglas puede cambiar cuál gana. Reordenar una sección a la vez, comparando capturas (ver `docs/ESTILOS.md`) |

## Hoja de ruta sugerida

**Antes del 1 de octubre:** aplicar la entrega de arreglos, menos la política, y apuntar las tareas de Railway a sus archivos.

**1 de octubre:** desplegar la política 1.3 y enviar el aviso.

**Este mes:** D10 y D11, que solo piden leer lo que el CI ya reporta, y las pruebas de JavaScript (D7) para el chat y el tour.

**Siguiente trimestre:**

- Lectores propios de Santander, BCI y Scotiabank, y CSV de Tenpo, MACH y Mercado Pago (ver [05 · Cartolas](05-CARTOLAS.md#prioridad)).
- D5 y D8, midiendo antes el tiempo de respuesta de las pantallas.
- D6 y D9, cuando los registros muestren esperas o cortes reales.
- Programa de rotación de secretos con fecha por secreto (ver [10 · Operación](10-OPERACION.md)).
