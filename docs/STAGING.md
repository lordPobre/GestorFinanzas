# Entorno de staging

Una copia de la app con su propia base de datos, para probar migraciones y
cambios sin tocar los datos reales. Hasta ahora todo se probaba en
producción: si una migración salía mal, salía mal sobre los movimientos de
verdad, y el único camino de vuelta era un respaldo.

## Lo que lo hace seguro

El entorno se declara con una variable, y la app cambia tres cosas:

| Variable | Valor en staging |
| --- | --- |
| `ENTORNO` | `staging` |
| `DATABASE_URL` | la del servicio Postgres de staging, **nunca** la de producción |
| `CORREO_EN_STAGING` | vacío (bloquea el envío) o `1` para probar correos |

Con `ENTORNO=staging`:

1. **No sale ningún correo.** `finanzas/correo.py` escribe el cuerpo completo
   en el log y devuelve éxito, así que el flujo sigue su curso. Es lo que
   impide que una prueba del aviso de inactividad —sobre una base copiada de
   producción— mande «vamos a borrar tu cuenta» a usuarios reales. Para probar
   un correo de verdad: `CORREO_EN_STAGING=1` y una base con direcciones
   tuyas.
2. **Se ve que es staging.** Una franja roja en la parte superior de todas las
   pantallas. Sin ella, una copia de la base se confunde con el original.
3. **No se indexa.** Cabecera `X-Robots-Tag: noindex, nofollow` en todas las
   respuestas, para que el dominio de pruebas no acabe en Google compitiendo
   con el real.

`ENTORNO` vale `produccion` si no se define. Un entorno de pruebas mal
etiquetado se comporta como el real, y ese error es peor que el inverso.

## Montarlo en Railway

1. **Servicio nuevo** en el mismo proyecto, apuntando a la misma rama o a una
   rama `staging`.
2. **Postgres propio** en ese servicio. Railway da la `DATABASE_URL`; no
   copiar la de producción ni «solo para esta prueba».
3. **Variables**: las mismas de producción salvo estas.

   ```
   ENTORNO=staging
   SECRET_KEY=<una clave distinta>
   DEBUG=False
   ALLOWED_HOSTS=<dominio-staging>
   CSRF_TRUSTED_ORIGINS=https://<dominio-staging>
   SITE_URL=https://<dominio-staging>
   ```

   `SECRET_KEY` distinta a propósito: comparte la firma de las sesiones y de
   los tokens de correo, así que con la misma clave una sesión de staging
   valdría en producción.

4. **Bucket R2 aparte** (`R2_BUCKET` distinto) o sin R2, que deja las fotos en
   el disco del contenedor. Compartir bucket significa que borrar un avatar en
   staging lo borra en producción.

5. **`ANTHROPIC_API_KEY`**: si no se pone, el análisis con IA se desactiva
   solo y el resto funciona igual. Es lo recomendable para no gastar cuota en
   pruebas.

## Llevar datos a staging

Con datos reales copiados, staging pasa a contener datos personales y le
aplican las mismas obligaciones que a producción: no es «un entorno de
juguete». Dos opciones:

- **Base vacía** y crear dos o tres cuentas de prueba. Es lo preferible.
- **Copia de producción**, solo si hace falta probar una migración contra el
  volumen real. Entonces: `ENTORNO=staging` antes de cualquier tarea,
  `CORREO_EN_STAGING` vacío, y borrar la copia al terminar.

```bash
pg_dump "$URL_PRODUCCION" > copia.sql
psql "$URL_STAGING" < copia.sql
```

## Probar una migración antes de producción

```bash
# en staging
python manage.py migrate --plan       # qué va a hacer, sin hacerlo
python manage.py migrate
python manage.py test finanzas        # las pruebas contra la base migrada
```

Si algo falla, falla acá. En producción la migración entra solo después.

## Las tareas programadas

En staging quedan **apagadas** salvo la que se esté probando. Concretamente
`limpiar_inactivas`, que borra cuentas: con la base copiada y las fechas de
producción, la primera corrida encontraría candidatos reales. Para probarla:

```bash
python manage.py limpiar_inactivas --seco
```

`--seco` no envía ni borra: solo dice qué haría.
