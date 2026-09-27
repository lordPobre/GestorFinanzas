# 13 · Deuda técnica y hoja de ruta

Lo que hay que corregir, ordenado por gravedad. Cada punto indica dónde está, qué pasa y cómo se arregla. Todo sale de la lectura del código de `main` del 27 de septiembre de 2026.

Gravedad: **Alta** = rompe algo o expone datos · **Media** = da un resultado incorrecto · **Baja** = incomodidad, prolijidad o riesgo acotado.

## Errores

| # | Gravedad | Dónde | Qué pasa | Arreglo |
| --- | --- | --- | --- | --- |
| E1 | Alta | `views/suscripciones.cancelar_suscripcion` | Al reactivar una suscripción en **enero**, `ultimo_mes_generado = año*100 + mes - 1` da `AAAA00`. Luego `generar_cobros_suscripciones` hace `date(AAAA, 0, 1)` y la pantalla responde 500 | Calcular el mes anterior con `relativedelta(months=1)`. Agregar una prueba con la fecha fija en enero |
| E2 | Media | `views/cartola.confirmar_cartola` | Al importar una cuota marcando “compra en cuotas”, se crea la `Deuda` con `cuotas_pagadas=1`, pero sin `PagoCuota` ni vínculo con el egreso importado. El mes muestra esa cuota como pendiente y, si se paga, se crea un segundo egreso | Crear el `PagoCuota` del periodo de la fecha importada con `transaccion=tx` y recalcular `cuotas_pagadas` con `pagos.count()` |
| E3 | Media | `servicios/suscripciones.generar_cobros_suscripciones` | Si el usuario no entra durante meses, los meses pasados se generan con `pagado=True`, pero sin `PagoServicio`. La pantalla de suscripciones los muestra atrasados y el inicio, pagados | Decidir una sola regla: o crear también el `PagoServicio` de esos meses, o dejarlos pendientes en los dos lados |
| E4 | Baja | `views/cuenta.configurar_2fa` | Una cuenta creada solo con Google (sin contraseña utilizable) no puede desactivar la 2FA ni regenerar los códigos, porque `check_password` siempre falla | Si `not has_usable_password()`, pedir un código TOTP válido en vez de la contraseña |
| E5 | Baja | `servicios/panel.desglose_categorias`, `views/estadisticas` | Las categorías propias aparecen con el *slug* como nombre y el color de `Otros` en el gráfico del inicio y en el ranking de estadísticas | Usar `Categoria.mapa(usuario)` para la etiqueta y el color |
| E6 | Baja | `views/cuenta.eliminar_cuenta` | Registra el fallo de contraseña en `borrado:{id}`, pero nunca consulta ese contador: no hay bloqueo real | Consultar `esta_bloqueado` antes de verificar |
| E7 | Baja | `static/js/sw.js` | La página “Sin conexión” está en voseo (“revisá”, “volvé”); el resto de la app tutea | Cambiar a “revisa la red y vuelve a intentar” |
| E8 | Baja | `respaldar_postgres._r2` y `docs/RESPALDOS.md` | Los dos llaman “público” al bucket de las fotos, pero es privado desde el lote C y las fotos se sirven con URL firmada | Corregir el texto: “tiene que ser distinto del de las fotos” |

## Seguridad

| # | Gravedad | Qué | Arreglo |
| --- | --- | --- | --- |
| S1 | Media | **Vinculación de Google por correo sin verificar** (`google_login._usuario_para`). Si alguien registró una cuenta con un correo ajeno y nunca lo confirmó, cuando el dueño real entra con Google queda dentro de esa cuenta. Y al revés: alguien puede preparar una cuenta con el correo de la víctima y esperar (pre-secuestro) | Vincular por correo solo si `profile.correo_verificado` es verdadero. Si no, crear una cuenta nueva o pedir la contraseña de la existente |
| S2 | Baja | `sesiones_activas` envía en el HTML la *session key* de las otras sesiones del mismo usuario para poder cerrarlas | Usar el `pk` de `SesionActiva` en el formulario y buscar la clave en el servidor |
| S3 | Baja | `seguridad.limitar` reescribe el TTL en cada llamada, así que la ventana se alarga mientras sigan llegando peticiones. Es más estricto de lo documentado, no menos | Guardar el vencimiento junto al contador, como hacen los topes de acceso |
| S4 | Baja | `crear_categoria` y `editar_categoria` guardan `color`, `icono` y `tipo` sin validarlos contra `PALETA`, `ICONOS` y `TIPOS`. El autoescape evita que se rompa el atributo, pero un valor raro se pinta dentro de `style` | Validar contra las listas |
| S5 | Baja | `confirmar_cartola` acepta cualquier `cat_i` como categoría | Validar contra `Categoria.opciones(usuario, tipo)` |

## Cumplimiento

| # | Gravedad | Qué | Arreglo |
| --- | --- | --- | --- |
| C1 | Media | **Los movimientos leídos de una cartola quedan en la sesión** (tabla `django_session`) hasta confirmar, descartar o que venza la sesión (8 h). La política dice que el archivo se descarta, lo cual es cierto, pero no menciona este detalle | Declararlo en la política (“lo leído queda en tu sesión hasta que confirmes o descartes, como máximo 8 horas”) o borrarlo al cerrar la pestaña de revisión con un plazo corto propio |
| C2 | Media | **`legal.VERSION` en `main` sigue en `1.2`.** El paso a 1.3, que incorpora el chat de ayuda, no se aplicó, aunque `privacidad.html` ya describe el chat | Subir a `1.3` con su fecha de vigencia y avisar por correo antes de que rija, como promete la propia política |
| C3 | Baja | `docs/REGISTRO-TRATAMIENTOS.md` no incluye el chat de ayuda ni el formulario de contacto | Agregar las dos actividades de tratamiento |

## Infraestructura y repositorio

| # | Qué | Arreglo |
| --- | --- | --- |
| I1 | Archivos que el código o el README usan y que no aparecen en el árbol de `main`: `.python-version` (el CI lo lee con `python-version-file`), `.env.example`, `requirements.in`, `requirements-dev.in`, `railway/Dockerfile.respaldo` y `static/site.webmanifest` (lo enlazan `base.html`, `auth_base.html` y `landing.html`) | Revisar con `git ls-files`. Los que falten, crearlos y subirlos: sin `.python-version` el CI no puede instalar Python y sin el manifiesto la app no se instala bien |
| I2 | Los servicios programados `avisos`, `inactivas` y `avatares` de Railway apuntan a `railway/avisos.json`, `railway/inactivas.json` y `railway/avatares.json`, pero en `main` solo está `railway/respaldo.json` | Subir los tres archivos (el formato es el de `respaldo.json`, con builder NIXPACKS). Si no están, un redespliegue de esos servicios toma `railway.json`, arranca gunicorn y espera `/salud/`, en vez de correr la tarea |
| I4 | El CI prueba contra Postgres 17 y producción corre Postgres 18 | Cambiar la imagen del servicio del CI a `postgres:18` |
| I3 | Restos del nombre anterior: usuario y base `rekon` en el CI, `ALLOWED_HOSTS=rekon.example`, respaldos `rekon-*.dump`, caché `cache_finapp`, estáticos `finapp.css` y `finapp.js`, caché del *service worker* `finapp-estaticos-*`, respaldos SQLite `finapp-*` | Cambiar los del CI y el prefijo de los respaldos de Postgres (la rotación usa la carpeta, así que es seguro). **No cambiar** `cache_finapp` (habría que recrear la tabla), el prefijo `finapp-` de SQLite (se pierde la rotación de las copias existentes) ni las claves de `localStorage` (reaparecería lo que cada persona ocultó) |

## Diseño y mantenibilidad

| # | Qué | Por qué importa |
| --- | --- | --- |
| D1 | El egreso de una suscripción se encuentra por el texto de su descripción (`Suscripción: {nombre}`) | Si alguien edita ese movimiento, se pierde el vínculo con el pago del mes. Conviene una FK `Transaccion.suscripcion`, como ya tiene `PagoCuota.transaccion` |
| D2 | No hay vista para editar una suscripción | Hoy, para corregir un monto hay que borrarla y crearla de nuevo, y se pierde el historial de pagos |
| D3 | `Prestamo` y `Persona` calculan con `float`; `Deuda` usa `Decimal` | Con montos grandes y muchos abonos puede aparecer un peso de diferencia. Pasar a `Decimal` |
| D4 | `Deuda.cuotas_pagadas` es un contador redundante con `pagos` | Se mantiene a mano en cada vista, y E2 muestra cómo se desincroniza. Calcularlo siempre desde `pagos` |
| D5 | `resumen_mes` y varias pantallas recorren en Python todas las compras en cuotas y suscripciones del usuario | Correcto y sin consultas por fila, pero crece con el historial. Filtrar en la base las compras que tienen cobro en el mes |
| D6 | La IA y el correo se llaman dentro de la petición | Si Anthropic o Resend tardan, ocupan uno de los 8 hilos. Con más usuarios, pasarlos a una cola |
| D7 | No hay pruebas de JavaScript | Ver [11 · Pruebas](11-PRUEBAS.md#qué-no-tiene-pruebas-hoy) |
| D8 | `comun.contadores()` corre en casi todas las pantallas: arma el formulario de registro, lista las categorías y calcula `salud_financiera`, que a su vez llama a `resumen_mes` del mes en curso | Entrar a cualquier pantalla paga el costo del resumen completo del mes para pintar el menú. Partirlo en una versión liviana para el menú y otra completa solo donde se muestra el panel de registro |
| D9 | La lectura de una cartola ocurre dentro de la petición, con el límite de 60 s de gunicorn | Los topes evitan que se cuelgue, pero una cartola cerca del tope puede cortarse. Pasarla a una cola (`django-q2` sobre Postgres, con un segundo servicio que corra `qcluster`) cuando los registros muestren cortes reales |
| D10 | Las reglas ampliadas de `ruff` (S, B, DJ, UP) solo informan | Revisar el resumen del trabajo `estilo-ampliado`, corregir por familia y moverlas a `select` en `pyproject.toml` |
| D11 | La cobertura mínima está en 55 % | Subirla al valor real, redondeado hacia abajo, y después 5 puntos por lote |
| D12 | `finapp.css` (unos 165 KB) tiene los ajustes de teléfono de varias pantallas agrupados en la sección de la barra inferior | Funciona, pero mover reglas puede cambiar cuál gana. Reordenar una sección a la vez, comparando capturas (ver `docs/ESTILOS.md`) |

## Hoja de ruta sugerida

**Esta semana (antes de sumar usuarios):** E1, E2, S1, C1, C2, I1.

**Este mes:** E3, E4, E5, I2, D1 y D2 (juntas), y las pruebas que faltan para cartolas y Google.

**Siguiente trimestre:**

- Lectores propios de Santander, BCI y Scotiabank, y CSV de Tenpo, MACH y Mercado Pago (ver [05 · Cartolas](05-CARTOLAS.md#prioridad)).
- D3, D4 y D5.
- Mover la IA y el correo a una tarea en segundo plano cuando el tráfico lo pida (D6).
- Programa de rotación de secretos con fecha por secreto (ver [10 · Operación](10-OPERACION.md)).
