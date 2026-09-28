# 14 · Convenciones y guía de contribución

## Idioma

- **Todo en español:** la interfaz, los mensajes, los nombres de variables, funciones, vistas, URL, modelos y pruebas (`periodos_pendientes`, `test_pagar_el_mas_antiguo_avanza_al_siguiente`). Se usa inglés solo donde lo impone Django o una librería (`save`, `clean`, `get_queryset`).
- **Tono:** se tutea (“anota”, “te quedan”), no se usa voseo. Frases cortas, sin tecnicismos para el usuario. Los montos en formato chileno: `$12.500`.
- La marca es **Fintora**. Los identificadores internos `finapp` se dejan como están (ver D-17 en [12 · Decisiones](12-DECISIONES.md)).

## Código

- **Sin comentarios ni *docstrings*.** Si algo necesita explicación, el nombre tiene que decirlo. Si es una decisión, va en `docs/12-DECISIONES.md`.
- Python 3.13, `ruff` con línea de 110 caracteres. `ruff check .` tiene que pasar.
- **Capas:** la vista lee la petición y responde. Los cálculos van en `servicios/` y no leen `request`. Lo que se deduce de los campos de un modelo va en una propiedad del modelo.
- **Dinero con `Decimal`**, nunca `float`, en todo lo que se guarda o se suma. Convertir a `float` solo para graficar.
- **Siempre filtrar por el dueño:** `get_object_or_404(Modelo, pk=…, usuario=request.user)`. No hay excepciones.
- Las acciones que cambian datos van por POST. Si la pantalla las usa sin recargar, responden JSON cuando llega `X-Requested-With: XMLHttpRequest`.
- Los errores externos (IA, correo) se registran con `log` y la vista sigue funcionando. Nunca un `except Exception: pass` sin registrar.
- Nada de configuración escrita en el código: variables de entorno leídas en `core/settings.py`.
- Módulo nuevo en `finanzas/` o archivo nuevo en `views/`, `servicios/` o `models/`: uno por tema. Si es un modelo, reexportarlo en `models/__init__.py`.

## Plantillas, CSS y JavaScript

- `<script>` siempre con `nonce="{{ csp_nonce }}"` y desde un archivo en `static/js/pantallas/`. Nada de JavaScript en línea ni de `onclick=`.
- Nada de recursos de terceros (fuentes, CDN, analítica). Si hace falta una librería, se copia a `static/vendor/` con su licencia.
- Colores y medidas con los tokens de `finapp.css`. Los estilos nuevos van en la sección de su pantalla (`docs/ESTILOS.md`).
- Texto que viene del usuario, de una cartola o de la IA: autoescape en la plantilla y `textContent` en JavaScript. Nunca `|safe` ni `innerHTML` con datos.
- Todo control táctil de 44 px como mínimo. Respetar `prefers-reduced-motion`.

## URL

`/<recurso>/`, `/<recurso>/nueva/` o `nuevo/`, `/<recurso>/<id>/<acción>/`, con palabras en español y guiones. Si se cambia una ruta existente, se deja la antigua en `RUTAS_ANTIGUAS` con 308.

## Base de datos

- Cada cambio de modelo, con su migración en el mismo commit. El CI lo exige.
- Migraciones compatibles hacia atrás durante el despliegue: agregar, usar y borrar en tres pasos.
- No renumerar migraciones.
- Restricciones en la base (`UniqueConstraint`) para lo que no puede duplicarse.

## Pruebas

- Toda corrección de un error trae la prueba que lo habría detectado.
- Toda vista nueva con datos queda cubierta por el aislamiento de `test_vistas.py` (un usuario no alcanza lo del otro).
- Los servicios externos siempre simulados. Nunca una cartola ni un dato real en una prueba.
- Detalle en [11 · Pruebas](11-PRUEBAS.md).

## Git y entregas

- `main` es producción: se despliega sola en Railway. Se trabaja en una rama y se fusiona con un PR y el CI en verde.
- Un commit por cambio con sentido, con el mensaje en español y en infinitivo o descriptivo: “Chat de ayuda en la landing”, “Corregir reactivación de suscripciones en enero”.
- Las dependencias se cambian en los `.in` y se recompilan los `.txt` con hashes, en el mismo commit.
- Los cambios grandes van en **lotes** chicos, cada uno subido con el CI en verde antes del siguiente.
- Nunca se suben `.env`, `db.sqlite3`, `media/`, `respaldos/` ni volcados de la base (están en `.gitignore`).

## Documentación

- Esta carpeta es la referencia. Un cambio que altera algo descrito aquí actualiza el capítulo en el mismo PR.
- Cambios en qué datos se tratan, con quién o por cuánto tiempo: actualizar `docs/REGISTRO-TRATAMIENTOS.md`, `privacidad.html` y `legal.VERSION`, y avisar a los usuarios antes de que rija.
- Un lector de cartola nuevo actualiza `docs/CARTOLAS-COBERTURA.md`.
- Un incidente se anota en `docs/BRECHAS.md`. Un simulacro, en `docs/RESPALDOS.md`.

## Lista antes de fusionar

- [ ] `python manage.py test` en verde
- [ ] `ruff check .` sin errores
- [ ] `makemigrations --check` sin cambios pendientes
- [ ] Probado en el teléfono (o con F12 en ancho de teléfono)
- [ ] Sin scripts sin nonce ni recursos externos nuevos
- [ ] Documentación actualizada si corresponde
- [ ] Si toca datos personales: registro de tratamientos y política revisados
