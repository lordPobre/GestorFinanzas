# Migrar GestorFinanzas de SQLite a Postgres

El código ya está listo (`settings.py` usa `dj_database_url` y cae a SQLite solo si no hay `DATABASE_URL`). Esto es 100% trabajo de infraestructura y datos, no de código.

## 1. Dónde vive el Postgres

Ya está decidido: **el Postgres del proyecto de Railway**, creado junto al
servicio web (ver `DESPLIEGUE-RAILWAY.md`). Railway te da dos URL para la
misma base y la diferencia importa:

- La **privada** (`postgres.railway.internal`) es la que usa la app. Se
  referencia con `DATABASE_URL=${{Postgres.DATABASE_URL}}` y no cobra egreso.
  Solo existe dentro de Railway.
- La **pública** (pestaña Connect de la base) es la que usas tú desde tu
  máquina para el `loaddata` de este documento y para cualquier cliente SQL.

Las dos son un `postgres://usuario:clave@host:5432/nombre_db`, que es lo que
`dj_database_url` espera.

## 2. Preparar el entorno, sin tocar producción todavía

```bash
pip install psycopg2-binary   # driver de Postgres, revisa que esté en requirements.txt
```

Prueba primero en local: pon `DATABASE_URL` apuntando al Postgres nuevo en tu `.env` local y corre:

```bash
python manage.py migrate
python manage.py test finanzas   # los tests que ya armamos corren igual contra Postgres
```

Si los tests pasan contra Postgres, el ORM no tiene nada específico de SQLite que se rompa.

## 3. Migrar los datos reales (no solo el esquema)

La forma más segura con SQLite → Postgres en Django es `dumpdata`/`loaddata`, no una copia directa de archivos:

```bash
# 1. Con DATABASE_URL SIN configurar (o apuntando a SQLite), saca todo:
python manage.py dumpdata --natural-foreign --natural-primary \
    -e contenttypes -e auth.Permission -e sessions \
    --indent 2 > datos_respaldo.json

# 2. Cambia DATABASE_URL a Postgres, crea las tablas:
python manage.py migrate

# 3. Carga los datos en la base nueva:
python manage.py loaddata datos_respaldo.json
```

`-e contenttypes -e auth.Permission -e sessions` evita conflictos de IDs con lo que Django genera solo al migrar — sin eso, `loaddata` puede fallar por duplicados.

Antes de esto tienes que bajar la base de PythonAnywhere: en su panel,
**Files** → descarga `db.sqlite3` y déjala en tu carpeta local del proyecto.

Y una advertencia sobre el archivo que produce el paso 1:
**`datos_respaldo.json` es tu base entera en texto plano** — descripciones,
correos, montos, todo. Está en `.gitignore`, pero bórralo del disco en cuanto
termines de verificar, y no lo mandes por correo ni lo dejes en Descargas.

## 4. Verificar antes de cortar

- Cuenta de filas por tabla en ambas bases (`SELECT COUNT(*)` por modelo) — deben coincidir.
- Entra con un usuario real, revisa que el dashboard muestre las mismas cifras que antes de migrar.
- Prueba pagar una cuota y crear una transacción — confirma que escribe bien en Postgres.

## 5. Cortar a producción

1. Pon `DATABASE_URL` en las variables de entorno de producción (no en el repo — ya es la convención que sigue tu `settings.py`).
2. Congela escrituras un momento: pon la app en modo mantenimiento o avisa, corre el `dumpdata` FINAL de SQLite (para no perder lo que se escribió mientras probabas), y cárgalo en Postgres.
3. Reinicia la app. `migrate` ya corrió en el paso 3 — no hace falta de nuevo salvo que haya migraciones nuevas.
4. Verifica login, dashboard, y un pago real antes de avisar que ya está.

## 6. Rollback si algo sale mal

Mientras no borres `db.sqlite3` ni las variables viejas, revertir es solo quitar `DATABASE_URL` del entorno — `settings.py` vuelve a caer a SQLite automáticamente. Guarda `db.sqlite3` sin tocar hasta confirmar que Postgres funciona bien un par de días.

## Notas sobre tu código específico

- `CACHES` usa `locmem` — no depende de la base, no afecta la migración. En
  Railway sigue funcionando bien porque es un contenedor único: el limitador
  de intentos de `seguridad.py` cuenta en memoria y no se reparte entre
  instancias, que es justo lo que se habría roto en un hosting serverless.
- No hay campos cifrados en la base (ver `docs/DECISION-CIFRADO.md`), así que
  no hay claves que llevar ni datos que puedan quedar ilegibles al cambiar de
  base.
- `manage.py respaldar` deja de servir en cuanto cortes: es específico de
  SQLite y lanza `CommandError` con Postgres, por diseño. Los respaldos pasan
  a ser los del servicio Postgres de Railway más un `pg_dump` tuyo de vez en
  cuando. `RESPALDOS.md` hay que reescribirlo después del corte.
- El campo `Deuda.periodo` y otros `IntegerField` con `año*100+mes` funcionan igual en Postgres, sin cambios.
- Las `UniqueConstraint` (`pago_unico_por_mes`, `categoria_unica_por_usuario`, etc.) las crea `migrate` igual en Postgres — no hay SQL específico de SQLite en tus modelos.
