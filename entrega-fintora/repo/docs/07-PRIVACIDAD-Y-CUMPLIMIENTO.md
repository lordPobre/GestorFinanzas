# 07 · Privacidad y cumplimiento

Fintora trata datos personales de residentes en Chile y está sujeta a la **Ley 21.719 sobre protección de datos personales**. Este capítulo resume cómo se cumple y dónde está la evidencia. El inventario formal es `docs/REGISTRO-TRATAMIENTOS.md` (anexo obligatorio) y el texto que ven los usuarios es `/privacidad/`.

| | |
| --- | --- |
| Responsable | Carlos López Figueroa, persona natural, Valparaíso, Chile |
| Contacto y derechos | soporte@perseustechnology.dev, respuesta en 30 días corridos |
| Política vigente | Versión y fecha en `finanzas/legal.py` (`VERSION`, `VIGENTE_DESDE`). Con la entrega de arreglos: 1.3, vigente desde el 8 de octubre de 2026 |
| Edad | Pensada para mayores de 18 años |

## Principios aplicados en el diseño

- **Minimización.** No se pide RUT ni número de tarjeta y nunca se pide la clave del banco. Nombre, teléfono, ciudad y foto son opcionales.
- **Sin conexión bancaria.** Todo lo que la app sabe lo anotó o lo subió la persona.
- **Sin terceros en el navegador.** Fuentes, íconos y gráficos se sirven desde el propio servidor. No hay analítica, píxeles ni publicidad. Lo prueba `test_terceros_fotos_cache.py`.
- **Cartolas sin archivo.** El PDF se lee y se descarta. Ver la salvedad sobre la sesión más abajo.
- **IA con agregados.** El análisis envía números, no textos. El chat envía solo lo que la persona escribe en él.
- **Borrado real.** Eliminar la cuenta borra todo en cascada en el momento.

## Qué se trata y con qué base

| Tratamiento | Base de licitud |
| --- | --- |
| Cuenta, movimientos, cuotas, suscripciones, metas, presupuesto | Ejecución del servicio pedido |
| Personas de “Me deben” (terceros que no son usuarios) | Interés legítimo del titular. Quien los ingresa responde de hacerlo con fundamento, y la política se lo advierte |
| Foto de perfil | Consentimiento (opcional) |
| Aviso mensual por correo | Consentimiento, revocable en el perfil |
| Análisis con IA | Consentimiento, revocable en el perfil (`analisis_ia`) |
| Chat de ayuda | Consentimiento: solo si la persona escribe |
| Formulario de contacto del chat | Consentimiento: al dejar su correo |
| Face ID o huella | Consentimiento, por dispositivo |
| Encuesta | Consentimiento: voluntaria |
| Registro de seguridad, contadores de bloqueo | Interés legítimo en la seguridad |
| Respaldos | Seguridad del tratamiento |

El **consentimiento a la política** se registra en el alta (`politica_version`, `politica_aceptada`), con una casilla obligatoria. Cuando la versión cambia, el perfil lo muestra y pide aceptar la nueva. `test_privacidad.py` prueba que sin aceptar no se crea la cuenta.

## Derechos del titular

Casi todos son botones en la app, sin pedir permiso:

| Derecho | Cómo | Código |
| --- | --- | --- |
| Acceso y portabilidad | *Perfil → Descargar todos mis datos*: JSON con todo, al instante. Además, Excel y CSV de los movimientos | `cuenta.mis_datos` |
| Rectificación | Cada dato se edita en su pantalla | |
| Supresión | *Perfil → Seguridad → Eliminar mi cuenta*: hay que escribir ELIMINAR y la contraseña | `cuenta.eliminar_cuenta` |
| Oposición a la IA | *Perfil → Análisis con IA*: con el interruptor apagado el servidor no llama a la API | `analisis.analisis_ia` |
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
| Contadores de bloqueo | 15 min a 1 h | Expiran solos en la caché |
| Contador del chat por IP | 1 h | Caché |
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
| Anthropic | Agregados del análisis y texto del chat | EE. UU. | DPA en los Commercial Terms |
| Google | Identidad, solo al entrar con Google | EE. UU. | Términos del servicio de identidad |
| Sentry (si está activo) | Errores de la aplicación, sin datos personales (`send_default_pii=False`) | EE. UU. | Por documentar |

Las copias de los DPA se guardan fuera del repositorio, en `legal/dpa/`, con la fecha en el nombre.

## Inteligencia artificial

**Análisis** (`ia.py`): envía ingreso y gasto promedio, cuota total, deuda restante, flujo libre, DTI, meses para saldar, cantidad de deudas, nivel de riesgo, tendencia y los factores de riesgo. No envía nombre, usuario, correo, descripciones de movimientos ni nombres de personas. Se puede verificar leyendo `_construir_prompt`. La respuesta no se guarda.

**Chat de ayuda** (`chat_ayuda.py`): envía el texto de la conversación, como máximo las últimas 12 intervenciones de hasta 600 caracteres. No envía ningún dato de la cuenta, aunque la persona esté dentro. Las instrucciones le prohíben pedir claves o datos del banco y le piden advertir si alguien los escribe. No se guarda nada en el servidor.

## Registro de seguridad

`EventoSeguridad` registra 19 tipos de evento, con fecha, IP, navegador y usuario o nombre intentado: accesos y fallos, bloqueos, cambios de 2FA, Face ID, contraseña, sesiones cerradas, descarga de datos, borrado de cuenta y accesos denegados al admin. Es de solo lectura en el admin. Sirve para detectar ataques y reconstruir un incidente. Al borrar una cuenta, sus eventos pierden el vínculo pero conservan el nombre de usuario hasta cumplir 12 meses: son la evidencia si el borrado lo hizo otra persona.

## Brechas

Ver [10 · Operación](10-OPERACION.md#incidentes-de-seguridad) y `docs/BRECHAS.md`.

## Pendientes de cumplimiento

Ninguno. C1, C2 y C3 se resolvieron en la entrega de arreglos (ver [13 · Deuda técnica](13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md)).

## Para un auditor

| Pregunta | Dónde mirar |
| --- | --- |
| ¿Qué datos se tratan y por qué? | `docs/REGISTRO-TRATAMIENTOS.md`, `/privacidad/` |
| ¿Qué acepta el usuario? | `/privacidad/`, `/terminos/`, `registration/registro.html`, `UserProfile.politica_*` |
| ¿Se pueden ejercer los derechos? | `views/cuenta.py` (`mis_datos`, `eliminar_cuenta`), `test_derechos.py` |
| ¿Se respetan los plazos? | `inactividad.py`, `auditoria.purgar`, `respaldar_postgres._rotar`, `test_conservacion.py` |
| ¿Qué sale hacia terceros? | `ia._construir_prompt`, `chat_ayuda`, `correo.py`, `test_terceros_fotos_cache.py`, la CSP en `middleware.py` |
| ¿Cómo se protege? | [06 · Seguridad](06-SEGURIDAD.md) |
| ¿Qué pasa ante una brecha? | `docs/BRECHAS.md` |
| ¿Hay contratos con los encargados? | Tabla de encargados y `legal/dpa/` |
