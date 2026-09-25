# Registro de actividades de tratamiento

Inventario de qué dato personal trata la aplicación, con qué finalidad, dónde
vive y cuánto se conserva. Es el documento que pide la Ley 21.719 cuando se
fiscaliza: no basta con tener los controles, hay que poder mostrar qué se
trata y por qué.

Última revisión: 23 de septiembre de 2026.

| | |
| --- | --- |
| Responsable del tratamiento | Carlos López Figueroa, persona natural, Valparaíso, Chile |
| Canal para el ejercicio de derechos | soporte@perseustechnology.dev |
| Alcance | Servicio abierto al público, con cuentas de usuarios reales |
| Política vigente | Versión 1.2, desde el 1 de octubre de 2026 (`finanzas/legal.py`) |

---

## 1. Cuenta de usuario

| | |
| --- | --- |
| Datos | Nombre de usuario, correo, contraseña (hash Argon2), nombre y apellido si se ingresan, ciudad, fecha de alta, fecha del último acceso |
| Finalidad | Identificar a la persona y darle acceso a sus propios datos |
| Base de licitud | Ejecución del servicio solicitado por el titular |
| Dónde | Postgres en Railway (`auth_user`, `finanzas_userprofile`) |
| Conservación | Mientras la cuenta exista. Se borra por completo al eliminarla |
| Quién accede | El titular. El administrador, solo si `ADMIN_URL` está habilitado, y entrando por el mismo acceso con bloqueo y verificación en dos pasos |

## 2. Movimientos financieros

| | |
| --- | --- |
| Datos | Fecha, monto, tipo, categoría y descripción libre de cada ingreso y gasto |
| Finalidad | La función central de la aplicación |
| Base de licitud | Ejecución del servicio |
| Dónde | Postgres (`finanzas_transaccion`) |
| Conservación | Mientras la cuenta exista |
| Observación | La descripción es texto libre y puede contener datos de terceros o información delicada. Hoy se guarda en claro; ver la decisión pendiente sobre `finanzas/cifrado.py` |

## 3. Compras en cuotas, suscripciones, metas y presupuesto

| | |
| --- | --- |
| Datos | Acreedor, montos, calendario de cobros, nombre de la meta, límite mensual |
| Finalidad | Proyectar los compromisos del mes |
| Base de licitud | Ejecución del servicio |
| Dónde | Postgres (`finanzas_deuda`, `finanzas_pagocuota`, `finanzas_suscripcion`, `finanzas_pagoservicio`, `finanzas_metaahorro`, `finanzas_aportemeta`, `finanzas_presupuesto`, `finanzas_gastopendiente`) |
| Conservación | Mientras la cuenta exista |

## 4. Datos de terceros: personas que deben dinero

| | |
| --- | --- |
| Datos | Nombre y un campo de contacto libre (teléfono, correo o nota), montos prestados y abonos |
| Finalidad | Llevar la cuenta de los préstamos personales del titular |
| Base de licitud | Interés legítimo del titular en administrar sus créditos personales |
| Dónde | Postgres (`finanzas_persona`, `finanzas_prestamo`, `finanzas_abonoprestamo`) |
| Conservación | Mientras la cuenta exista |
| Observación | **Son datos de personas que no son usuarias de la aplicación y no han dado consentimiento.** El titular los ingresa por su cuenta. La política de privacidad debe advertir que quien los ingresa es responsable de hacerlo con fundamento |

## 5. Foto de perfil

| | |
| --- | --- |
| Datos | Imagen del rostro, normalmente |
| Finalidad | Identificación visual dentro de la propia cuenta |
| Base de licitud | Consentimiento: es opcional y la sube el titular |
| Dónde | Cloudflare R2, bucket privado, con nombre de archivo aleatorio |
| Conservación | Hasta que se reemplace o se elimine la cuenta. `limpiar_avatares_huerfanos` retira las que quedan sueltas |
| Observación | Se muestra con enlaces firmados que caducan a las 6 horas (`finanzas/almacenamiento.py`). Resuelve el punto A8 de la auditoría |

## 6. Cartolas bancarias importadas

| | |
| --- | --- |
| Datos | Movimientos del extracto: fecha, comercio, monto, cuotas |
| Finalidad | Cargar movimientos sin escribirlos a mano |
| Base de licitud | Ejecución del servicio, a pedido expreso del titular |
| Dónde | El archivo se procesa en memoria; **no se guarda**. Los movimientos que el titular confirma se guardan como transacciones normales |
| Conservación | El archivo, nada. Los movimientos, mientras la cuenta exista |

## 7. Verificación en dos pasos

| | |
| --- | --- |
| Datos | Secreto TOTP, hash de los códigos de respaldo, marca de uso |
| Finalidad | Proteger el acceso |
| Base de licitud | Seguridad del tratamiento |
| Dónde | Postgres (`finanzas_segundofactor`, `finanzas_codigorespaldo`) |
| Conservación | Mientras esté activa |
| Observación | El secreto y los hashes no se incluyen en la descarga de datos del titular: son credenciales, no información personal entregable |

## 8. Registros de seguridad

| | |
| --- | --- |
| Datos | Tipo de evento (acceso, acceso fallido, bloqueo, cambios de verificación, Face ID o huella, contraseña, descarga de datos, borrado de cuenta), fecha y hora, usuario o nombre intentado, dirección IP y navegador |
| Finalidad | Detectar ataques y poder reconstruir un incidente |
| Base de licitud | Interés legítimo en la seguridad del servicio |
| Dónde | Postgres (`finanzas_eventoseguridad`), además de la salida estándar del contenedor |
| Conservación | 12 meses. `limpiar_inactivas` borra los más antiguos cada día |
| Observación | Al eliminar una cuenta, sus eventos pierden el vínculo con ella pero conservan el nombre de usuario hasta cumplir los 12 meses: son la evidencia si el borrado lo hizo un tercero. El titular los recibe en su descarga de datos |

## 9. Contadores de bloqueo

| | |
| --- | --- |
| Datos | Dirección IP y usuario, asociados a contadores de intentos |
| Finalidad | Bloqueo temporal: 5 fallos del mismo usuario desde la misma IP (15 minutos), 20 fallos contra una misma cuenta desde cualquier IP (1 hora) o 50 fallos desde una misma IP contra cualquier cuenta (1 hora) |
| Dónde | Tabla `cache_finapp` en Postgres |
| Conservación | 15 minutos o 1 hora. Expira solo |

## 10. Correo de aviso mensual

| | |
| --- | --- |
| Datos | Correo del titular y el resumen de cobros del mes |
| Finalidad | Recordar los cobros por vencer |
| Base de licitud | Consentimiento: se activa desde el perfil y se puede desactivar |
| Dónde | Se entrega a Resend por API HTTPS |
| Conservación | La que aplique el proveedor a su registro de envíos |

## 11. Análisis con inteligencia artificial

| | |
| --- | --- |
| Datos enviados | **Solo agregados numéricos**: ingreso y gasto mensual promedio, cuota total, deuda restante, flujo libre, ratio deuda/ingreso, meses restantes, cantidad de deudas, nivel de riesgo y tendencia |
| Datos que NO se envían | Nombre, correo, nombre de usuario, descripciones de movimientos, nombres de personas, cualquier identificador |
| Finalidad | Traducir el diagnóstico numérico a lenguaje natural |
| Base de licitud | Consentimiento, revocable en Perfil → Análisis con IA (`UserProfile.analisis_ia`). Apagado, `views.analisis_ia` no llama a la API |
| Dónde | API de Anthropic, Estados Unidos |
| Conservación | La que aplique el proveedor. La aplicación no guarda la respuesta |
| Verificable en | `finanzas/ia.py`, función `_construir_prompt` |

## 12. Encuesta de satisfacción

| | |
| --- | --- |
| Datos | Antigüedad y frecuencia de uso, notas de 1 a 5 y de 0 a 10, textos libres sobre la app |
| Finalidad | Mejorar la aplicación |
| Base de licitud | Consentimiento: es voluntaria y se puede posponer u omitir |
| Dónde | Postgres (`finanzas_respuestaencuesta`) |
| Conservación | Mientras la cuenta exista |
| Quién accede | Solo cuentas de personal (`is_staff`), en la página de resultados |

## 13. Acceso con Face ID o huella

| | |
| --- | --- |
| Datos | Identificador de la credencial, clave pública, nombre del dispositivo, fecha de alta y de último uso |
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
| Dónde | Bucket privado de Cloudflare R2, cifrado en reposo por el proveedor |
| Conservación | 30 copias diarias. Una cuenta eliminada desaparece de los respaldos cuando rota la última copia que la contenía |

---

## Encargados del tratamiento y transferencias internacionales

Todos los proveedores están fuera de Chile, lo que constituye transferencia
internacional y debe declararse en la política de privacidad.

| Proveedor | Qué trata | País | Acuerdo de tratamiento |
| --- | --- | --- | --- |
| Railway | Cómputo y base de datos completa | Estados Unidos | DPA firmado el 2026-09-24 (firma aparte, railway.com/legal/dpa) |
| Cloudflare R2 | Fotos de perfil y respaldos de la base | Red global | Customer DPA v6.4, incorporado al Self-Serve Subscription Agreement, revisado y descargado el 2026-09-23 |
| Resend | Correo del titular y contenido del aviso | Estados Unidos | DPA prefirmado por Resend, vigente desde el alta de la cuenta; copia firmada descargada el 2026-09-23 |
| Anthropic | Agregados numéricos del análisis | Estados Unidos | DPA incorporado a los Commercial Terms, revisados y descargados el 2026-09-23 |
| Google | Identidad al entrar con cuenta de Google | Estados Unidos | Términos del servicio de identidad |

## Plazos de conservación

| Dato | Plazo | Estado |
| --- | --- | --- |
| Todo lo de la cuenta | Mientras la cuenta exista | Aplicado |
| Cuenta sin ningún acceso | Aviso a los 12 meses, borrado 30 días después | Aplicado: tarea diaria `limpiar_inactivas` |
| Registros de seguridad | 12 meses | Aplicado: `finanzas_eventoseguridad`, purgado por `limpiar_inactivas` |
| Respaldos de la base | 30 días | Aplicado: rotación de `respaldar_postgres` |
| Contadores de bloqueo | 15 minutos a 1 hora | Aplicado: expiran solos |
| Archivo de cartola | No se guarda | Aplicado |

`UserProfile.ultima_actividad` es el campo sobre el que se mide la
inactividad; lo escribe `ActividadMiddleware` una vez al día. `last_login`
no sirve: una sesión recordada lo deja congelado.

## Derechos del titular: estado

| Derecho | Cómo se ejerce hoy |
| --- | --- |
| Acceso y portabilidad | Perfil → Descargar todos mis datos (JSON), y exportación a Excel y CSV |
| Rectificación | Cada dato se edita desde su propia pantalla |
| Supresión | Perfil → Seguridad → Eliminar mi cuenta. Borra todo de inmediato |
| Oposición al análisis con IA | Perfil → Análisis con IA, apagado |
| Oposición al correo mensual | Perfil → Aviso mensual, apagado |
| Canal formal de solicitudes | soporte@perseustechnology.dev, respuesta en 30 días corridos |
| Evidencia del consentimiento | `UserProfile.politica_version` y `politica_aceptada`, registrados en el alta |
