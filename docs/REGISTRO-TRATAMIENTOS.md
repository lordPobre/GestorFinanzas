# Registro de actividades de tratamiento

Inventario de qué dato personal trata la aplicación, con qué finalidad, dónde vive y cuánto se conserva. Es el documento que pide la Ley 21.719 cuando se fiscaliza: no basta con tener los controles, hay que poder mostrar qué se trata y por qué.

Última revisión: 24 de noviembre de 2026.

| | |
| --- | --- |
| Responsable del tratamiento | Carlos López Figueroa, persona natural, Valparaíso, Chile |
| Canal para el ejercicio de derechos | soporte@perseustechnology.dev |
| Alcance | Servicio abierto al público, con cuentas de usuarios reales |
| Política vigente | La indicada en `finanzas/legal.py` (`VERSION`, `VIGENTE_DESDE`). Los tratamientos 15 y 16 entran con la versión 1.3, el 19 con la 1.6, el 21 con la 1.9 y el 23 con la 1.10 |

---

## 1. Cuenta de usuario

| | |
| --- | --- |
| Datos | Nombre de usuario, correo, contraseña (hash Argon2), nombre y apellido si se ingresan, teléfono, ciudad y país si se ingresan, moneda, fecha de alta, fecha del último acceso, identificador de Google si entra con Google |
| Finalidad | Identificar a la persona y darle acceso a sus propios datos |
| Base de licitud | Ejecución del servicio solicitado por el titular |
| Dónde | Postgres en Railway (`auth_user`, `finanzas_userprofile`). Antes de confirmar el correo, el registro espera en `finanzas_altapendiente`, con la contraseña ya con hash |
| Conservación | Mientras la cuenta exista. Se borra por completo al eliminarla. Un registro sin confirmar, 48 horas |
| Quién accede | El titular. El administrador, solo si `ADMIN_URL` está habilitado, entrando por el mismo acceso con bloqueo y verificación en dos pasos |

## 2. Movimientos financieros

| | |
| --- | --- |
| Datos | Fecha, monto, tipo, categoría, descripción libre y estado de pago de cada ingreso y gasto, y las categorías propias |
| Finalidad | La función central de la aplicación |
| Base de licitud | Ejecución del servicio |
| Dónde | Postgres (`finanzas_transaccion`, `finanzas_categoria`) |
| Conservación | Mientras la cuenta exista |
| Observación | La descripción es texto libre y puede contener datos de terceros o información delicada. Se guarda en claro, protegida por el cifrado en reposo del proveedor. La decisión de no cifrar el campo y sus motivos están en `docs/12-DECISIONES.md` |

## 3. Compras en cuotas, suscripciones, metas, presupuesto y cuentas por pagar

| | |
| --- | --- |
| Datos | Acreedor o nombre, montos, calendario de cobros y pagos, nombre de la meta y aportes, límite mensual, topes por categoría y el último recordatorio de cada tope. Comercios que la persona marcó como «no es una suscripción» (un texto corto derivado de la descripción, sin montos ni fechas) |
| Finalidad | Proyectar los compromisos del mes |
| Base de licitud | Ejecución del servicio |
| Dónde | Postgres (`finanzas_deuda`, `finanzas_pagocuota`, `finanzas_suscripcion`, `finanzas_pagoservicio`, `finanzas_metaahorro`, `finanzas_aportemeta`, `finanzas_presupuesto`, `finanzas_topecategoria`, `finanzas_gastopendiente`, `finanzas_sugerenciadescartada`) |
| Conservación | Mientras la cuenta exista |

## 4. Datos de terceros: personas que deben dinero o a quienes se les debe

| | |
| --- | --- |
| Datos | Nombre y un campo de contacto libre (teléfono, correo o nota), el lado (me debe o le debo), montos prestados o debidos, cuotas y abonos |
| Finalidad | Llevar la cuenta de los préstamos personales del titular, en los dos sentidos |
| Base de licitud | Interés legítimo del titular en administrar sus créditos y deudas personales |
| Dónde | Postgres (`finanzas_persona`, `finanzas_prestamo`, `finanzas_abonoprestamo`) |
| Conservación | Mientras la cuenta exista, o hasta que el titular los borre |
| Observación | **Son datos de personas que no son usuarias de la aplicación y no han dado consentimiento.** El titular los ingresa por su cuenta. La política le advierte que responde de hacerlo con fundamento, que anote lo mínimo y que borre los datos si la persona lo pide. En Debo, el nombre puede aparecer en el recordatorio del teléfono del titular («Hoy vence …») |

## 5. Foto de perfil

| | |
| --- | --- |
| Datos | Imagen, normalmente del rostro |
| Finalidad | Identificación visual dentro de la propia cuenta |
| Base de licitud | Consentimiento: es opcional y la sube el titular |
| Dónde | Cloudflare R2, bucket privado, con nombre de archivo aleatorio |
| Conservación | Hasta que se reemplace o se elimine la cuenta. `limpiar_avatares_huerfanos` retira las que quedan sueltas |
| Observación | Se muestra con enlaces firmados que caducan a las 6 horas (`finanzas/almacenamiento.py`) |

## 6. Cartolas bancarias importadas

| | |
| --- | --- |
| Datos | Movimientos del extracto: fecha, comercio, monto, cuotas. Número de cuenta enmascarado (últimos 4 dígitos) |
| Finalidad | Cargar movimientos sin escribirlos a mano |
| Base de licitud | Ejecución del servicio, a pedido expreso del titular |
| Dónde | El archivo se procesa en memoria y **no se guarda**. Si el documento es de un banco que la app lee con su propio lector y cuadra con los saldos o con el total facturado, no sale del servidor. Si no, el texto se envía a la API de Anthropic (Estados Unidos) con el RUT, el nombre, el correo, el teléfono, los números de tarjeta y de cuenta y la dirección tapados. Las fotos y los PDF escaneados van como imagen y no se pueden tapar. Lo leído queda en la sesión del titular (tabla `django_session`) mientras revisa. Los movimientos que confirma se guardan como transacciones normales. Si la lectura falla, se guarda en la sesión una muestra anonimizada de la estructura del texto (dígitos → 9, palabras → X) para mostrársela una vez |
| Conservación | El archivo, nada. Lo leído, hasta confirmar, descartar o que venza la sesión (8 horas). Lo confirmado, mientras la cuenta exista. En Anthropic, la que aplique el proveedor. El contador de lecturas con IA (20 al mes), en la tabla `Contador` |
| Observación | La lectura con IA no depende del interruptor del análisis con IA: es parte del servicio que el titular pide al subir el archivo. La pantalla de importar lo avisa antes de subirlo |
| Verificable en | `finanzas/cartolas/lector_ia.py` (`tapar`, `_lectura_propia`), `finanzas/tests/test_cartola_ia.py`, `finanzas/tests/test_cartola_lector_propio.py` |

## 7. Verificación en dos pasos

| | |
| --- | --- |
| Datos | Secreto TOTP, último código usado, hash de los códigos de respaldo, marca de uso |
| Finalidad | Proteger el acceso |
| Base de licitud | Seguridad del tratamiento |
| Dónde | Postgres (`finanzas_segundofactor`, `finanzas_codigorespaldo`) |
| Conservación | Mientras esté activa |
| Observación | El secreto y los hashes no se incluyen en la descarga de datos del titular: son credenciales, no información personal entregable |

## 8. Registros de seguridad

| | |
| --- | --- |
| Datos | Tipo de evento (acceso, acceso fallido, salida, bloqueo, código incorrecto, cambios de verificación en dos pasos, Face ID o huella, contraseña, recuperación, sesiones cerradas, descarga de datos, borrado de cuenta, acceso denegado al panel), fecha y hora, usuario o nombre intentado, dirección IP y navegador |
| Finalidad | Detectar ataques y poder reconstruir un incidente |
| Base de licitud | Interés legítimo en la seguridad del servicio |
| Dónde | Postgres (`finanzas_eventoseguridad`), además de la salida estándar del contenedor |
| Conservación | 12 meses. `limpiar_inactivas` borra los más antiguos cada día |
| Observación | Al eliminar una cuenta, sus eventos pierden el vínculo con ella pero conservan el nombre de usuario hasta cumplir los 12 meses: son la evidencia si el borrado lo hizo un tercero. El titular los recibe en su descarga de datos |

## 9. Sesiones abiertas y contadores de bloqueo

| | |
| --- | --- |
| Datos | Por sesión: identificador, IP, navegador, fecha de inicio y de última actividad. Por contador: IP (las IPv6, como red /64), usuario o correo, con la cantidad de intentos. Por aparato conocido: una huella derivada de la cookie `fintora_aparato` y el navegador |
| Finalidad | Que el titular vea y cierre sus sesiones, y que reciba un aviso si alguien entra desde un aparato nuevo. Bloqueo temporal: 5 fallos del mismo usuario desde la misma IP (15 minutos), 20 contra una misma cuenta desde cualquier IP (1 hora) o 50 desde una misma IP contra cualquier cuenta (1 hora) |
| Base de licitud | Seguridad del tratamiento |
| Dónde | Postgres (`finanzas_sesionactiva`, `django_session`, `finanzas_contador`, `finanzas_dispositivoconocido`) |
| Conservación | Sesiones: 8 horas desde la última actividad y 7 días como máximo, o hasta que se cierran. Contadores: 15 minutos a 1 día; `limpieza_diaria` borra los vencidos. Aparatos: mientras exista la cuenta. Las copias de respaldo no llevan los datos de sesiones ni de contadores |

## 10. Correos de la cuenta y aviso mensual

| | |
| --- | --- |
| Datos | Correo del titular. Según el caso: enlace de confirmación, enlace de recuperación, aviso de inactividad, resumen de cobros del mes, aviso de acceso desde un aparato nuevo (navegador y sistema), enlace para confirmar un correo nuevo y aviso al anterior, aviso de registro con un correo que ya tiene cuenta, o aviso de un cambio de la política de privacidad |
| Finalidad | Confirmar el correo, recuperar el acceso, cumplir el plazo de conservación, recordar los cobros por vencer, avisar de cambios de seguridad en la cuenta e informar los cambios de la política |
| Base de licitud | Ejecución del servicio. El aviso mensual, consentimiento: se activa y desactiva desde el perfil. Los avisos de seguridad, interés legítimo en la seguridad. El aviso de la política, la obligación de informar los cambios antes de que rijan |
| Dónde | Se entrega a Resend por API HTTPS |
| Conservación | La que aplique el proveedor a su registro de envíos |

## 11. Análisis con inteligencia artificial

| | |
| --- | --- |
| Datos enviados | **Solo agregados numéricos**: ingreso y gasto mensual promedio, cuota total, deuda restante, flujo libre, ratio deuda/ingreso, meses restantes, cantidad de deudas, nivel de riesgo, tendencia y factores de riesgo. En «Explicar mi plan», los montos del plan para tu plata |
| Datos que NO se envían | Nombre, correo, nombre de usuario, descripciones de movimientos, nombres de personas, cualquier identificador |
| Finalidad | Traducir el diagnóstico numérico a lenguaje natural |
| Base de licitud | Consentimiento, revocable en Perfil → Análisis con IA (`UserProfile.analisis_ia`). Apagado, `views/analisis.analisis_ia` no llama a la API |
| Dónde | API de Anthropic, Estados Unidos |
| Conservación | La que aplique el proveedor. La aplicación no guarda la respuesta |
| Verificable en | `finanzas/ia.py`, función `_construir_prompt`, y `finanzas/ia_plan.py` |

## 12. Encuesta de satisfacción

| | |
| --- | --- |
| Datos | Antigüedad y frecuencia de uso, notas de 1 a 5 y de 0 a 10, pantallas que usa, textos libres sobre la app |
| Finalidad | Mejorar la aplicación |
| Base de licitud | Consentimiento: es voluntaria y se puede posponer u omitir |
| Dónde | Postgres (`finanzas_respuestaencuesta`) |
| Conservación | Mientras la cuenta exista |
| Quién accede | Solo cuentas de personal (`is_staff`), en la página de resultados |

## 13. Acceso con Face ID o huella

| | |
| --- | --- |
| Datos | Identificador de la credencial, clave pública, contador de firmas, nombre del dispositivo, fecha de alta y de último uso |
| Datos que NO se tratan | La cara, la huella o cualquier dato biométrico. El dispositivo los verifica y solo entrega una firma |
| Finalidad | Entrar sin contraseña |
| Base de licitud | Consentimiento: lo activa el titular por dispositivo y lo puede quitar |
| Dónde | Postgres (`finanzas_passkey`) |
| Conservación | Hasta que el titular lo quite o elimine la cuenta |

## 14. Respaldos de la base

| | |
| --- | --- |
| Datos | Copia completa de la base, incluidos todos los tratamientos anteriores |
| Finalidad | Recuperar el servicio ante pérdida o daño de la base |
| Base de licitud | Seguridad del tratamiento |
| Dónde | Bucket privado de Cloudflare R2, distinto del de las fotos, cifrado en reposo por el proveedor. Además, los respaldos del servicio Postgres de Railway |
| Conservación | 30 copias diarias. Una cuenta eliminada desaparece de los respaldos cuando rota la última copia que la contenía. Si hubiera que restaurar una copia, las cuentas eliminadas después se vuelven a borrar |

## 15. Chat de ayuda de la página de inicio

| | |
| --- | --- |
| Datos | Texto de las preguntas del visitante y de las respuestas, dentro de la misma conversación (máximo las últimas 12 intervenciones de 600 caracteres). Dirección IP, solo para el contador de preguntas |
| Datos que NO se envían | Ningún dato de la cuenta, aunque el visitante haya iniciado sesión |
| Finalidad | Responder dudas sobre la aplicación |
| Base de licitud | Consentimiento: el chat se usa solo si la persona escribe en él. La interfaz advierte que no se escriban claves ni datos del banco |
| Dónde | La conversación vive en la pestaña del navegador y se envía a la API de Anthropic (Estados Unidos). El contador por IP, en la caché de Postgres |
| Conservación | La conversación, no se guarda en el servidor. El contador por IP, 1 hora. En Anthropic, la que aplique el proveedor |
| Verificable en | `finanzas/chat_ayuda.py`, `finanzas/views/landing.py` |

## 16. Formulario de contacto del chat

| | |
| --- | --- |
| Datos | Correo del visitante y su pregunta |
| Finalidad | Responder por correo lo que el chat no supo o cuando se acabó el cupo de preguntas |
| Base de licitud | Consentimiento: el visitante deja su correo para que le respondan |
| Dónde | Se envía por Resend al buzón de soporte@perseustechnology.dev. No se guarda en la base |
| Conservación | En el buzón de soporte hasta responder y cerrar la consulta |

## 17. Voz de la esfera

| | |
| --- | --- |
| Datos enviados | La frase de la esfera de la pantalla (estado del mes, montos, y en Me deben los nombres de las personas y lo que deben, hasta 5). En la primera visita después de entrar, además el saludo con el nombre del titular y el cambio de estado |
| Datos que NO se envían | Correo, nombre de usuario, identificadores, descripciones de movimientos |
| Finalidad | Leer en voz alta el resumen de la pantalla |
| Base de licitud | Consentimiento, con el mismo interruptor del análisis con IA (`UserProfile.analisis_ia`). Apagado, la pantalla no trae textos firmados y la vista responde 403 |
| Dónde | API de ElevenLabs, Estados Unidos. El audio, en la caché de Postgres |
| Conservación | El audio, 6 horas. `UserProfile.esfera_estado_visto`, mientras exista la cuenta. En ElevenLabs, la que aplique el proveedor |
| Verificable en | `finanzas/voz.py`, `finanzas/views/voz.py`, `finanzas/templatetags/voz.py`, `finanzas/servicios/esfera.py` |

## 18. Medición en las páginas públicas

| | |
| --- | --- |
| Datos | Visita a la portada, las páginas legales, entrar o registro: página, origen, aparato. Con consentimiento, las cookies de Google Analytics y de los píxeles de Meta, TikTok y X, y el evento de registro (sin correo, nombre ni montos) |
| Finalidad | Saber de dónde llegan las personas y medir los anuncios |
| Base de licitud | Plausible, sin cookies: interés legítimo. El resto: consentimiento en el aviso de cookies, revocable desde «Cookies» en el pie |
| Dónde | Plausible (Unión Europea), Google, Meta, TikTok y X. Nada dentro de la app |
| Conservación | La que aplique cada proveedor. La decisión de cookies, en el navegador |
| Verificable en | `finanzas/marketing.py`, `static/js/consentimiento.js`, `finanzas/tests/test_seo.py`, `finanzas/tests/test_evento_registro.py` |

## 19. Recordatorios en el teléfono

| | |
| --- | --- |
| Datos | Por aparato: la dirección que entrega el navegador para recibir avisos (`endpoint`), sus claves de cifrado (`p256dh`, `auth`), el navegador, la fecha de alta y la del último envío. Por cuenta: las cinco opciones y el último día de envío |
| Datos enviados | El texto del aviso: el nombre de lo que vence (cuota, suscripción, cuenta o persona a quien se le debe), la categoría de un tope y, solo si la persona activa «Mostrar montos», los montos |
| Finalidad | Recordar los cobros y los topes sin abrir la app |
| Base de licitud | Consentimiento: el navegador pide permiso en cada aparato. Se apaga en Perfil o en los ajustes del teléfono |
| Dónde | Postgres (`finanzas_suscripcionpush` y los campos `push_*` de `finanzas_userprofile`). El aviso viaja por el servicio de avisos del navegador, cifrado de punta a punta: ese servicio no puede leerlo |
| Conservación | Hasta que se apague en el aparato, el servicio responda que el aparato ya no existe o se elimine la cuenta. Hasta 10 aparatos por cuenta |
| Verificable en | `finanzas/push.py`, `finanzas/servicios/recordatorios.py`, `finanzas/views/recordatorios.py`, `finanzas/tests/test_recordatorios.py` |

## 20. Revisión de movimientos repetidos con IA

| | |
| --- | --- |
| Datos enviados | De cada par dudoso (mismo monto, fechas cercanas): fecha, tipo, monto, categoría y descripción de los dos movimientos, hasta 80 caracteres por descripción |
| Datos que NO se envían | Nombre, correo, nombre de usuario, identificadores |
| Finalidad | Decidir si dos movimientos son el mismo anotado dos veces, al importar una cartola y en Perfil → Movimientos repetidos |
| Base de licitud | Consentimiento, con el interruptor del análisis con IA (`UserProfile.analisis_ia`). Apagado, solo se usan las reglas propias |
| Dónde | API de Anthropic, Estados Unidos. El veredicto, en la caché de Postgres |
| Conservación | El veredicto (sí o no), 30 días, con una clave que es un hash del par. En Anthropic, la que aplique el proveedor |
| Verificable en | `finanzas/ia_repetidos.py`, `finanzas/servicios/repetidos.py` |

## 21. Preguntas a la esfera

| | |
| --- | --- |
| Datos enviados | A Anthropic: la pregunta (hasta 300 caracteres), las anteriores de la misma conversación (hasta 4) y las cifras que entregan las herramientas para responderla: lo que queda del mes, el gasto de una categoría, las cuotas por mes, cuándo termina una deuda y cómo van las metas. Los nombres de las deudas y las metas van como alias (Deuda 1, Meta 1). A ElevenLabs: la grabación, si la pregunta se hace con la voz, y la respuesta para leerla en voz alta |
| Datos que NO se envían | Correo, nombre de usuario, descripciones de movimientos, nombres de deudas o metas |
| Finalidad | Responder preguntas sobre la plata del titular |
| Base de licitud | Consentimiento, con el interruptor del análisis con IA y la política vigente aceptada (`ia_preguntas.puede_preguntar`) |
| Dónde | APIs de Anthropic y ElevenLabs, Estados Unidos. La conversación y el contador diario, en Postgres |
| Conservación | La conversación, 30 minutos en la caché. La grabación, no se guarda: se pasa a texto en memoria. El contador (30 preguntas al día), 2 días. En los proveedores, la que apliquen |
| Verificable en | `finanzas/ia_preguntas.py`, `finanzas/servicios/preguntas.py` |

## 22. Clave personal para anotar desde afuera

| | |
| --- | --- |
| Datos | Hash de la clave (la clave se muestra una sola vez y no se guarda), sus primeros caracteres para reconocerla, fecha de creación y del último uso. Lo que se anota con ella queda como un movimiento normal |
| Finalidad | Anotar gastos desde un atajo del teléfono o el bot de Telegram sin abrir la app |
| Base de licitud | Ejecución del servicio, a pedido del titular |
| Dónde | Postgres (`finanzas_claveapi`). Si el análisis con IA está activado y el servidor no entiende la frase, la frase se envía a la API de Anthropic para leer el monto, la categoría y la fecha |
| Conservación | Hasta que el titular la revoque o elimine la cuenta |
| Verificable en | `finanzas/models/api.py`, `finanzas/servicios/anotar_texto.py` |

## 23. Anotar desde Telegram

| | |
| --- | --- |
| Datos | Número del chat, nombre en Telegram, fecha de conexión y del último uso. Los mensajes y audios que el titular le manda al bot y las respuestas |
| Finalidad | Anotar gastos escribiéndole o grabándole al bot |
| Base de licitud | Ejecución del servicio, a pedido del titular: lo conecta con un enlace de un solo uso que dura 10 minutos y lo corta con /desconectar o desde el perfil. Los audios y las frases que se leen con IA, consentimiento con el interruptor del análisis con IA |
| Dónde | Postgres (`finanzas_chattelegram`). Los mensajes pasan por los servidores de Telegram. Los audios se pasan a texto con ElevenLabs y las frases que el servidor no entiende se leen con Anthropic |
| Conservación | La conexión, hasta desconectarla o eliminar la cuenta. Los audios, no se guardan. En Telegram y en los proveedores de IA, la que apliquen |
| Verificable en | `finanzas/models/telegram.py`, `finanzas/views/telegram.py` |

---

## Encargados del tratamiento y transferencias internacionales

Todos los proveedores están fuera de Chile, lo que constituye transferencia internacional y se declara en la política de privacidad.

| Proveedor | Qué trata | País | Acuerdo de tratamiento |
| --- | --- | --- | --- |
| Railway | Cómputo y base de datos completa | Estados Unidos | DPA firmado el 2026-09-24 (firma aparte, railway.com/legal/dpa) |
| Cloudflare R2 | Fotos de perfil y respaldos de la base | Red global | Customer DPA v6.4, incorporado al Self-Serve Subscription Agreement, revisado y descargado el 2026-09-23 |
| Resend | Correo del titular y contenido de los correos de la cuenta y del aviso; correo y pregunta del formulario de contacto | Estados Unidos | DPA prefirmado por Resend, vigente desde el alta de la cuenta; copia firmada descargada el 2026-09-23 |
| Anthropic | Agregados numéricos del análisis y montos del plan; texto del chat de ayuda; contenido de las cartolas que no lee el lector propio, con los datos personales tapados salvo en fotos y escaneos; preguntas a la esfera con sus cifras; pares de movimientos repetidos dudosos; frases de Telegram o de la clave personal que el servidor no entiende | Estados Unidos | DPA incorporado a los Commercial Terms, revisados y descargados el 2026-09-23 |
| Servicio de avisos del navegador: Google (Chrome y Android), Mozilla (Firefox), Apple (Safari) o Microsoft (Edge) | El recordatorio cifrado, sin poder leerlo; la dirección del aparato y la hora del envío | Estados Unidos | Lo elige el navegador de la persona. Sin contrato con Fintora |
| Google | Identidad al entrar con cuenta de Google | Estados Unidos | Términos del servicio de identidad |
| ElevenLabs | Texto que lee la esfera: montos, nombres de las personas de Me deben, el nombre del saludo y las respuestas a las preguntas. Grabaciones de las preguntas con la voz y audios del bot de Telegram, para pasarlos a texto | Estados Unidos | Por documentar: descargar el DPA al contratar el plan de pago |
| Telegram (si el titular conecta el bot) | Los mensajes y audios que el titular le manda al bot y sus respuestas | Internacional | Términos de la plataforma de bots de Telegram. Sin DPA: lo elige el titular al conectarlo |
| Sentry (si `SENTRY_DSN` está activo) | Errores de la aplicación, sin datos personales (`send_default_pii=False`) | Estados Unidos | Por documentar |
| Plausible (si `PLAUSIBLE_DOMINIO` está activo) | Visitas a las páginas públicas, sin cookies | Unión Europea | Términos del servicio |
| Google Analytics, Meta, TikTok, X (si su variable está activa) | Visitas a las páginas públicas y el evento de registro, con consentimiento | Estados Unidos e internacional | Términos de cada plataforma |

## Plazos de conservación

| Dato | Plazo | Estado |
| --- | --- | --- |
| Todo lo de la cuenta | Mientras la cuenta exista | Aplicado |
| Cuenta sin ningún acceso | Aviso a los 12 meses, borrado 30 días después | Aplicado: tarea diaria `limpiar_inactivas` |
| Registros de seguridad | 12 meses | Aplicado: purgado por `limpiar_inactivas` |
| Respaldos de la base | 30 días | Aplicado: rotación de `respaldar_postgres` |
| Contadores de bloqueo y del chat | 15 minutos a 1 día | Aplicado: tabla `Contador` y `limpieza_diaria` |
| Sesiones | 8 horas desde la última actividad, 7 días como máximo | Aplicado: `SesionAbsolutaMiddleware` y `limpieza_diaria` |
| Aparatos conocidos | Mientras la cuenta exista | Aplicado: borrado en cascada |
| Correo nuevo sin confirmar | 48 horas | Aplicado: el enlace vence |
| Registro sin confirmar | 48 horas | Aplicado: `alta.purgar` y el enlace vence |
| Audio de la voz de la esfera | 6 horas | Aplicado: caché |
| Conversación con la esfera | 30 minutos | Aplicado: caché |
| Grabación de una pregunta y audio de Telegram | No se guarda | Aplicado: se pasa a texto en memoria |
| Veredicto de repetidos con IA | 30 días | Aplicado: caché, solo sí o no |
| Conexión con Telegram | Hasta desconectarla o eliminar la cuenta | Aplicado: `/desconectar`, el perfil y borrado en cascada |
| Clave personal | Hasta revocarla o eliminar la cuenta | Aplicado: se guarda solo su hash |
| Aparatos con recordatorios | Hasta apagarlos, que el servicio los dé por vencidos o se borre la cuenta | Aplicado: `push_quitar`, borrado ante 404 o 410 y en cascada |
| Archivo de cartola | No se guarda | Aplicado |
| Lo leído de una cartola | Hasta 8 horas, en la sesión | Aplicado; se declara en la política 1.3 |
| Conversación del chat | No se guarda | Aplicado |
| Formulario del chat | Hasta cerrar la consulta | Manual, en el buzón de soporte |

`UserProfile.ultima_actividad` es el campo sobre el que se mide la inactividad. Lo escribe `ActividadMiddleware` una vez al día. `last_login` no sirve solo: una sesión recordada lo deja congelado.

## Derechos del titular: estado

| Derecho | Cómo se ejerce hoy |
| --- | --- |
| Acceso y portabilidad | Perfil → Descargar todos mis datos (JSON), y exportación a Excel y CSV |
| Rectificación | Cada dato se edita desde su propia pantalla |
| Supresión | Perfil → Seguridad → Eliminar mi cuenta. Borra todo de inmediato |
| Oposición al análisis con IA | Perfil → Análisis con IA, apagado. Apaga también la voz, las preguntas a la esfera, los repetidos con IA y los audios de Telegram. La lectura de cartolas con IA se evita subiendo el PDF o el Excel de un banco con lector propio |
| Oposición al correo mensual | Perfil → Aviso mensual, apagado |
| Oposición a los recordatorios | Perfil → Recordatorios en este aparato, apagado, o los ajustes del teléfono |
| Desconectar Telegram o la clave personal | /desconectar en el bot, o Perfil → Anotar desde Telegram → Revocar |
| Canal formal de solicitudes | soporte@perseustechnology.dev, respuesta en 30 días corridos |
| Evidencia del consentimiento | `UserProfile.politica_version` y `politica_aceptada`, registrados en el alta y al aceptar cada versión nueva |
