# 07 · Privacidad y cumplimiento

Fintora trata datos personales de residentes en Chile y está sujeta a la **Ley 21.719 sobre protección de datos personales**. Este capítulo resume cómo se cumple y dónde está la evidencia. El inventario formal es `docs/REGISTRO-TRATAMIENTOS.md` (anexo obligatorio) y el texto que ven los usuarios es `/privacidad/`.

| | |
| --- | --- |
| Responsable | Carlos López Figueroa, persona natural, Valparaíso, Chile. Es también el titular de los derechos sobre la aplicación y su código |
| Contacto y derechos | soporte@perseustechnology.dev, respuesta en 30 días corridos |
| Política vigente | Versión y fecha en `finanzas/legal.py` (`VERSION`, `VIGENTE_DESDE`). Hoy, la 1.10, vigente desde el 14 de noviembre de 2026: suma Telegram y las frases que se leen con Anthropic |
| Edad | Pensada para mayores de 18 años |

## Principios aplicados en el diseño

- **Minimización.** No se pide RUT ni número de tarjeta y nunca se pide la clave del banco. Nombre, teléfono, ciudad y foto son opcionales.
- **Sin conexión bancaria.** Todo lo que la app sabe lo anotó o lo subió la persona.
- **Sin terceros dentro de la app.** Fuentes, íconos y gráficos se sirven desde el propio servidor. Dentro de la app no hay analítica, píxeles ni publicidad. Lo prueba `test_terceros_fotos_cache.py`. Las páginas públicas pueden medir visitas, como se explica más abajo.
- **Cartolas sin archivo.** El PDF se lee y se descarta. Si el banco tiene lector propio y la lectura cuadra, no sale del servidor. Si no, va a Anthropic con los datos personales tapados (en fotos y escaneos no se pueden tapar). Ver la salvedad sobre la sesión más abajo.
- **IA con lo mínimo.** El análisis envía números, no textos. El chat envía solo lo que la persona escribe en él. Las preguntas a la esfera envían la pregunta y las cifras para responderla, con las deudas y metas como alias. La voz envía la frase que se lee en pantalla (en Me deben incluye los nombres de las personas) y, al entrar, el nombre del saludo. Los repetidos dudosos envían fecha, monto, categoría y descripción de cada par.
- **Borrado real.** Eliminar la cuenta borra todo en cascada en el momento.

## Qué se trata y con qué base

| Tratamiento | Base de licitud |
| --- | --- |
| Cuenta, movimientos, cuotas, suscripciones, metas, presupuesto | Ejecución del servicio pedido |
| Personas de “Me deben” y “Debo” (terceros que no son usuarios) | Interés legítimo del titular. Quien los ingresa responde de hacerlo con fundamento, y la política se lo advierte |
| Foto de perfil | Consentimiento (opcional) |
| Aviso mensual por correo | Consentimiento, revocable en el perfil |
| Recordatorios en el teléfono | Consentimiento, por aparato: el navegador pide permiso. Se apagan en el perfil o en los ajustes del teléfono |
| Análisis con IA, voz, preguntas a la esfera, repetidos dudosos y audios de Telegram | Consentimiento, revocable en el perfil (`analisis_ia`). Un solo interruptor los apaga todos |
| Lectura de cartolas | Ejecución del servicio, a pedido del titular. No depende del interruptor de la IA y la pantalla de importar lo avisa |
| Anotar desde Telegram y con la clave personal | Ejecución del servicio, a pedido del titular. Se conecta y se corta desde el perfil |
| Chat de ayuda | Consentimiento: solo si la persona escribe |
| Formulario de contacto del chat | Consentimiento: al dejar su correo |
| Face ID o huella | Consentimiento, por dispositivo |
| Encuesta | Consentimiento: voluntaria |
| Registro de seguridad, contadores de bloqueo, aparatos conocidos y avisos de acceso | Interés legítimo en la seguridad |
| Medición sin cookies en las páginas públicas (Plausible) | Interés legítimo |
| Analítica y píxeles en las páginas públicas (Google Analytics, Meta, TikTok, X) | Consentimiento: el aviso de cookies, revocable desde «Cookies» en el pie |
| Respaldos | Seguridad del tratamiento |

El **consentimiento a la política** se registra en el alta (`politica_version`, `politica_aceptada`), con una casilla obligatoria. Cuando la versión cambia, `avisar_politica` la avisa por correo, el Inicio muestra una franja con el enlace y el botón «Aceptar», y el perfil también la pide. La franja llega a las cuentas sin correo. `test_privacidad.py` prueba que sin aceptar no se crea la cuenta.

## Derechos del titular

Casi todos son botones en la app, sin pedir permiso:

| Derecho | Cómo | Código |
| --- | --- | --- |
| Acceso y portabilidad | *Perfil → Descargar todos mis datos*: JSON con todo, al instante. Además, Excel y CSV de los movimientos, y *Perfil → Actividad de la cuenta* con los accesos de 90 días | `perfil.mis_datos`, `views/actividad.py` |
| Rectificación | Cada dato se edita en su pantalla | |
| Supresión | *Perfil → Seguridad → Eliminar mi cuenta*: hay que escribir ELIMINAR y la contraseña | `cuenta.eliminar_cuenta` |
| Oposición a la IA | *Perfil → Análisis con IA*: con el interruptor apagado el servidor no llama a Anthropic ni a ElevenLabs | `analisis.analisis_ia`, `templatetags/voz.puede_usar` |
| Oposición al correo mensual | *Perfil → Aviso mensual* | |
| Reclamo | Correo a soporte. Si no queda resuelto, la Agencia de Protección de Datos Personales | |

La descarga de datos excluye las credenciales (secreto 2FA, hashes de los códigos, clave pública de las passkeys, contraseña). Incluye los eventos de seguridad de la propia cuenta. `test_derechos.py` prueba que trae lo propio y no lo ajeno.

## Plazos de conservación

| Dato | Plazo | Cómo se cumple |
| --- | --- | --- |
| Todo lo de la cuenta | Mientras exista | Borrado en cascada al eliminarla |
| Cuenta sin uso | Aviso a los 12 meses, borrado 30 días después | `limpiar_inactivas`, diaria |
| Registro de seguridad | 12 meses, también después de borrar la cuenta (sin vínculo, con el nombre de usuario) | Purga en `limpiar_inactivas` |
| Respaldos | 30 copias diarias | Rotación de `respaldar_postgres` |
| Contadores de bloqueo | 15 min a 1 h | Tabla `Contador`. Dejan de contar al vencer y `limpieza_diaria` los borra |
| Contador del chat por IP | Hasta 1 día | Tabla `Contador` |
| Sesiones | 8 h sin uso, 7 días como máximo | `SesionAbsolutaMiddleware` y `limpieza_diaria` (`clearsessions`) |
| Aparatos conocidos | Mientras exista la cuenta | Borrado en cascada |
| Correo nuevo sin confirmar | 48 h | El enlace vence |
| Registro sin confirmar | 48 h | `alta.purgar` al registrarse alguien y al abrir un enlace vencido |
| Audio de la voz | 6 h | Caché del servidor |
| Conversación con la esfera | 30 min | Caché del servidor |
| Grabación de una pregunta y audio de Telegram | No se guarda | Se pasa a texto en memoria |
| Veredicto de repetidos con IA | 30 días | Caché, solo sí o no |
| Conexión con Telegram | Hasta desconectarla o borrar la cuenta | `/desconectar`, el perfil y borrado en cascada |
| Clave personal | Hasta revocarla o borrar la cuenta | Se guarda solo su hash |
| Aparatos con recordatorios | Hasta apagarlos, que el servicio de avisos diga que el aparato ya no existe o se borre la cuenta | `push_quitar`, borrado ante 404 o 410 y en cascada |
| Conversación del chat | No se guarda en el servidor | Vive en la pestaña |
| Formulario del chat | En el buzón de soporte hasta cerrar la consulta | Manual |
| Archivo de cartola | No se guarda | Se procesa en memoria |
| Lo leído de una cartola, antes de confirmar | Hasta confirmar, descartar o que venza la sesión (8 h) | Sesión en la base. Declarado desde la versión 1.3 |

## Encargados y transferencias internacionales

Todos los proveedores están fuera de Chile. Cada transferencia se declara en la política.

| Proveedor | Qué recibe | País | Acuerdo |
| --- | --- | --- | --- |
| Railway | Aplicación y base completa | EE. UU. | DPA firmado el 24/09/2026 |
| Cloudflare R2 | Fotos y respaldos, en almacenamiento privado | Red global | Customer DPA v6.4 |
| Resend | Correo y contenido del aviso mensual, de la verificación, de la recuperación y del formulario de contacto | EE. UU. | DPA prefirmado |
| Anthropic | Agregados del análisis y montos del plan, texto del chat, cartolas que no lee el lector propio (con los datos tapados salvo en fotos y escaneos), preguntas a la esfera con sus cifras, pares de repetidos dudosos y frases de Telegram o de la clave personal que el servidor no entiende | EE. UU. | DPA en los Commercial Terms |
| Google | Identidad, solo al entrar con Google | EE. UU. | Términos del servicio de identidad |
| Servicio de avisos del navegador (Google, Mozilla, Apple o Microsoft, según el aparato) | El recordatorio cifrado, que no puede leer. Ve la dirección del aparato y la hora del envío | EE. UU. | Lo elige el navegador de la persona. No hay contrato con Fintora |
| ElevenLabs | Texto que la esfera lee en voz alta (montos, en Me deben los nombres de las personas y lo que deben, el nombre del saludo y las respuestas a las preguntas), grabaciones de las preguntas con la voz y audios del bot de Telegram. Solo con el análisis con IA activado | EE. UU. | Por documentar (ver pendientes) |
| Telegram (si se conecta el bot) | Los mensajes y audios que la persona le manda al bot y sus respuestas | Internacional | Términos de la plataforma de bots. Sin DPA: lo elige la persona al conectarlo |
| Sentry (si está activo) | Errores de la aplicación, sin datos personales (`send_default_pii=False`) | EE. UU. | Por documentar |
| Plausible (si está activo) | Visitas a las páginas públicas, sin cookies | UE | Términos del servicio |
| Google Analytics, Meta, TikTok, X (si están activos) | Visitas a las páginas públicas y el evento de registro, solo con consentimiento | EE. UU. e internacional | Términos de cada plataforma |

Las copias de los DPA se guardan fuera del repositorio, en `legal/dpa/`, con la fecha en el nombre.

## Inteligencia artificial

**Análisis** (`ia.py`): envía ingreso y gasto promedio, cuota total, deuda restante, flujo libre, DTI, meses para saldar, cantidad de deudas, nivel de riesgo, tendencia y los factores de riesgo. No envía nombre, usuario, correo, descripciones de movimientos ni nombres de personas. Se puede verificar leyendo `_construir_prompt`. La respuesta no se guarda.

**Voz de la esfera** (`voz.py`): envía la frase de la esfera (los montos y el estado del mes de esa pantalla; en Me deben, también los nombres de hasta 5 personas y lo que deben) y, en la primera visita después de entrar, el saludo con el nombre y el cambio de estado. No envía correo, usuario ni identificadores. El servidor solo acepta textos firmados por él mismo para esa persona, así que la ruta no sirve para que ElevenLabs lea otra cosa. El audio queda 6 horas en la caché del servidor.

**Chat de ayuda** (`chat_ayuda.py`): envía el texto de la conversación, como máximo las últimas 12 intervenciones de hasta 600 caracteres. No envía ningún dato de la cuenta, aunque la persona esté dentro. Las instrucciones le prohíben pedir claves o datos del banco y le piden advertir si alguien los escribe. No se guarda nada en el servidor.

**Lectura de cartolas** (`cartolas/lector_ia.py`): primero prueba el lector propio del banco; si la lectura cuadra con los saldos o el total, no se llama a la IA. Si no, envía el texto con `tapar()` aplicado (RUT, nombre, correo, teléfono, tarjeta, cuenta y dirección), en partes de 5.000 caracteres. Las fotos y los escaneos van como imagen. Hasta 20 lecturas con IA al mes por cuenta. El servidor comprueba cada monto contra el archivo.

**Preguntas a la esfera** (`ia_preguntas.py`): envía la pregunta, hasta 4 turnos de la conversación y las cifras de las herramientas de `servicios/preguntas.py`, con los nombres de deudas y metas cambiados por alias. Con la voz, la grabación se pasa a texto con ElevenLabs en memoria. La conversación dura 30 minutos en la caché. Hasta 30 preguntas al día.

**Repetidos** (`ia_repetidos.py`): solo los pares dudosos, con fecha, tipo, monto, categoría y descripción. Se guarda el veredicto 30 días.

**Telegram y clave personal** (`views/telegram.py`, `servicios/anotar_texto.py`): las frases se leen primero con reglas propias. Solo si no alcanzan y el análisis con IA está activado, la frase va a Anthropic. Los audios del bot se pasan a texto con ElevenLabs y no se guardan.

## Registro de seguridad

`EventoSeguridad` registra 23 tipos de evento, con fecha, IP, navegador y usuario o nombre intentado: accesos y fallos, bloqueos, cambios de 2FA, Face ID, contraseña, sesiones cerradas, descarga de datos, borrado de cuenta, accesos denegados al admin, cambios de correo, accesos desde un aparato nuevo y sesiones vencidas. La persona ve los suyos en *Perfil → Actividad de la cuenta*, salvo los del admin y el borrado. Es de solo lectura en el admin. Sirve para detectar ataques y reconstruir un incidente. Al borrar una cuenta, sus eventos pierden el vínculo pero conservan el nombre de usuario hasta cumplir 12 meses: son la evidencia si el borrado lo hizo otra persona.

## Brechas

Ver [10 · Operación](10-OPERACION.md#incidentes-de-seguridad) y `docs/BRECHAS.md`.

## Pendientes de cumplimiento

C1, C2 y C3 se resolvieron en la entrega de arreglos (ver [13 · Deuda técnica](13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md)). C7 se resolvió en el lote 88: como el lote 86 había sumado los recordatorios a la 1.5 ya publicada, la política pasó a 1.6, y quien aceptó la 1.5 tiene que aceptar de nuevo. Quedan abiertos:

- **C4. Aviso de la política vigente.** Revisar en `politica_avisada` que las cuentas activas recibieron el aviso de la 1.10. Si falta alguna, correr `avisar_politica`, que manda solo a las que faltan.
- **C5. Acuerdo con ElevenLabs.** Revisar y descargar su DPA y guardarlo en `legal/dpa/`. El plan gratuito no permite uso comercial: en producción hace falta un plan de pago.
- **C6. Acuerdos de Sentry y de los proveedores de medición**, si se activan.
- **C8. Plazo del registro sin confirmar.** El lote 90 guarda hasta 48 horas lo que se escribe al registrarse, antes de que exista la cuenta. Sumarlo a la tabla de plazos de `/privacidad/` en la próxima versión de la política, junto con su aviso.
- **C9. Lector propio antes que la IA (lote 282).** `/privacidad/` dice que la cartola se le pide a Anthropic. Desde el lote 282, si el banco tiene lector propio y la lectura cuadra, no sale del servidor. Es menos de lo que la política declara, así que no obliga a una versión nueva. Ajustar el texto en la próxima.

## Para un auditor

| Pregunta | Dónde mirar |
| --- | --- |
| ¿Qué datos se tratan y por qué? | `docs/REGISTRO-TRATAMIENTOS.md`, `/privacidad/` |
| ¿Qué acepta el usuario? | `/privacidad/`, `/terminos/`, `registration/registro.html`, `UserProfile.politica_*` |
| ¿Se pueden ejercer los derechos? | `views/perfil.py` (`mis_datos`, `eliminar_cuenta`), `test_derechos.py` |
| ¿Se respetan los plazos? | `inactividad.py`, `auditoria.purgar`, `respaldar_postgres._rotar`, `test_conservacion.py` |
| ¿Qué sale hacia terceros? | `ia._construir_prompt`, `chat_ayuda`, `voz.py` y `views/voz.py`, `correo.py`, `marketing.py`, `test_terceros_fotos_cache.py`, `test_voz.py`, `push.py` y `servicios/recordatorios.py` con `test_recordatorios.py`, la CSP en `middleware.py` |
| ¿Cómo se protege? | [06 · Seguridad](06-SEGURIDAD.md) |
| ¿Qué pasa ante una brecha? | `docs/BRECHAS.md` |
| ¿Hay contratos con los encargados? | Tabla de encargados y `legal/dpa/` |
