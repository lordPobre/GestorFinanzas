# Revisión de código y estructura (2026-09-25)

Revisado contra `lordPobre/GestorFinanzas@main` (commit `273637732aa2`).

## A. El repo no tiene lo que creemos que tiene

1. **`requirements.txt` sin hashes.** El de `main` pesa 366 bytes, tiene rangos (`>=`) y no hay `requirements.in`. El punto 9 de la guía está marcado como hecho, pero no llegó al repo. `anthropic`, `argon2-cffi`, `django-storages` y `boto3` no tienen tope de versión.
2. **`docs/` incompleto.** En `main` solo están `BRECHAS.md` y `GUIA-PENDIENTES-MANUALES.md`. Faltan `ARQUITECTURA`, `DEUDA-TECNICA`, `RESPALDOS`, `REGISTRO-TRATAMIENTOS`, `STAGING`, `DECISION-CIFRADO`, las auditorías y el resto. `.gitignore` además excluye `DESPLIEGUE-RAILWAY.md`.

## B. Plantillas sin uso

3. `detalle_persona.html` y `form_ingreso.html` no los usa ninguna vista: `detalle_persona` usa `prestamos.html`, que tiene su propio modal de abono y funciona. El `<script>` sin `nonce` de `detalle_persona.html` no afecta a nadie. Se borran las dos.

## C. Limpieza (sin cambiar comportamiento)

4. `build.sh` sobra: es de Render. Railway usa `railway.json`.
5. `settings.py`: `ALLOWED_HOSTS` por defecto incluye `finanzas.pythonanywhere.com`. `DEFAULT_FROM_EMAIL` cae en `MAILGUN_FROM`, y `correo.py` mantiene el envío por Mailgun. Si ya solo usas Resend, se van.
6. `settings.py`: el `try/except ImportError` envuelve la llamada a `load_dotenv`, no el import, así que no protege nada.
7. Hay 15 `except Exception`, varios con `pass` silencioso (`context_processors.py`, `middleware.py`). Hay que cambiarlos por la excepción concreta o registrar el error.
8. El perfil se crea en tres lugares: `get_or_create_profile` en `views.py`, `ActividadMiddleware` y `views_cuenta`. Debería hacerlo una sola señal `post_save` de `User`.
9. `middleware.py` importa `settings` dos veces dentro de `__call__`. El docstring de la política de contenidos menciona jsdelivr, cdnjs y Google Fonts, que ya no se usan.
10. Comentarios y docstrings en todo el backend. `CLAUDE.md` pide código sin comentarios. Se pueden quitar en un solo lote.
11. Las herramientas de desarrollo (`ruff`, `coverage`, `pip-tools`) se instalan sueltas en el CI. Deberían estar en un `requirements-dev.in` propio.

## D. Estructura del backend

12. **`views.py`: 82 KB y unas 1.900 líneas, con más de 60 vistas.** Propuesta: convertirlo en el paquete `finanzas/views/`, con un archivo por dominio (`panel`, `cuotas`, `movimientos`, `metas`, `prestamos`, `suscripciones`, `categorias`, `exportar`, `sistema`). `views_cuenta`, `views_cartola`, `views_encuesta` y `views_passkeys` entran al mismo paquete. `urls.py` cambia solo los imports. Las funciones auxiliares que quedan (`serie_cuotas`, `pendientes_del_mes`, `_insights_dashboard`…) pasan a `servicios/`, como ya indica `DEUDA-TECNICA.md`.
13. **`models.py`: 65 KB y unas 1.700 líneas, con 20 modelos.** Propuesta: paquete `finanzas/models/` (`movimientos`, `cuotas`, `prestamos`, `suscripciones`, `metas`, `cuenta`, `seguridad`, `encuesta`) con `__init__.py` reexportando todo. No genera migraciones porque la app sigue siendo `finanzas`.
14. **Pruebas:** hay 13 archivos sueltos, varios nombrados por lote (`tests_lote_a/b/c`). Propuesta: paquete `finanzas/tests/`, con un archivo por dominio.
15. **URLs con dos estilos:** `nueva-deuda/` y `editar-deuda/<id>/` frente a `categorias/<id>/editar/`. Conviene unificarlas, pero rompe marcadores y la PWA. Solo vale la pena con redirecciones desde las rutas antiguas. Es de baja prioridad.
16. **No tocar:** mover modelos a una app `cuentas` aparte (exige migraciones entre apps y el beneficio es poco) y renumerar migraciones (el salto 0016→0100 es inofensivo).

## E. Frontend

17. **Estilos en línea.** Plantillas como `detalle_persona.html` casi no usan clases y repiten colores escritos a mano (`#60a5fa`, `rgba(52,211,153,…)`) en vez de las variables de `finapp.css`. Propuesta: sacar los patrones repetidos a clases (`tarjeta-dato`, `etiqueta-estado`, `modal`) y los colores a variables.
18. **Unos 30 bloques `<script nonce>` dentro de las plantillas.** Propuesta: moverlos a `static/js/<pantalla>.js`, con los datos en atributos `data-*`. Así el navegador los guarda en caché y quedan fuera del HTML.
19. **Bloques `<style>` en las plantillas** con `!important` (`detalle_persona`, `onboarding`, `legal_base`, `auth_base`). Van a `finapp.css`.
20. `finapp.css` tiene 121 KB y `dashboard.html` 54 KB. No es urgente partirlos. Lo que conviene es ordenar el CSS por secciones con un índice y quitar reglas muertas.

## Orden propuesto

| Lote | Contenido | Riesgo |
| --- | --- | --- |
| 1 | A1, A2, B3, C4–C9, C11 | Bajo |
| 2 | D12: paquete `views/` y funciones a `servicios/` | Bajo-medio |
| 3 | D13 y D14: paquete `models/` y `tests/` | Bajo |
| 4 | E17–E19: JS a archivos estáticos, estilos a clases | Medio (visual) |
| 5 | C10: quitar comentarios | Bajo |

Cada lote se entrega por separado y se sube con el CI en verde antes de empezar el siguiente.

## Estado (25 de septiembre de 2026)

| Punto | Estado | Lote |
| --- | --- | --- |
| A1 requisitos con hashes | Hecho | 1 |
| A2 docs completos en el repo | Hecho | 1 |
| B3 plantillas sin uso | Hecho | 1 |
| C4–C9, C11 limpieza | Hecho | 1 |
| C10 comentarios | Hecho | 5 |
| D12 paquete `views/` y `servicios/` | Hecho | 2 |
| D13 paquete `models/` | Hecho | 3 |
| D14 paquete `tests/` | Hecho | 3 |
| D15 URL con un solo estilo | Hecho, con redirecciones 308 desde las rutas antiguas | 9 |
| D16 no tocar | Se mantiene | — |
| E17 estilos en línea y colores | Hecho: clases en el lote 6, colores a variables en el lote 12 | 6, 12 |
| E18 scripts a `static/js/pantallas/` | Hecho | 4a, 4b |
| E19 bloques `<style>` a `finapp.css` | Hecho | 4c, 8 |
| E20 ordenar `finapp.css` | Parcial: reglas sin uso quitadas e índice en `docs/ESTILOS.md` | 10 |

Fuera de la revisión se hicieron además el cambio a Python 3.13 (lote 7) y el panel de acceso corto en el teléfono (lote 8).

### Lo que queda de E20

No se movieron reglas de lugar. Se revisó con un programa qué reglas se podían mover sin cambiar el resultado: una regla puede cambiar de lugar si no define las mismas propiedades que las reglas que salta, o si nunca pueden aplicarse al mismo elemento. De 35 grupos de reglas fuera de su sección, solo 3 pasaron esa prueba. Los demás saltan reglas genéricas (`.x > *`, `.x span`) o clases que las plantillas arman con variables, y esos casos no se pueden descartar sin mirar cada pantalla.

La mayoría de esas reglas son los ajustes generales para teléfono que están en la sección de la barra inferior. Ahí funcionan bien y el índice lo indica. Si algún día se reordena, conviene hacerlo una sección a la vez, comparando capturas antes y después.
