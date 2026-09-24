# Qué hacer ante un incidente de seguridad

Procedimiento para una brecha de datos personales: acceso no autorizado,
filtración, pérdida o alteración. La Ley 21.719 obliga a notificar a la
Agencia de Protección de Datos Personales sin dilación indebida, y a los
titulares cuando el incidente pueda afectarlos de forma significativa. El
estándar de referencia son 72 horas desde que se toma conocimiento.

Esto no es un documento para archivar. Es lo que se lee el día que pasa.

---

## Contactos

| Rol | Quién | Cómo |
| --- | --- | --- |
| Responsable del tratamiento | Carlos López Figueroa | soporte@perseustechnology.dev |
| Quien decide notificar | Carlos López Figueroa | *+56 9 8341 3957* |
| Agencia de Protección de Datos Personales | — | Canal oficial, cuando esté publicado |
| Soporte de Railway | — | Panel del proyecto |
| Soporte de Cloudflare | — | Panel de la cuenta |
| Soporte de Resend | — | Panel de la cuenta |

Con el servicio abierto al público, la notificación a los titulares se hace
por correo a las direcciones de `auth_user.email`.

---

## Paso 1 — Contener, antes de investigar

Primero cortar, después entender. Una hora de análisis con el atacante dentro
cuesta más que una hora de servicio caído.

Según el caso:

- **Credencial filtrada** (`SECRET_KEY`, clave de R2, API key): rotarla en el
  panel del hosting y redesplegar. Rotar `SECRET_KEY` invalida todas las
  sesiones, que es justo lo que se quiere.
- **Cuenta de usuario comprometida**: forzar el cierre de sesión cambiando su
  contraseña y revisar sus movimientos recientes.
- **Acceso al panel de administración**: poner `ADMIN_URL` vacío y
  redesplegar. Con eso la ruta deja de existir.
- **La base**: revisar las conexiones activas en el panel de Railway y rotar
  la contraseña de Postgres.

## Paso 2 — Registrar la hora

Anotar por escrito, con hora exacta:

- Cuándo se detectó y cómo.
- Qué se vio (mensaje de error, línea de log, aviso de un usuario).
- Qué se hizo para contener, y a qué hora.

El plazo de notificación corre desde el momento en que se toma conocimiento.
Si ese momento no está anotado, no se puede demostrar que se cumplió.

## Paso 3 — Determinar el alcance

Responder estas cinco preguntas. "No se sabe" es una respuesta válida y hay
que escribirla como tal.

1. ¿Qué datos quedaron expuestos? (cuentas, movimientos, fotos, todo)
2. ¿De cuántas personas?
3. ¿Se copiaron, o solo quedaron accesibles?
4. ¿Hay datos de terceros involucrados? Las personas de "Me deben" no son
   usuarias y no saben que están en el sistema.
5. ¿Sigue abierta la vía de acceso?

Fuentes para responder: panel de logs de Railway, `seguridad.log` si hay
volumen montado, Sentry, registros de acceso de R2.

## Paso 4 — Decidir si se notifica

Se notifica a la Agencia cuando hay datos personales comprometidos. La duda
se resuelve notificando: el costo de informar un incidente menor es bajo, y el
de no informar uno real es una infracción.

Se notifica además a los titulares afectados cuando la exposición puede
perjudicarlos. En esta aplicación, cualquier filtración de movimientos o de
las personas de "Me deben" entra en esa categoría: es el mapa del dinero y de
las relaciones de alguien.

## Paso 5 — Notificar

A la Agencia, por el canal oficial, incluyendo:

- Qué pasó y cuándo se detectó.
- Qué categorías de datos y cuántos titulares aproximadamente.
- Consecuencias probables.
- Qué se hizo para contener y qué se hará para que no se repita.
- Datos de contacto del responsable.

A los titulares, por correo, en lenguaje claro: qué pasó, qué dato suyo
estuvo expuesto, qué se hizo, y qué conviene que hagan ellos (cambiar la
contraseña, revisar sus movimientos).

## Paso 6 — Cerrar

- Arreglar la causa, no el síntoma.
- Escribir una prueba que falle si el agujero vuelve.
- Anotar el incidente en el historial de abajo.
- Revisar si el mismo agujero existe en otra parte.

---

## Historial de incidentes

| Fecha | Qué pasó | Datos afectados | Notificado | Cerrado |
| --- | --- | --- | --- | --- |
| 2026-09-15 | Claves de acceso de Cloudflare R2 publicadas en el historial del repositorio, dentro de una migración | Ninguno de forma comprobada: el bucket solo contiene fotos de perfil | No aplica: repositorio privado, sin evidencia de acceso de terceros | **Cerrado** (septiembre de 2026): token rotado en Cloudflare y archivo corregido. El token viejo sigue en el historial de git y ya no sirve para nada |

---

## Antes de necesitarlo

Estas tres cosas hacen la diferencia entre detectar una brecha y que la
cuente un usuario:

1. **Sentry configurado** (`SENTRY_DSN`), con alerta al correo.
2. **Volumen montado con `LOG_DIR`**, para que los accesos fallidos tengan
   historial y no se pierdan en cada despliegue.
3. **Un monitor externo** apuntando a `/salud/`.
