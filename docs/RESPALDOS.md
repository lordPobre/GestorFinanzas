# Respaldos y restauración

Procedimiento para la base Postgres de Rekon en Railway. Un respaldo que nunca
se restauró no se sabe si funciona: la última sección es un simulacro que se
corre una vez al mes.

Hay dos líneas de respaldo:

1. **La propia**: `manage.py respaldar_postgres`, todos los días, a un bucket
   privado de Cloudflare R2. Sobrevive a un problema con la cuenta de Railway.
2. **La del proveedor**: los backups del servicio Postgres en Railway. Sirven
   para volver atrás rápido, pero viven en el mismo proveedor que la base.

---

## Configurar una vez

1. En Cloudflare, crea un bucket **privado** llamado por ejemplo
   `rekon-respaldos`. No le actives acceso público ni dominio. El bucket de las
   fotos es público y el comando se niega a usarlo.
2. Crea un token de API de R2 con permiso de lectura y escritura **solo sobre
   ese bucket**.
3. En Railway, crea el servicio `respaldo` con el mismo repositorio (ver
   `DESPLIEGUE-RAILWAY.md`, sección 7) y estas variables:

| Variable | Valor |
| --- | --- |
| `DATABASE_URL` | La misma del servicio web |
| `R2_ENDPOINT_URL` | La misma de las fotos |
| `R2_BUCKET_RESPALDOS` | `rekon-respaldos` |
| `R2_RESPALDOS_ACCESS_KEY_ID` | La del token del paso 2 |
| `R2_RESPALDOS_SECRET_ACCESS_KEY` | La del token del paso 2 |
| `SECRET_KEY` | La misma del servicio web |
| `PG_MAJOR` | Opcional. Versión de tu Postgres; por defecto `18` |

Railway Config File: `/railway/respaldo.json`. Ya trae el comando y el horario
(`0 7 * * *`, 3 o 4 de la mañana en Chile).

Este servicio no se construye con Nixpacks sino con
`railway/Dockerfile.respaldo`: Python 3.13 más el cliente oficial de
PostgreSQL desde apt.postgresql.org. Así `pg_dump` coincide con la versión
del servidor, que hoy es la 18. Nixpacks no tiene PostgreSQL 18 y, si se le
pide otra versión con `NIXPACKS_PKGS`, choca con la 16 que instala solo.

Si algún día se actualiza el Postgres, agrega la variable `PG_MAJOR` con la
versión nueva (por ejemplo `PG_MAJOR=19`) y redespliega el servicio. Sin la
variable se usa la 18.

El comando compara las dos versiones antes de copiar y, si no calzan, falla
con el valor de `PG_MAJOR` que corresponde.

4. Antes de dejarlo programado, córrelo a mano con `--seco`: hace y verifica la
   copia pero no la sube.

## Qué hace cada corrida

1. `pg_dump` en formato comprimido de Postgres, sin dueños ni permisos, para
   que se pueda restaurar en cualquier base.
2. `pg_restore --list` sobre el archivo: si no se puede leer, o le faltan
   `auth_user`, `finanzas_transaccion` o `finanzas_userprofile`, falla y no
   sube nada.
3. Calcula el SHA-256 y lo guarda como metadato del objeto.
4. Sube a `postgres/rekon-AAAAMMDD-HHMMSS.dump` y borra las copias que pasen
   de 30.

Opciones:

```bash
python manage.py respaldar_postgres --seco
python manage.py respaldar_postgres --conservar 60
python manage.py respaldar_postgres --destino /tmp/respaldos
```

Si una corrida falla, el servicio termina con error y Railway lo muestra en el
panel. Con Sentry configurado, conviene revisar ahí también.

## Restaurar

Nunca sobre la base de producción sin haber probado antes en una base aparte.

1. Descarga la copia desde el panel de R2, o con cualquier cliente S3.
2. Crea una base vacía (un Postgres nuevo en Railway sirve) y toma su URL.
3. Restaura:

```bash
pg_restore --no-owner --no-privileges --dbname "$URL_DESTINO" rekon-AAAAMMDD-HHMMSS.dump
```

4. Apunta un entorno de staging a esa base y revisa que entras y que tus
   movimientos están.
5. Solo si todo está bien, cambia `DATABASE_URL` del servicio web a la base
   restaurada, o restaura sobre la de producción con `--clean`.

## Simulacro mensual

Una vez al mes, el primer lunes:

- [ ] Descargar la copia más reciente del bucket.
- [ ] Comprobar su SHA-256 contra el metadato del objeto.
- [ ] Restaurar en una base vacía.
- [ ] Contar usuarios y movimientos y compararlos con producción.
- [ ] Borrar la base de prueba y el archivo descargado.
- [ ] Anotar la fecha y el resultado abajo.

| Fecha | Copia | Resultado | Quién |
| --- | --- | --- | --- |
| | | | |

## Desarrollo local con SQLite

`python manage.py respaldar` sigue sirviendo para la base SQLite local. Con
Postgres se niega a correr y remite a este documento.
