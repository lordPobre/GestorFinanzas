# Documentación de Fintora

Referencia completa del proyecto: qué hace, cómo está construido, cómo se opera, cómo se protege y qué falta. Se escribió leyendo el código de `lordPobre/GestorFinanzas`, rama `main`, el 27 de septiembre de 2026. Si el código y este texto no coinciden, manda el código, y hay que corregir el texto.

## Capítulos

| # | Capítulo | Qué contiene |
| --- | --- | --- |
| 01 | [Producto](01-PRODUCTO.md) | Qué es, para quién, funciones, diferenciales, estado y costos |
| 02 | [Arquitectura](02-ARQUITECTURA.md) | Stack, estructura del repositorio, capas, recorrido de una petición, el cálculo del mes, configuración por entorno y límites |
| 03 | [Modelo de datos](03-MODELO-DE-DATOS.md) | Los 20 modelos, sus campos, restricciones, cálculos y migraciones |
| 04 | [Rutas, vistas y API interna](04-RUTAS-Y-VISTAS.md) | Las más de 80 rutas, con método, permisos, topes y respuestas JSON |
| 05 | [Cartolas](05-CARTOLAS.md) | Cómo se lee un extracto bancario, lectores por banco, enriquecimiento, cobertura y cómo agregar uno |
| 06 | [Seguridad](06-SEGURIDAD.md) | Modelo de amenazas, acceso, aislamiento, CSP, topes, infraestructura y cómo verificar |
| 07 | [Privacidad y cumplimiento](07-PRIVACIDAD-Y-CUMPLIMIENTO.md) | Ley 21.719: bases de licitud, derechos, plazos, encargados, IA y pendientes |
| 08 | [Frontend](08-FRONTEND.md) | Plantillas, CSS y tokens, JavaScript, recorrido guiado y PWA |
| 09 | [Instalación y despliegue](09-INSTALACION-Y-DESPLIEGUE.md) | Entorno local, todas las variables, Railway, dependencias, migraciones y cómo volver atrás |
| 10 | [Operación](10-OPERACION.md) | Tareas programadas, respaldos y restauración, monitoreo, mantenimiento, incidentes y soporte |
| 11 | [Pruebas](11-PRUEBAS.md) | CI, las 211 pruebas por archivo, lo que falta cubrir y cómo escribir una |
| 12 | [Historial de decisiones](12-DECISIONES.md) | Cronología y las 19 decisiones que explican el código |
| 13 | [Deuda técnica y hoja de ruta](13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md) | Errores, hallazgos de seguridad y cumplimiento, pendientes de infraestructura y el orden sugerido |
| 14 | [Convenciones](14-CONVENCIONES.md) | Idioma, código, plantillas, URL, base, pruebas, git y la lista antes de fusionar |

## Anexos vivos

Documentos operativos que se actualizan con el uso y se leen en el momento:

| Anexo | Para qué |
| --- | --- |
| [REGISTRO-TRATAMIENTOS.md](REGISTRO-TRATAMIENTOS.md) | Inventario legal de tratamientos (Ley 21.719). Actualizado en esta revisión con el chat de ayuda, el formulario de contacto y la sesión de la cartola |
| [BRECHAS.md](BRECHAS.md) | Qué hacer ante un incidente, contactos e historial de incidentes |
| [RESPALDOS.md](RESPALDOS.md) | Configuración del respaldo, restauración y registro del simulacro mensual |
| [STAGING.md](STAGING.md) | Cómo montar y usar el entorno de pruebas |
| [CARTOLAS-COBERTURA.md](CARTOLAS-COBERTURA.md) | Estado de cada emisor de cartolas |
| [ESTILOS.md](ESTILOS.md) | Índice de secciones de `finapp.css` |
| [AUDITORIA-SEGURIDAD.md](AUDITORIA-SEGURIDAD.md), [AUDITORIA-CUMPLIMIENTO-2026.md](AUDITORIA-CUMPLIMIENTO-2026.md) | Auditorías de septiembre de 2026, conservadas como evidencia fechada. No se reescriben: lo que siga abierto está en el capítulo 13 |

## Por dónde empezar según quién eres

| Si eres… | Lee |
| --- | --- |
| **El dueño, volviendo después de meses** | 13 (qué está pendiente), 10 (qué corre solo y qué revisar), 09 (cómo desplegar), 12 (por qué es así) |
| **Un desarrollador que se suma** | 02, 03, 04, 14, 11 y luego 09 para levantarlo. Después, el capítulo del tema que te toque |
| **Quien compra o audita el proyecto** | 01, 02, 06, 07, 13 y 11. La calidad del código se ve en el 11 y la deuda en el 13 |
| **Un inversionista o socio** | 01 y, si quiere profundizar, 07 (privacidad como diferencial) y 13 (riesgos conocidos) |
| **Un auditor de datos personales** | 07, REGISTRO-TRATAMIENTOS, BRECHAS, 06, y la tabla “Para un auditor” al final del 07 |

## Qué pasó con los documentos anteriores

Se revisaron uno por uno los 16 archivos que había en `docs/` y la copia de `DESPLIEGUE-RAILWAY.md` en la raíz:

| Documento | Decisión | Dónde quedó |
| --- | --- | --- |
| `ARQUITECTURA.md` | Absorbido y borrado. Describía `views.py` y `tests.py` antes de los lotes 1–12 | 02, 12 (D-05, D-06) y 13 (D8) |
| `DECISION-CIFRADO.md` | Absorbido y borrado | 12 (D-08), completo |
| `DEUDA-TECNICA.md` | Absorbido y borrado | 13 (D8 a D11) |
| `REVISION-CODIGO-2026-09.md` | Absorbido y borrado. Todo quedó hecho | 12 (cronología) |
| `ACTUALIZAR-DJANGO-5.2.md` | Absorbido y borrado. Ya está en Django 5.2.17 | 12 |
| `MIGRACION-POSTGRES.md` | Absorbido y borrado. La migración ya se hizo | 12 (procedimiento histórico) |
| `DESPLIEGUE-RAILWAY.md` (en `docs/` y en la raíz) | Absorbido y borrado. El de la raíz era un duplicado | 09 y 10; la salida de PythonAnywhere, en 12 |
| `GUIA-PENDIENTES-MANUALES.md` | Absorbido y borrado. Los 9 pasos estaban hechos | 12 (cronología), 10 (recordatorio de DMARC) |
| `REGISTRO-TRATAMIENTOS.md` | **Se mantiene, actualizado** | Anexo |
| `BRECHAS.md` | Se mantiene | Anexo |
| `RESPALDOS.md` | Se mantiene. Hay que corregirle una frase (E8) | Anexo |
| `STAGING.md` | Se mantiene | Anexo |
| `CARTOLAS-COBERTURA.md` | Se mantiene | Anexo |
| `ESTILOS.md` | Se mantiene | Anexo |
| `AUDITORIA-SEGURIDAD.md` | Se mantiene como evidencia fechada | Anexo |
| `AUDITORIA-CUMPLIMIENTO-2026.md` | Se mantiene como evidencia fechada | Anexo |

## Versión en PDF

`Documentacion Fintora.pdf` reúne los 14 capítulos con portada e índice. Se genera desde estos mismos archivos, así que ante cualquier diferencia manda el Markdown.
