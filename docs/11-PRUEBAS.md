# 11 · Pruebas y control de calidad

## Cómo se corren

```bash
python manage.py test                  # todo
python manage.py test finanzas.tests.test_cuotas
coverage run manage.py test && coverage report
ruff check .
python manage.py check --deploy        # con DEBUG=False
python manage.py makemigrations --check --dry-run
```

Durante las pruebas, `core/settings.py` quita `RESEND_API_KEY` del entorno, así que no sale ningún correo aunque tengas la clave en `.env`. Las llamadas a Anthropic y a Google siempre se simulan con `unittest.mock`.

## Integración continua

`.github/workflows/ci.yml` corre en cada push a `main` y en cada pull request. Tiene cuatro trabajos:

| Trabajo | Qué hace | Si falla |
| --- | --- | --- |
| `pruebas` | Levanta Postgres 18. Instala con `--require-hashes`, corre `ruff check`, `makemigrations --check`, `coverage run manage.py test` y `coverage report` | Build en rojo. La cobertura mínima es 55 % (`fail_under` en `pyproject.toml`) |
| `despliegue` | `check --deploy --fail-level WARNING` con `DEBUG=False` | Build en rojo: significa que falta un ajuste de seguridad de producción |
| `dependencias` | `pip-audit --strict` sobre `requirements.txt` y `requirements-dev.txt` | Build en rojo: hay una dependencia con una vulnerabilidad conocida |
| `estilo-ampliado` | `ruff` con las reglas S (seguridad), B, DJ y UP | Solo informa (`--exit-zero`) |

Las pruebas corren contra Postgres, igual que producción, y no contra SQLite. Dependabot abre PRs semanales para pip (los lunes, con parches y versiones menores agrupados) y mensuales para las GitHub Actions.

En el CI, el usuario y la base de Postgres se llaman `fintora` y `ALLOWED_HOSTS` es `fintora.example`.

## Qué cubre cada archivo

Son 24 archivos en `finanzas/tests/` con 283 pruebas.

| Archivo | Pruebas | Qué asegura |
| --- | --- | --- |
| `test_acceso_y_montos.py` | 17 | Admin: su login es el de la app, sin sesión manda al acceso, cuenta sin permiso → 404 y evento, el personal entra. Topes de intentos: 5 por usuario+IP, cambiar de IP no salta el tope de la cuenta, una IP contra muchas cuentas se frena, entrar bien no limpia el contador de la IP, con la cuenta bloqueada la contraseña correcta no entra. Eventos de seguridad: acceso y fallo quedan anotados, la descarga de datos los incluye, borrar la cuenta deja la evidencia sin vínculo, la purga borra solo lo de más de un año. El destino se conserva al pasar por 2FA. Las sumas del mes no arrastran error de coma flotante |
| `test_cabecera.py` | 1 | Las pantallas sueltas traen el perfil que usa la cabecera |
| `test_cartola_cuentarut.py` | 10 | Lector de CuentaRUT: reconoce el formato, lee todas las filas, completa el año, deduce el signo por la cadena de saldos, une descripciones partidas en dos líneas, quita el número de operación, cuadra contra los totales declarados, avisa si falta una fila, rechaza un PDF sin detalle y no se lo lleva el lector genérico de BancoEstado |
| `test_cartola_tabla.py` | 14 | CSV/Excel: detecta extensiones, columnas cargo/abono, monto con saldo, monto con signo, rechazo de columnas desconocidas y de archivos vacíos. La muestra anónima borra nombres y cifras, conserva la estructura y respeta el tope de líneas |
| `test_conservacion.py` | 19 | Inactividad: quién entra en la lista, la sesión abierta cuenta como actividad, superusuarios fuera, un solo aviso, sin correo no hay aviso, no se borra sin aviso ni durante la gracia, quien vuelve sale de la cola, el borrado se lleva todo, `--seco` no toca nada. Topes de cartola: movimientos, páginas y texto |
| `test_cuenta.py` | 13 | Verificación de correo al registrarse: no bloquea el uso, el enlace confirma sin iniciar sesión, un token inventado no sirve, cambiar el correo invalida el enlace anterior. Sesiones abiertas: anotar, marcar la actual, cerrar las demás, no cerrar las de otra persona, salir borra la fila |
| `test_cuotas.py` | 18 | Arrastre de cuotas atrasadas al mes actual sin doble conteo. Reparto del redondeo en la última cuota. Periodos a pagar, pagados y atrasados. `resumen_mes`: ingresos, gastos, cuotas pagadas y pendientes, sin duplicar el egreso de la cuota. `DeudaForm`: total = cuota × cuotas, cuota en cero, edición, total desbordado |
| `test_derechos.py` | 16 | Fechas: ingreso futuro hasta un año, gasto futuro rechazado. Descarga de mis datos: trae lo propio, no lo ajeno, no entrega el secreto 2FA, pide sesión. Borrado de la cuenta: exige contraseña y la palabra ELIMINAR, borra todo lo que cuelga y no toca otra cuenta. `/salud/` responde sin sesión. 2FA: bloqueo tras cinco códigos malos |
| `test_landing.py` | 21 | La landing sin sesión, el inicio con sesión, `?fuente=pwa` → acceso, scripts con nonce. Chat de ayuda: respuesta, sin respuesta, validación, solo POST, tope por visitante, limpieza del historial, sin clave no llama, tope diario. Formulario de contacto: llega al correo, valida, trampa para bots, error si no sale. La política declara el chat |
| `test_legal.py` | 4 | Pestaña marcada, versión y contacto, secciones con ancla y título, scripts con nonce |
| `test_moneda_exportacion_ia.py` | 21 | Filtros de plantilla de moneda (`money`, `money_signed`, `money_corto`, `pct`, `a_json`). Exportación CSV y Excel, con y sin movimientos. IA: el prompt lleva los números; sin clave o sin datos no llama; respuestas en bloque de código, sin claves, no JSON o con error de la API. `analizar_finanzas` con y sin movimientos |
| `test_passkeys_google_encuesta.py` | 24 | 2FA: la contraseña sola no abre sesión, código correcto, código malo anotado, un código no sirve dos veces. Face ID o huella: vincular pide contraseña, desafío, verificación obligatoria de la persona, sin desafío se rechaza, credencial desconocida se rechaza y se anota, firma válida entra, firma de otra cuenta no entra, no se puede quitar la de otra persona. Encuesta: guardado, obligatorias, rangos, resultados solo para el personal, CSV. Token de Google: válido, correo sin verificar, otra aplicación, vencido, otro emisor. Pantalla de cartolas con y sin sesión |
| `test_privacidad.py` | 9 | Páginas legales públicas con responsable, contacto y versión. Sin aceptar la política no se crea la cuenta, y al aceptar queda registrada. Con la IA apagada el servidor no la llama. El registro de actividad marca a los usuarios con sesión y no escribe nada sin sesión |
| `test_rutas.py` | 5 | Cada ruta antigua lleva a la nueva con 308: conserva el método POST y la consulta. Las rutas nuevas siguen un solo estilo. El atajo de ingreso abre el formulario con el tipo |
| `test_terceros_fotos_cache.py` | 11 | Ninguna página (acceso, legales, inicio con gráficos) pide recursos a terceros, ni en el HTML ni en la CSP. La política declara Face ID, encuesta, registro de seguridad y respaldos. Las fotos se sirven con URL firmada. Caché de meses cerrados: no recalcula, se invalida con movimientos o cuotas nuevas, el mes en curso nunca sale de caché y cada usuario tiene la suya |
| `test_vistas.py` | 8 | Aislamiento: un usuario no alcanza ni modifica objetos de otro, y las listas solo muestran lo propio. Las pantallas privadas piden sesión. Con `prefetch_related` no hay consultas extra por fila |
| `test_ritmo.py` | 7 | Avisa cuando una categoría se pasa del promedio, da el monto por día si aún hay margen, no avisa antes del día 7 ni con un solo mes de historial, ignora suscripciones y pendientes, felicita si se gasta menos |
| `test_detectar_suscripciones.py` | 11 | La clave ignora números y palabras de relleno, pide 3 meses seguidos y montos parecidos, descarta dos cobros en un mes y lo que dejó de cobrarse, ignora lo ya registrado y lo descartado, agregar no duplica el cobro del mes |

## Qué no tiene pruebas hoy

Estos son los huecos que conviene cubrir primero, ordenados por riesgo:

1. **Reactivar una suscripción en enero.** Hoy falla (ver [13 · Deuda técnica](13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md)). Una prueba con la fecha fija en enero lo habría detectado.
2. **Importar una cartola hasta el final** (`confirmar_cartola`), en especial la opción “compra en cuotas”.
3. **Vinculación de Google con una cuenta existente sin correo verificado.**
4. **Lectores de Banco de Chile, CMR y Ripley.** Tienen documento real de referencia, pero no una prueba propia como CuentaRUT.
5. **`avisar_pagos`**: día efectivo en meses cortos y un solo envío por periodo.
6. **`respaldar_postgres`** con `--seco` en el CI, contra el Postgres del servicio.
7. **Frontend**: no hay pruebas de JavaScript. Los flujos críticos (registrar desde el panel, pagar desde el inicio, el chat de ayuda) solo se prueban a mano.

## Cómo se escribe una prueba nueva

- Una prueba por comportamiento, con el nombre como frase en español que diga qué se espera: `test_pagar_el_mas_antiguo_avanza_al_siguiente`.
- `SimpleTestCase` si no toca la base (lectores de cartola, filtros). Si la toca, `TestCase`.
- Para dos usuarios, heredar de `BaseDosUsuarios` en `test_vistas.py`: arma a Ana y a Beto con datos de cada tipo.
- Servicios externos siempre simulados: `mock.patch('anthropic.Anthropic')`, `mock.patch.object(correo, 'enviar')`, `mock.patch.object(chat_ayuda, 'responder')`.
- Si la prueba usa topes o caché, llamar a `cache.clear()` en `setUp`.
- Para cartolas se usa texto de ejemplo con datos inventados dentro de la prueba. Nunca una cartola real.
