# 13 · Deuda técnica y hoja de ruta

Lo que queda por mejorar y lo que se resolvió: la entrega de arreglos del 28 de septiembre de 2026 y la auditoría de seguridad de octubre (lotes 77 a 80). Actualizado el 6 de octubre de 2026 con los lotes hasta el 90.

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

## Resuelto en la auditoría de seguridad de octubre

| # | Qué era | Cómo quedó | Lote |
| --- | --- | --- | --- |
| SA1 | `/\malo.com` pasaba el filtro de `next` | `redirecciones.py` en todos los `next` | 77 |
| SA2 | Una descripción como `=HYPERLINK(...)` se exportaba como fórmula | `'` delante en el CSV, texto en el Excel | 77 |
| SA3 | Un `.xlsx` comprimido malicioso podía agotar la memoria | Revisión del zip antes de abrirlo y `defusedxml` | 77, 79 |
| SA4 | Atrás mostraba la app después de salir | `no-store` con sesión, `Clear-Site-Data` al salir y recarga en Safari | 77, 77b |
| SA5 | Sentry podía recibir formularios y cookies | Solo cuatro cabeceras y tokens ocultos en la URL | 77 |
| SA6 | `/analisis/ia/` aceptaba GET | Solo POST con CSRF | 77 |
| SA7 | El admin no exigía 2FA | Obligatoria, revisada en cada página | 77 |
| SB1 | Cambiar el correo no pedía la contraseña | Reautenticación, enlace al correo nuevo y aviso al anterior | 78 |
| SB2 | Los contadores podían perder intentos entre workers y las IPv6 los saltaban | Tabla `Contador` y agrupación /64 | 78 |
| SB3 | Una sesión usada a diario no vencía nunca | Máximo de 7 días | 78 |
| SB4 | No se avisaba de un acceso desde un aparato nuevo | Cookie `fintora_aparato` y correo | 78 |
| SC1 | Las sesiones vencidas se acumulaban y viajaban en el respaldo | `limpieza_diaria` y respaldo sin sus datos | 79 |
| SC2 | Cookies sin prefijo y sitio accesible por varios nombres | `__Host-` y dominio canónico | 79, 79b |
| SC3 | No se buscaban secretos en el historial | Gitleaks en el CI | 79 |
| SD1 | Un `NaN` en un monto daba error 500 | `monto_post` lo rechaza | 80 |
| SD2 | Un doble toque podía pagar dos veces | Transacción con bloqueo de fila | 80 |
| SD3 | El registro decía si un correo tenía cuenta | Respuesta igual y aviso por correo | 80 |
| SD4 | Las fotos guardaban la ubicación del EXIF | Se vuelven a guardar sin EXIF | 80 |
| SD5 | Google sin PKCE ni `nonce` | Agregados | 80 |

## Resuelto en los lotes 86 a 105

| # | Qué era | Cómo quedó | Lote |
| --- | --- | --- | --- |
| D14 | Un registro nuevo entraba a la app y uno con correo repetido volvía al acceso | La cuenta se crea al confirmar el correo. Los dos casos responden igual | 90 |
| C7 | Los recordatorios se sumaron a la política 1.5 ya publicada | Política 1.6, avisada por correo y con franja en el Inicio | 88 y 89 |
| D10 | Las reglas ampliadas de `ruff` (S, B, DJ, UP) solo informaban | Los 37 avisos corregidos o justificados en `per-file-ignores`; las cuatro familias están en `select` y el trabajo `estilo-ampliado` se quitó | 91 |
| D13 | Los atributos `style` seguían permitidos (`style-src-attr 'unsafe-inline'`) | Las etiquetas `<style>` piden nonce y ninguna pantalla usa atributos `style`: `style-src-attr 'none'` en toda respuesta que no sea un error. Los estilos están en `sesion.css`, `acceso.css` y `portada.css`, y lo que depende de los datos va en atributos `data-` que aplica `estilos.js` | 90, 92, 96, 103 a 105 |
| D7 | Las pruebas de JavaScript cubrían solo el aviso al anotar y el *service worker* | 67 pruebas en `pruebas_js/`: el panel para anotar, lo por pagar en el Inicio, el chat de ayuda, el tour y la esfera. Activar los recordatorios queda a mano | 93 y 95 |

## Pendiente

| # | Qué | Por qué importa |
| --- | --- | --- |
| D5 | `resumen_mes` y varias pantallas recorren en Python todas las compras en cuotas y suscripciones del usuario | Correcto y sin consultas por fila, pero crece con el historial. Filtrar en la base las compras que tienen cobro en el mes |
| D6 | La IA y el correo se llaman dentro de la petición | Si Anthropic o Resend tardan, ocupan uno de los 8 hilos. Con más usuarios, pasarlos a una cola |
| D8 | `comun.contadores()` corre en casi todas las pantallas: arma el formulario de registro, lista las categorías y calcula `salud_financiera`, que llama a `resumen_mes` del mes en curso | `base.html` dibuja el panel de registro y la salud del mes en todas las pantallas. Partirlo exige cambiar primero la plantilla base: mostrar la salud solo en el inicio y cargar el panel de registro al abrirlo |
| D9 | La lectura de una cartola ocurre dentro de la petición, con el límite de 60 s de gunicorn | Los topes evitan que se cuelgue, pero una cartola cerca del tope puede cortarse. Pasarla a una cola (`django-q2` sobre Postgres, con un segundo servicio que corra `qcluster`) cuando los registros muestren cortes reales |
| D11 | La cobertura mínima está en 74 % (lote 94; `views/movimientos.py` ya está al 100 %) | Subirla 5 puntos por lote, empezando por los módulos con menos cobertura en `coverage report` |
| D12 | `finapp.css` (unos 165 KB) tiene los ajustes de teléfono de varias pantallas agrupados en la sección de la barra inferior, y encima van `tema-vidrio.css` y diez hojas por pantalla | Funciona, pero el orden de carga decide qué regla gana (el lote 70 lo sufrió). Reordenar una sección a la vez, comparando capturas (ver `docs/ESTILOS.md`) |
| D15 | DNSSEC y la inscripción en HSTS *preload* | DNSSEC se activa en Cloudflare y en Registrar.eu. El *preload* es difícil de revertir: solo cuando todos los subdominios funcionen por HTTPS |
| D16 | La voz depende del plan de ElevenLabs | El plan gratuito no permite uso comercial ni voces de Voice Library. En producción hace falta un plan de pago, y su DPA (C5 en [07](07-PRIVACIDAD-Y-CUMPLIMIENTO.md#pendientes-de-cumplimiento)) |
| D17 | `esfera_salud.py` y `esfera.py` calculan el color de Inicio por separado | Hoy usan los mismos tramos. Si uno cambia, el otro tiene que cambiar igual |
| D18 | En el computador, el aviso abre Fintora pero no trae el botón «Marcar pagada» (propuesta 2c) | Las acciones dentro del aviso dependen del navegador. Hoy hay que entrar a la app para pagar |
| D19 | `enviar_recordatorios` manda en serie, con hasta 10 segundos de espera por aparato | Con pocas cuentas sobra. Con cientos de aparatos puede tardar minutos: mandar en paralelo o por tandas |
| D20 | Los recordatorios salen a la misma hora para todos (12:00 UTC) | Se corren una hora con el horario de verano y no sirven a quien vive en otro huso |

## Hoja de ruta sugerida

**Antes del 13 de octubre:** correr `avisar_politica` (política 1.6).

**Antes del 20 de octubre:** contratar el plan de ElevenLabs y guardar su DPA (C4, C5 y D16), apuntar `railway/limpieza.json` en su servicio, poner `VAPID_PRIVADA`, crear el servicio `recordatorios`.

**Este mes:** DNSSEC (D15).

**Siguiente trimestre:**

- Lectores propios de Santander, BCI y Scotiabank, y CSV de Tenpo, MACH y Mercado Pago (ver [05 · Cartolas](05-CARTOLAS.md#prioridad)).
- D5 y D8, con lo que muestren los avisos de `Respuesta lenta` (ver [10](10-OPERACION.md#respuestas-lentas)). Desde el lote 90, `resumen_mes` ya no se repite dentro de una misma petición.
- D6 y D9, cuando los registros muestren esperas o cortes reales.
- Programa de rotación de secretos con fecha por secreto (ver [10 · Operación](10-OPERACION.md)).
