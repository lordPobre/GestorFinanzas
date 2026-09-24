# Cifrado de descripciones: decisión y por qué

**Decisión: no se aplica. `finanzas/cifrado.py` se eliminó.**

Tomada el 19 de septiembre de 2026, como parte del lote 3 de cumplimiento.

## Qué había

`cifrado.py` definía `TextoCifrado`, un `TextField` que se guardaba cifrado
con Fernet y se leía en claro. Estaba bien escrito y razonado, y llevaba meses
sin que ningún modelo lo usara: tres auditorías seguidas lo anotaron como
código muerto. La pregunta pendiente era aplicarlo a los campos de texto libre
—`Transaccion.descripcion`, `Persona.contacto`, `AbonoPrestamo.nota`,
`Prestamo.descripcion`— o borrarlo.

## Por qué no se aplica

**1. La app consulta esos campos en la base, no solo los muestra.** El cobro
mensual de cada suscripción se reconoce por su descripción:

```python
Transaccion.objects.filter(descripcion__startswith=f'Suscripción: {nombre}')
```

Con el campo cifrado, cada fila guarda un texto distinto —Fernet incluye un
vector aleatorio, así que el mismo texto cifra distinto cada vez— y ese filtro
no encuentra nada. No falla con un error: devuelve cero filas. El histórico de
cada suscripción pasaría a marcar $0 y nadie se enteraría hasta revisar a mano.
Lo mismo vale para `clase_tono` y `marca_suscripcion`, que leen el prefijo
`Suscripción: ` para elegir color e icono.

**2. La clave tendría que vivir donde vive la base.** `FIELD_ENCRYPTION_KEY`
sería una variable de entorno del mismo servicio que corre la app. Quien pueda
leer la base en un incidente real —acceso al panel del hosting, credenciales
filtradas— normalmente también puede leer esa variable. La protección es menor
de lo que aparenta.

**3. Añadía un modo de fallo irreversible.** Perder la clave hace ilegibles los
textos para siempre. Cambiarla por equivocación —o restaurar un respaldo de la
base junto a un entorno con otra clave— deja cada descripción en
`[no se pudo descifrar]`. Es un riesgo nuevo de pérdida de datos a cambio de
una protección parcial.

**4. Nadie prometió lo contrario.** La política de privacidad dice que el
tráfico va cifrado y que la base está en una red privada. No promete cifrado a
nivel de campo, así que borrarlo no incumple nada de lo publicado.

## Qué protege los datos en reposo, entonces

Cifrado a nivel de motor, que es donde corresponde: protege el archivo
completo —montos incluidos, que es lo que un campo cifrado no podía cubrir sin
romper las sumas— y la app conserva `Sum()`, los filtros y los índices.

- **Postgres gestionado** (Railway, Neon, Supabase): viene activado. Confirmar
  en el panel del proveedor.
- **SQLite**: cifrado de disco en el servidor, o SQLCipher.

## Qué se borró

- `finanzas/cifrado.py`
- `FIELD_ENCRYPTION_KEY` en `.env.example`, `README.md` y el CI
- `cryptography` en `requirements.txt` (solo estaba por este módulo)

## Si algún día se reabre

Hace falta, antes de cifrar nada:

1. Dejar de identificar las suscripciones por su descripción. Un
   `ForeignKey` de `Transaccion` a `Suscripcion` es lo correcto de todos
   modos, y elimina la dependencia del texto.
2. Una migración de datos que cifre lo existente, y un respaldo de la clave
   guardado aparte de los respaldos de la base.
3. Aceptar que la búsqueda en servidor sobre esos campos deja de existir.

Nada de eso está hecho hoy, y hasta que lo esté, cifrar solo agrega riesgo.
