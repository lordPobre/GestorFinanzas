# Actualizar a Django 5.2 LTS

Django 5.1 ya no recibe parches de seguridad. La 5.2 es LTS, con soporte hasta
abril de 2028.

## Qué cambió

| Archivo | Cambio |
| --- | --- |
| `requirements.in` y `requirements.txt` | `Django>=5.2,<5.3`, `gunicorn>=23.0,<24.0`, `Pillow>=11.0,<13.0` |
| `core/settings.py` | `STATICFILES_STORAGE` pasa a `STORAGES` |

`STATICFILES_STORAGE` dejó de existir en Django 5.1. Producción la ignoraba sin
avisar, así que los estáticos se servían sin comprimir y sin el hash en el
nombre. Con `STORAGES` WhiteNoise vuelve a hacerlo: los archivos pesan menos y
el navegador los guarda en caché sin riesgo de ver una versión vieja.

## Probar en local (15 min)

Usa en local la misma versión que en producción. Hoy tienes la 6.0 instalada.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m django --version
```

Tiene que decir `5.2.x`. Luego:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

`makemigrations --check` debe decir *No changes detected*. Si detecta cambios,
no los generes todavía: avísame qué muestra.

Por último, prueba los estáticos como en producción:

```bash
set DEBUG=False
set SECRET_KEY=una-clave-larga-cualquiera-solo-para-esta-prueba-local
python manage.py collectstatic --noinput
```

Tiene que terminar sin errores. Si falla con *Missing staticfiles manifest
entry* o *could not be found*, alguna plantilla o CSS apunta a un archivo que
no existe; el mensaje dice cuál.

## Subir

1. Rama nueva: `git checkout -b django-5.2`.
2. `git add requirements.in requirements.txt core/settings.py docs/ACTUALIZAR-DJANGO-5.2.md`
3. `git commit -m "Django 5.2 LTS y STORAGES"` y `git push -u origin django-5.2`.
4. Abre el pull request y espera el CI en verde.
5. Si tienes staging, despliega ahí primero y revisa login, panel, foto de
   perfil y una cartola.
6. Fusiona a `main`.

**Cómo saber que quedó:** en producción, abre las herramientas del navegador
(F12) → **Red** y recarga. Los `.css` y `.js` tienen que llamarse con un hash,
por ejemplo `estilos.3f2a9c1b.css`, y responder con `Content-Encoding: br` o
`gzip`.

## Volver atrás

Si algo falla en producción, en Railway → **Deployments** → el despliegue
anterior → **Redeploy**. Esta actualización no trae migraciones, así que
volver no afecta la base.
