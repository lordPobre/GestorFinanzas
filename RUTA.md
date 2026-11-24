# Ruta de Fintora

Un paso por lote. Al terminar un paso: marcarlo con [x], anotar el número de lote y pasar al siguiente. Si un paso resulta más grande de lo previsto, se parte en sub-pasos aquí antes de seguir.

Los códigos (B2, F1, D12…) son los de `Revision Fintora.dc.html` y `docs/13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md`.

## Paso 19 · Después del 2c (decidido el 24 de noviembre)

**Modelo de negocio:** todo gratis mientras se pueda sostener. Se mantienen los topes de IA (20 cartolas al mes, 30 preguntas al día) y los lectores propios bajan el gasto, porque si cuadran no se llama a la IA (lote 282).

- [x] 19a (lote 283). Ley 21.719, vigente el 1 de diciembre. `docs/REGISTRO-TRATAMIENTOS.md` (tratamientos 20 a 23) y `docs/07` con Telegram, la lectura de cartolas con Anthropic, los repetidos con IA, las preguntas a la esfera, la clave personal y el audio a texto con ElevenLabs. La landing, Importar cartola y el chat de ayuda dicen cuándo la cartola pasa por Anthropic. Queda para ti: el DPA de ElevenLabs (plan de pago) y el de Sentry en `legal/dpa/`, y revisar el aviso de la 1.10.
- [ ] 19b. Ingreso fijo: el sueldo mensual se anota solo cada mes y el monto de un mes se puede cambiar (horas extra) sin tocar el sueldo base. Maqueta primero.
- [ ] 19c. Lectores propios por banco, uno por lote y con una cartola real de cada uno: Santander, BCI, Scotiabank y los que se pidan. Si cuadran, se usan antes que la IA.
- [ ] 19d. Transiciones entre pantallas en `fintora-2c.css`: se perdieron en el lote 276, porque `@view-transition` quedó solo en `tema-vidrio.css` y `transiciones.css` se borró.
- [ ] 19e. Operación: staging en `.railway/railway.ts`, borrar `railway.json` de la raíz, primer simulacro de respaldo, DMARC a `quarantine`, DNSSEC y un monitor externo de `/salud/`.
- [ ] 19f. Cada lote como rama con su PR (el CI ya corre en los PR) y un lote de documentación: `docs/13` y `PENDIENTES.md` quedaron en octubre.

## Para mañana (dejado el 9 de noviembre, en la noche)

**Decisión del 9 de noviembre:** el 2c tiene que quedar **igual al prototipo** (`Fintora Prototipo 2c.dc.html` en el teléfono y `Fintora Escritorio 2c.dc.html` en el computador), detalle por detalle. Solo se mantienen las lógicas (vistas, contexto, formularios, URLs y scripts que hablan con el servidor). Las pieles de los lotes 241 a 246 (`tema-2c.css` sobre las hojas viejas y `tema-2c-auto.css`) no alcanzan: pelean con `finapp.css` y `tema-vidrio.css` y se ven mal.

**Paso 17 · El 2c desde cero, sin las hojas viejas.** Cambio general: con la cookie, las pantallas 2c dejan de cargar `finapp.css`, `tema-vidrio.css` y las pieles. Usan una base nueva y una sola hoja escrita desde el prototipo.

- [x] 17a (lote 247, `sw.js` v109; va después de los lotes 245 y 246). `base_2c.html` y `fintora-2c.css`, con Inicio, Este mes, Cuotas y Suscripciones ya en la base nueva. La base carga solo `capas.css` (letra y Font Awesome) y `fintora-2c.css`, con medidas, colores, radios y sombras copiados del prototipo:
  - **Barra lateral de 248 px:** Fintora, Inicio · Pagos · Plan · Tú, «Anotar», la tarjeta de salud con «Toca para preguntar» y la persona abajo.
  - **Encabezado:** el título de la sección, el mes en píldora y la campana.
  - **Barra de abajo flotante:** 72 px y radio 28, con «Anotar» al centro.
  - **Hoja que sube:** para el panel Registrar y los avisos.
  - **Aviso flotante:** para los mensajes de la app.
  - Mismos ids y `data-*` de hoy, para que sigan funcionando `finapp.js`, `panel-carga.js`, `anotar.js`, el tour y la esfera.
  - La franja de la barra de estado no se toca: sigue en `tema-vidrio.css` para el diseño de siempre. Con el 2c la barra del iPhone va en `default` y no hace falta.
- [x] 17b (lotes 248 a 250, `sw.js` v112; el 249 arregla la base y el 250 la distribución en el computador). Inicio: teléfono con el orden y las piezas del prototipo (Lo que viene nuevo) y escritorio como `Fintora Escritorio 2c`. Antes: `dashboard_2c.html` a `base_2c.html`, con el marcado del prototipo. En el teléfono: Noviembre ▾, campana y avatar; la cifra; «Escuchar mi mes»; los 4 cuadros de «En qué se va»; lo que viene y los últimos. En el computador, la columna de `Fintora Escritorio 2c`.
- [x] 17c (lote 253). Pagos: Este mes, Cuotas, Suscripciones y Préstamos, con el marcado del prototipo (Préstamos con su plantilla propia y la persona en su pantalla, como `persona` del prototipo).
- [x] 17d (lote 253). El panel Registrar, Avisos, los formularios en hoja (compra en cuotas, préstamo, meta, suscripción) y los montos (abono, aporte, tope), como las hojas del prototipo.
- [x] 17e (lote 253). Plan: Metas (lista con barra y «Aportar»), Tu plan (pasos y «¿Me alcanza?»), Estadísticas (barras por mes y categorías) y Análisis IA, como el prototipo. Antes, la parte de escritorio en `Fintora Escritorio 2c.dc.html`.
- [x] 17f (lote 253). Tú: la lista de Tú, Categorías y topes, Importar cartola y Telegram, como el prototipo. Antes, su parte de escritorio.
- [x] 17g (lote 253). Entrar y la landing, desde `Fintora Login 2c v2.dc.html` y `Fintora Landing 2c.dc.html`, con plantillas propias.
- [x] 17h (lote 253). Quitar las pieles (`tema-2c-auto.css` y lo que sobre de `tema-2c.css`) cuando todas las pantallas estén en `base_2c.html`.
- [x] 17i (cerrado con el paso 18, lotes 275 a 277). Probar el lote 253 en el teléfono y el computador, ajustar lo que no calce y, cuando esté bien, poner `DISENO_2C_PARA_TODOS=1` en Railway. Después, en un lote propio, borrar las plantillas viejas y la cookie.
  - [x] Lote 254 (`sw.js` v116): la esfera del teléfono sube al centro y habla como el prototipo, Anotar como la hoja del prototipo, Tú principal como el prototipo con «Privacidad y seguridad» aparte, Tu plan con cifra, pasos y «¿Me alcanza?» arriba y el resto en «Más para tu plan», gráficos del plan en claro, colores de categoría en la paleta suave, Inicio en el orden del prototipo, pestañas en píldoras debajo del título, Pagos y Cuotas sin lo que no está en el prototipo.
  - [x] Lote 255 (`sw.js` v117, incluye el 254): mes en Cuotas, Suscripciones y Préstamos; Suscripciones y Préstamos en el orden y colores del prototipo; Plan en el teléfono solo con lo del prototipo.
  - [x] Lote 256 (`sw.js` v118, incluye 254 y 255): Inicio en el computador como el prototipo (esfera y barra lateral con el mismo estado que la cifra, cuadros de categoría, chispa de cuotas), Este mes en el computador sin filtros.
  - [x] Lote 257 (`sw.js` v119, incluye 254 a 256): pedido del 10 de noviembre. Todo en una columna en el computador (salvo Préstamos, que mantiene la persona al lado), logo de Fintora en la barra lateral, Inicio del teléfono, landing y Entrar, Inicio del computador con más vida (reparto de categorías, Por pagar en dos columnas con «Pagar», cuotas y «Cómo sigue tu plata» a lo ancho), Tu plan con sus piezas en estilo 2c y controles al lado del resultado, Tú por partes (Avisos, Tus datos, Seguridad, Privacidad) en el teléfono y el computador.
  - [x] Lote 258 (`sw.js` v120): la app instalada ya no sirve hojas viejas (red primero para `.css`, `.js` y `.json`), panel de la esfera en claro en el computador, Importar cartola sin cajas grises, Suscripciones con el peso de cada una.
  - [x] Lote 259 (`sw.js` v121): el mes del teléfono en Plan · Estadísticas a la derecha del título, barras con meses cortos que terminan en el mes elegido, Tu plan del computador rehecho (la cuenta de la cifra, Tu ruta, Prueba tu plan con una herramienta a la vez). La captura de Tu plan del 10 de noviembre traía `plan-2c.css` del 254: revisar que el despliegue corra.
  - [x] Lote 260 (`sw.js` v122): Entrar igual a `Fintora Login 2c v2.dc.html` (teléfono con huella y «Usar mi contraseña» sin tarjeta, la tarjeta al pedir la contraseña, computador en dos columnas con la esfera junto a la cifra).
  - [x] Lote 261 (`sw.js` v124, incluye 260): logos de las apps ajustados en el 2c, logo 2b (esfera verde con la F blanca) en todas las páginas, la pestaña y el ícono de la app; el teléfono de la landing 2c también en el celular.
  - [x] Lote 262 (`sw.js` v125, incluye 261): Préstamos 2c rehecho como `Fintora Prestamos 2c.dc.html` (cabecera con reparto y lo del mes, personas, persona con cuotas en fila e historial de abonos) en computador y teléfono.
  - [x] Lote 263 (`sw.js` v126, incluye 262): Privacidad, Términos y Seguridad con el 2c (`legal_base_2c.html` y `legal-2c.css`), elegidas por la vista según la cookie.
  - [x] Lote 264 (`sw.js` v127, incluye 263): Crear cuenta y el resto del acceso con el 2c (`auth_base_2c.html`), y la app instalada a pantalla completa (`black-translucent` en todo el 2c, manifest crema).
  - [x] Lote 265 (`sw.js` v128): puntos 1 y 2 de la revisión visual del 11 de noviembre. `heredadas-2c.css` viste en 2c Revisar cartola, seguridad de la cuenta, encuesta, repetidos, formularios, Movimientos «Ver todo», Primeros pasos y los avisos; montos de Avisos con separador.
  - [x] Lote 266 (`sw.js` v129): el tour en el 2c (`tour-2c.css`, 19 pasos, Anotar en la barra, esfera de Inicio, sin el paso de deslizar, los pasos de Tú abren su parte) y la cartola de tarjeta por ciclo (sin fecha de cierre, las compras desde el 20 van al mes siguiente; la lectura con IA también aplica el ciclo).
  - [x] Lote 267 (`sw.js` v130): Anotar igual a la hoja del prototipo (`anotar-2c.css`, `anotar-2c.js`) y Revisar cartola ordenada (`revisar-2c.css`: contadores, logos en círculo, opciones sin cortar, barra de guardar en una línea).
  - [x] Lote 268 (`sw.js` v131): más vida en el computador según `Fintora Escritorio Vida.dc.html` (Inicio con «Tu mes día a día», Metas, Estadísticas, Análisis IA y Tú), saludo según la hora sobre la cifra y «Ocultar» de Primeros pasos arreglado en el 2c.
  - [x] Lote 269 (`sw.js` v132): pedido del 12 de noviembre. Cuotas con botones parejos y «Compras que ya pagaste» plegable, Editar movimiento y las suscripciones en ventana flotante como Editar compra (`editar-flotante.js`), Estadísticas con líneas de referencia y montos en las barras, categorías sin el mini gráfico encimado, «Por qué ese número» sin salirse de la tarjeta y Tú ordenado en el computador.
  - [x] Lote 270 (`sw.js` v133): punto 3 de la revisión visual según `Correos y Errores 2c.dc.html`. Los 10 correos en papel crema con la esfera (aparato nuevo, cambio de correo y registro repetido ahora con HTML), páginas de error con la esfera del color del problema, bienvenida 2c, aviso de cookies 2c e imagen al compartir nueva.
  - [x] Lote 271 (`sw.js` v134): «Eliminar gastos» en Movimientos según `Eliminar gastos del mes.dc.html`. Borra los gastos del mes (no ingresos, cuotas, suscripciones ni cuentas por pagar), con confirmación, total y «Deshacer» por 10 segundos (`servicios/borrar_mes.py`).
  - [x] Lote 272 (`sw.js` v135): pantalla Indicadores (dólar, euro, UF, UTM) con gráfico que se recorre, rangos, conversor y verde/rojo según suba o baje. Datos de mindicador.cl cada hora (`servicios/indicadores.py`), entrada en Tú.
  - [x] Lote 273 (`sw.js` v136): arreglo de Indicadores (fecha leída sin zona horaria, espera de 12 s, último mes si falla el año, registro de fallas).
  - [x] Lote 274 (`sw.js` v137): Indicadores pasa a indicadores.cl, porque mindicador.cl no responde desde Railway. Se cita con enlace al pie.
  - [ ] Revisión visual, lo que queda: punto 4 (botones bajo 44 px, letra de 10 y 11 px, texto tenue), punto 5 (pasar el mouse, foco de teclado, ventanas de 721 a 1000 px) y punto 6 (escala de letra y radios, recorrido guiado; «Volver al diseño actual» ya salió en el lote 275).
  - [ ] Probar los lotes 259 a 265 con capturas del computador (Tu plan, Inicio, Pagos, Préstamos y Tú) y del teléfono (Estadísticas con otro mes, Pagos, Préstamos, la landing, Privacidad, Crear cuenta, la app instalada, Revisar cartola, Seguridad y Movimientos) y seguir con lo que no calce.

**Paso 18 · Dejar solo el 2c.** Revisado contra `main` el 13 de noviembre (`sw.js` v137). Decisión del 13 de noviembre: `tema-vidrio.css` se queda en el repositorio sin cargarse, con la franja intacta (CLAUDE.md no cambia).

- [x] 18a (lote 275, `sw.js` v138). Repetidos 1a/1b en un lote (sin `repetidos.css`), página sin conexión de `sw.js` en papel crema con la esfera, y sacar «Volver al diseño actual» del menú de la cuenta, de la hoja Más de `base_2c.html` y de la pestaña de Tú en `_navegacion.html`.
- [x] 18b. Ya no hace falta: el lote 276 deja el 2c fijo. Si la variable `DISENO_2C_PARA_TODOS` está en Railway, se puede borrar.
- [x] 18c (lote 276, `sw.js` v139). Lote de borrado:
  - Plantillas viejas con par `_2c`: base, dashboard, deudas, por_pagar, suscripciones, prestamos, metas, plan, estadisticas, analisis, perfil, categorias, importar_cartola, clave_api, form_transaccion, form_suscripcion, editar_suscripcion, onboarding, landing, legal_base, `registration/auth_base` y `registration/login`.
  - `diseno.py`, `plantillas_2c.py`, `templatetags/diseno.py`, `views/diseno.py` y sus URLs; las ramas `diseno.activo` de `cuotas.py`, `panel.py`, `por_pagar.py`, `suscripciones.py`, `indicadores.py`, `legal.py` y `menu.py`; los `t2c` de `_inicio_movimientos.html` y `prestamos.html`.
  - Hojas solo del diseño viejo: `finapp.css`, `sesion.css`, `acceso.css`, `encabezado.css`, `salud-esfera.css`, `avisos.css`, `titulos.css`, `transiciones.css`, `marca-2b.css`, `inicio-esfera.css`, `cuotas-fin.css`, `perfil.css`, `categorias.css`, `por-pagar.css`, `prestamos-acciones.css`, `me-deben-mes.css`, `landing-telefono.css`, `landing-esfera.css`, `portada.css` y `login-esfera.css`. `tema-vidrio.css` no se borra.
  - Se quedan: `mes-elegir.css`, `cartola.css`, `plan-proyeccion.css` y `saldo-futuro.css`. `repetidos.css` y `repetidos.html` se borran aquí (desde el lote 275 el 2c usa `repetidos_2c.html`).
  - Pruebas: `test_diseno_2c.py`, `test_acceso_2c.py`, `test_estilos_calculados.py` y las que nombren plantillas viejas.
- [x] 18d (lotes 277 y 279). Pruebas que seguían mirando el diseño viejo (hoja «Más», calendario de Inicio, campanas, Por pagar de Inicio, barra de abajo) pasan al marcado 2c.
- [x] Lote 280 (`sw.js` v140), pedido del 22 de noviembre. La cartola con IA se lee en partes de 5.000 caracteres (100 filas en Excel y CSV) que van en paralelo, porque una sola parte de 16.000 tardaba unos 3 minutos (Haiku 78 s y Sonnet 103 s) y la pantalla se rendía a los 2. La pantalla espera hasta 5 minutos y no se corta si falla una consulta. La tarjeta de salud de la barra lateral muestra siempre el mes (`esfera_mes` solo viene de Inicio); en Metas, Cuotas y Suscripciones ya no muestra la esfera de la pantalla.
- [x] Lote 281, pedido del 22 de noviembre. En el estado de cuenta de Falabella la IA tomaba el monto de la compra (180.000) y no el valor de la cuota (30.000), porque la fila trae tres montos sin nombre de columna. Por eso las cuotas no se unían a Cuotas ni a Me deben, la suma no cuadraba con el total facturado y Sonnet repetía la lectura. El servidor corrige el monto con la línea impresa (valor de la cuota × cuotas = total a pagar).
- [x] Lote 282, pedido del 24 de noviembre. El estado de cuenta de noviembre seguía sin cuadrar: la IA y el lector de CMR no restaban las 3 devoluciones (−107.717). El lector de CMR ahora las lee como ingreso y cuadra (132 filas, $1 de diferencia); si el PDF es de un banco conocido y su lector cuadra, se usa ese sin gastar la IA. La IA cuenta los montos negativos de la tarjeta como devolución. Las cuotas también se unen a Cuotas y a Me deben por el precio o el total de la compra (cuotas con interés), y las uniones con el nombre más parecido se asignan primero.

**Lote 253 (9 de noviembre):** trae los lotes 245 a 252 y todo lo de 17c a 17h, más los arreglos de Inicio (falta el ingreso, Movimientos solo pasado, «Pagar», explicación de «Cómo sigue tu plata» y montos en las barras de cuotas). Se aplica con `aplicar.ps1 -Probar` encima de `main`. `sw.js` v115.

Cómo se trabaja cada lote del paso 17:
- El marcado sale del prototipo tal cual, pasando los estilos en línea a clases de `fintora-2c.css` (con la CSP no se pueden estilos en línea).
- El contexto sale de las vistas de hoy. Si falta un dato, se suma en un servicio `*_2c.py` sin tocar la lógica.
- Comparar con capturas del teléfono y del computador antes de dar el lote por bueno.

## Para mañana (dejado el 8 de noviembre)

**Revisado contra `main` el 9 de noviembre:** los lotes 236 a 240 ya están subidos (`sw.js` v102, las plantillas `*_2c.html`, sus hojas, `inicio-2c.js`, `cuotas-2c.js`, la letra y las 6 pruebas `test_*_2c.py`). Las migraciones de los lotes 217 y 223 también (`0135_clave_api` y `0136_chat_telegram`). Lo que sigue abajo de «Antes de seguir» ya no aplica salvo probar en el teléfono.

Rediseño 2c, paso 16. Todo va detrás de la cookie `diseno=2c` (`/diseno/2c/` para activar, `/diseno/actual/` para volver). Sin la cookie la app queda igual que hoy.

Lotes armados el 8 de noviembre, **sin subir todavía**. Hay que subirlos en orden, porque cada uno va encima del anterior:
- 236 · 16a: base (colores, letra Familjen Grotesk, barra lateral, encabezado, barra de abajo, modales). `sw.js` v98.
- 237 · 16b: Inicio 2c y la barra de estado del iPhone en `default` con el 2c. `sw.js` v99.
- 238 · 16c: Pagos · Este mes, con las pestañas de Pagos y las cuotas de meses anteriores para pagarlas ahí. Prueba corregida (`?mes=AAAA-MM`). `sw.js` v100.
- 239 · 16d: Pagos · Cuotas, con Editar en un panel y Mes a mes. `sw.js` v101.
- 240 · 16e1: Pagos · Suscripciones. `sw.js` v102.

Antes de seguir:
1. Copiar los lotes 236 a 240 y correr `python manage.py test finanzas` y `node --test pruebas_js/*.test.js`. Si algo falla, pegar el error y se corrige antes del siguiente lote.
2. Correr la comparación de estilos del lote 171: sin la cookie tiene que dar cero.
3. Subir a `main` y probar con `/diseno/2c/` en el teléfono y en el computador lo que dice cada `LEER-PRIMERO.md`. En el iPhone instalado, cerrar y abrir la app para que tome la barra de estado.
4. Anotar lo que se vea raro (restos del tema oscuro, tamaños, espacios) para el lote de ajustes.

Siguiente, en orden:
1. ~~16e2, 16f y 16g~~ hechos en el lote 241 con la piel 2c. Antes: **16e2 · Préstamos** (lote 241). `prestamos.html` es grande: Me deben y Debo, mes a mes (`me_deben_mes.py`), abonos, la persona y WhatsApp. Bajar de `main` `prestamos.html`, `views/prestamos.py`, `me-deben-mes.js`, `prestamos.js` y `me-deben-mes.css` antes de empezar. Misma receta que los anteriores: `prestamos_2c.html` con el mismo contexto, pestaña «Préstamos» de `_pagos_pestanas.html` y los mismos scripts.
2. **16f · Plan.** Antes, la maqueta de escritorio de Plan (Metas, Tu plan, Estadísticas, Análisis IA) en `Fintora Escritorio 2c.dc.html`, que hoy muestra un aviso al tocar Plan.
3. **16g · Tú, categorías, cartola y Telegram.** Antes, su maqueta de escritorio.
4. **Ajustes 2c.** Lote 246 (`sw.js` v108): cajas grises más suaves, barra de abajo sin recuadro y sin «Cómo sale la cifra» en el teléfono. Siguen, con plantilla propia: Metas (lista con barra y «Aportar» del prototipo), Tu plan y Análisis. Antes: Lote 245 (`sw.js` v107): encabezado con el nombre de la sección, tarjeta de salud legible y `tema-2c-auto.css`, que pasa a papel y tinta los colores oscuros escritos a mano en las 19 hojas. Después, pantalla por pantalla con capturas nuevas. Antes: Parte 1 hecha en el lote 242 (`sw.js` v104): «Cómo sigue tu plata», Movimientos, elegir el mes, el panel Registrar y `form_deuda.html` con error. Queda lo que se anote al probar en el teléfono y los gráficos de Estadísticas. Antes: Lo anotado en el paso 4 de arriba, los modales de Movimientos y de «Cómo sigue tu plata» (todavía con restos oscuros) y el formulario de Editar cuota cuando trae un error (hoy cae a `form_deuda.html`).
5. **Navegación 2c.** Hecha en el lote 243 (`sw.js` v105): Inicio · Pagos · Anotar · Plan · Tú, pestañas de Plan y de Tú, sin botón flotante. Antes: Pasar la barra lateral y la barra de abajo a Inicio · Pagos · Anotar · Plan · Tú cuando existan Plan y Tú en 2c (`navegacion.py` y `test_navegacion.py`).
6. **16h · Landing** hecha en el lote 244 con la piel 2c y detrás de la cookie (`sw.js` v106). Falta **16i · Entrar**. Antes: **16h · Landing** y **16i · Entrar**, desde `Fintora Landing 2c.dc.html` y `Fintora Login 2c v2.dc.html`. Van sin cookie, porque se ven antes de entrar: se suben cuando el 2c quede para todos.
7. **Dejar el 2c para todos:** quitar la cookie y las plantillas viejas, en un lote propio.

Pendientes que siguen de antes (revisados contra `main` el 9 de noviembre):
- **14b, sin hacer.** Ninguna plantilla de la política nombra a Telegram (solo `clave_api.html`). Va con una política 1.10 en `legal.py` (hoy 1.9, desde el 9 de noviembre de 2026) y su aviso de cambio.
- **14c, sin hacer.** El bot solo trae el botón «Deshacer» (`views/telegram.py`). Faltan los dos botones con otras categorías para cambiarla ahí mismo; `callback_query` ya llega al webhook.
- **CSS chico, sin hacer.** `@view-transition` sigue en `tema-vidrio.css` (línea 368) y no en `transiciones.css`. Las reglas `.saludo-card` de `tema-vidrio.css` (324, 764 y 936) siguen ahí.
- Hecho: las migraciones de los lotes 217 y 223.

## Para mañana (dejado el 24 de octubre)

Estado de los lotes de hoy:
- **En `main`:** del 198 al 206, subidos el 24 de octubre. El 206 deja `sw.js` en v85.
- La política queda en 1.9. Revisar que `VIGENTE_DESDE` en `legal.py` tenga la fecha que corresponde (quedó la de la 1.8, «9 de noviembre de 2026»).
- Probar en el teléfono: aceptar la 1.9, bajar la hoja de Inicio, tocar «Pregúntame algo», hacer 4 preguntas y revisar que la respuesta se escuche.

Siguiente, en orden:
1. **13d · Preguntar con la voz.** El micrófono de 2a (teclado a la izquierda, micrófono al centro, repetir a la derecha), la grabación con la onda y el contador, y el audio a ElevenLabs para pasarlo a texto en el servidor, leído en memoria y sin guardarlo. Estados 3c (micrófono sin permiso, queda escribir) y 3d («No alcancé a entenderte», sin descontar la pregunta). La política 1.9 ya lo nombra.
2. **13e · La esfera en las demás pantallas.** Escritorio: el panel de 4a que sale de la tarjeta de salud de la barra lateral. Teléfono: el mismo panel desde la esfera de las otras pantallas.
3. **12b · La línea de saldo futuro en Inicio.** Maqueta primero, después la pantalla, con `proyeccion()` por `fetch` al abrirla.
4. **I3 · Anotar sin abrir la app** y **B12 · API pequeña y versionada.**
5. **Antes del 1 de diciembre:** pasar la configuración de Railway a `.railway/railway.ts`. Hecho en el lote 215 (24 de octubre): `.railway/railway.ts` escrito a mano, porque `migrate` le copiaba el `railway.json` de la web a los 9 servicios. `apply` aplicado y `plan` al día. La política de reinicio que es igual a la de Railway por defecto se dejó fuera, porque Railway no la guarda. En Windows, `plan` necesita `$env:_` apuntando a `railway.exe` (error del SDK). Los `.json` se borran en el mismo commit.

Pendientes chicos, sin lote:
- Confirmar en el teléfono que el lote 190 (panel Registrar al usarlo) no se siente lento al primer toque.
- En el próximo lote de CSS: pasar las reglas de `@view-transition` de `tema-vidrio.css` a `transiciones.css`, sumando `transiciones.css` a `onboarding.html` y `auth_base.html`, y revisar la sección 7 de `docs/ESTILOS.md`. `.saludo-card` sigue en uso en Encuesta (lote 216).

## Para retomar

- Último lote en `main`: **206** (I2 · 13c2, 24 de octubre). `sw.js` en v85.
- Tiempos del servidor (logs del 17 al 22 de octubre): `inicio/voz/` tarda de 1,8 a 3,5 s con 6 a 11 consultas, casi todo en preparar el audio la primera vez. `analisis/ia/` tardaba 15,7 s, lo que ya resolvió el lote 185. Inicio (`GET ''`) pasó una vez de 1,5 s (2 s, el 20 de octubre a las 21:59, quizás justo después de un despliegue), pero con **97 consultas**: B6 tiene que bajar ese número, no solo partir la vista.
- Antes del 1 de diciembre de 2026: Railway deja de leer `railway.json` y `railway/*.json` (aviso de la CLI del 22 de octubre). Hay que pasar la configuración de web, cola, audios y las tareas programadas a `.railway/railway.ts` con `railway config migrate`. Va en un lote propio.
- Siguiente: **I2 · 13d, preguntar con la voz**. Inicio queda en 53 consultas con el caché vacío tras el lote 196.
- Las copias de trabajo del repositorio se bajan de `main` con las herramientas de GitHub antes de cada lote (las de hoy son del 24 de octubre). No usar copias viejas.
- Correr también `node --test pruebas_js/*.test.js` en cada lote que toque JavaScript: el DOM mínimo de esas pruebas no trae `matchMedia` ni `style.removeProperty` (lote 188b).
- Antes de armar un lote de CSS, bajar de `main` el archivo que se va a tocar: se trabaja sobre lo que está subido, no sobre copias viejas.
- El usuario usa PowerShell. Comparación de estilos, con el código actual:

```powershell
$env:GUARDAR_ESTILOS = "estilos/antes.json"
python manage.py test finanzas.tests.test_estilos_calculados
Remove-Item Env:GUARDAR_ESTILOS
```

  Copiar el lote y comparar:

```powershell
$env:COMPARAR_ESTILOS = "estilos/antes.json"
python manage.py test finanzas.tests.test_estilos_calculados
Remove-Item Env:COMPARAR_ESTILOS
```

  Si el lote ya está copiado, medir el antes con `git stash push static/` y volver con `git stash pop`. La medición de antes y la de después se hacen con la misma versión de la prueba.

## Hecho

- [x] Log del servicio `audios` revisado el 24 de octubre: corre cada hora, arranca bien y borra de 0 a 1 audio vencido por corrida.

- [x] B2 · Decidir por relaciones, no por el texto
- [x] B4 · Un cobro de suscripción por mes (migración 0130)
- [x] B5 · Tope de consultas en Inicio
- [x] F7 · Títulos: dos ciclos y quietos
- [x] D2 · Color del título según el estado
- [x] F1 · Capas de cascada: `vendor` (lote 168) y todo el CSS propio en `app` (lote 169)
- [x] D12 · parte 1: ajustes de teléfono de `finapp.css` en su sección (lote 170)
- [x] Comparación de estilos antes y después (lotes 171 y 171b)
- [x] D12 · parte 2: Plan, Suscripciones, Cartola e Inicio juntos en `tema-vidrio.css` (lotes 172 a 175)
- [x] Revisión de seguridad: nombres de categoría con `textContent` en `base-4.js` y claves tachadas en la auditoría (lote 176)
- [x] Esfera fluida: variables en la hoja y no en `<html>`, arrastre por cuadro, esfera en pausa y oculta con la hoja arriba (lote 178)
- [x] Sin fantasma del panel Más en la transición entre pantallas: `pageswap` en `finapp.js` (lote 179)
- [x] CI: Trivy, Actions fijadas por SHA, permisos mínimos y respaldo sin root (lote 193)
- [x] B6 · 8b: Inicio de 74 a 37 consultas, con tope (lote 194)
- [x] B6 · 8c y 8d: calendario y lista de movimientos de Inicio al abrirlos (lotes 195 y 196)
- [x] F5: precarga del menú y transiciones con nombre entre pantallas (lotes 197 y 198)
- [x] La voz dice los números en palabras y con velocidad ajustable (lote 199)
- [x] La cartola reconoce las cuotas de compras que ya estaban en Cuotas o en Préstamos (lote 224)
- [x] La esfera se ve igual en Android y el brillo de arriba ya no se corta en la app instalada (lote 225)
- [x] La hoja de abajo ya no tapa el texto ni el botón para preguntarle a la esfera en pantallas bajas (lote 226)
- [x] Un gasto que aún debes puede llevar fecha futura y cuenta en el mes en que lo pagarás (lote 227)
- [x] La cartola reconoce el gasto que dejaste pendiente para el mes siguiente y no lo duplica (lote 228)
- [x] La cartola se lee con IA sin importar el banco o la tienda, también desde fotos y escaneos, y el servidor comprueba cada monto contra el archivo y los saldos o el total (lote 229)
- [x] La cartola protegida con clave se abre: Fintora pide la clave, la usa solo para abrir el PDF y no la guarda (lote 230)
- [x] Me deben mes a mes: saldo y cobros de los últimos 6 meses y proyección de los próximos 6, «Si pagan al día» o «Según cómo pagan» (lote 233; sin «Por persona» en el lote 234)
- [x] Limpieza: fuera 6 archivos sin uso y las reglas `.mes-*` de `finapp.css`, `humanize` solo donde se usa, y las rutas de acceso y perfil apuntan directo a sus vistas (lote 235)

## Siguiente

1. [x] **Comparar estilos antes y después** · `test_estilos_calculados.py` (lote 171; fecha fija en el lote 171b). Se usa en cada lote de CSS desde aquí.
1b. [x] **D12 · parte 2** · Juntar los trozos de cada pantalla de `tema-vidrio.css`, una pantalla por lote, con la comparación del lote 171 en cero. La franja de la barra de estado no se mueve.
    - [x] Plan (lote 172, comparado OK)
    - [x] Suscripciones (lote 173, comparado OK)
    - [x] Cartola y revisar cartola (lote 174, comparado OK)
    - [x] Inicio (lote 175, comparado OK)
    - [x] Préstamos (lote 177)
    - [x] Formularios (lote 180)
    - Lo demás que aparece repartido son componentes compartidos (`.sec-*`, `.nav-*`, `.chip-*`) o reglas que se cortan con un id, y se deja como está.
2. [x] **CSS sin uso** · 241 clases sin uso borradas de `finapp.css`, `tema-vidrio.css` y `sesion.css` (lote 181).
3. [x] **B3 · Categorías fase 2** · Revisado el 21 de octubre contra `main`: ya está todo hecho en los lotes 164 a 166 (migraciones 0132 a 0134). No hizo falta un lote nuevo.
4. [x] **B8 · Audios fuera de la base** · MP3 en R2 (`voz/`), 5 horas de vida y limpieza cada hora con `railway/audios.json` (lote 182).
5. [x] **B7 · Cola para IA, cartolas y correo** · Partido en sub-pasos (21 de octubre):
    - [x] 5a. La cola sola (lote 183): `django-q2` con la base como intermediario, `Q_CLUSTER` en settings, servicio `cola` en Railway (`railway/cola.json` con `qcluster`), pruebas en modo síncrono. Sin mover nada todavía.
    - [x] 5b. El correo a la cola (lote 184): `correo.encolar` para los correos de registro, verificación, aparato nuevo, recuperación y cambio de email. La landing y las tareas programadas siguen con `enviar`.
    - [x] 5c. El análisis con IA a la cola (lote 185): Análisis y Plan. La vista devuelve un número de tarea firmado, la pantalla consulta `analisis/ia/tarea/` y la tarea se borra al entregarla.
    - [x] 5d (lote 213). La cartola en segundo plano, con «Leyendo tu cartola…». No va a la cola porque django-q2 guarda los argumentos en la base: se lee en un hilo del proceso web con el PDF solo en memoria, 2 a la vez, y el resultado pasa por la caché hasta que la pantalla lo recoge. `sw.js` v88.
6. [x] **F2 · Navegación y pendientes sin duplicar** · Partido en sub-pasos (22 de octubre):
    - [x] 6a. La navegación en un solo lugar (lote 186): `navegacion.py` + `{% menu %}` para la barra lateral, la barra de abajo, la hoja Más y el menú de la cuenta. «Me deben» pasa a «Préstamos» y el verde de Préstamos vuelve a funcionar.
    - [x] 6b. El saludo una sola vez (lote 187): la tarjeta del saludo solo se dibuja en las 2 pantallas donde se ve (encuesta y resultados), la campana sale de `_campana.html` con una sola condición y la comparación de estilos identifica cada elemento por su clase. Quedan sin uso dos reglas `.saludo-card` en `tema-vidrio.css`, que se borran en el próximo lote de CSS.
    - [x] 6c. Los pendientes una sola vez (lote 188): cada pago sale una vez dentro de `.ini-regla`, con un formulario. En el teléfono y en el modal de atrasados se ve como lista gracias a `@container pendientes`. El modal se llena al tocar «N pagos atrasados».
7. [x] **F3 · Scripts por función y carga diferida** · Partido en sub-pasos (23 de octubre):
    - [x] 7a. Nombres por función y el tour, las marcas y los recordatorios al primer uso (lote 189): `modales-temprano.js`, `registro-sw.js`, `barra-estado.js`, `saludo-hora.js`, `panel-anotar.js` y `tour-arranque.js`, que carga `tour.js` solo cuando hace falta.
    - [x] 7b. El panel Registrar al primer uso (lote 190): `panel-carga.js` pide `anotar.js`, `anotar-tope.js` y `panel-anotar.js` al primer toque y abre el panel con el tipo del botón. `?registrar=1`, `abrir_panel` y `mantener-lugar.js` siguen funcionando.
    - [x] 7c. Módulos ES (lote 191): las 25 plantillas con sesión cargan sus scripts con `type="module"`, sin `import` ni `export`. Los 14 archivos que leían `currentScript` buscan su etiqueta por `data-js`. Siguen clásicos los cuatro que corren antes de pintar, lo que se carga al usarlo, Chart.js, `consentimiento.js` y las páginas sin sesión.
8. [x] **B6 · Inicio por bloques** · Partido en sub-pasos (23 de octubre):
    - [x] 8a. Sin cálculos que no se muestran (lote 192): las compras con sus pagos en una sola consulta y 34 valores sin uso fuera de `views/panel.py`. Medición opcional con `MEDIR_INICIO=1`.
    - [x] 8b (lote 194). Bajar las consultas fijas de Inicio (74 a 78 tras el 8a, sin crecer con las compras): `finanzas_transaccion` 24, `finanzas_suscripcion` 10, `finanzas_deuda` 10. Y un tope con `assertNumQueries`.
    - [x] 8c (lote 195). El calendario, los días con pagos y los modales de las metas al abrirlos, como fragmento HTML por `fetch`.
    - [x] 8d (lote 196). La lista del mes de «Movimientos» al abrirla, con el deslizar de `finapp.js` como `window.finappSwipe(raiz)`.
9. [x] **F5 · Transiciones entre pantallas** · Partido en sub-pasos (23 de octubre). `@view-transition { navigation: auto; }` y los nombres de la barra lateral, la barra de abajo y el botón de anotar ya estaban en `tema-vidrio.css`.
    - [x] 9a (lote 197). Precargar al ir a tocar el menú con Speculation Rules en `base.html`, con nonce y sin tocar la CSP.
    - [x] 9b (lote 198). `transiciones.css` con `titulo` (`.sec-titulo`), `cifra` (`.sec-monto` y el `.ini-monto` a la vista) y `esfera` (la grande en Inicio, la de la barra lateral en las demás). `test_transiciones.py` revisa que ninguna pantalla repita un nombre.

## Este trimestre

10. [x] **B1 · Dinero sin float** · Antes de I1, porque el saldo futuro suma montos. Partido en sub-pasos (24 de octubre):
    - [x] 10a (lote 200, en `main` el 24). El mes en `Decimal`: `_resumen_mes` y `_numeros_pasados` sin `float`, `redondear()` con `ROUND_HALF_UP` en `dinero.py`, usado en Inicio, la esfera, Estadísticas, `mes_tipico` y `money`. Claves de caché `mes-d:` y `meses-d:`.
    - [x] 10b (lote 201, en `main` el 24). `_plata()` por moneda en Inicio, `data-base` con `unlocalize`, sin `exacto`, y sin `float` en `desglose_categorias`, Estadísticas, `plan.py` y `recordatorios.py`.
11. [x] **D1 · Una dirección visual única** · `docs/ESTILOS.md`, «instrumento cálido» (lote 202). Lo que no cumple queda en su sección 7, para lotes de CSS.
12. [x] **I1 · Saldo futuro** · Partido en sub-pasos (24 de octubre):
    - [x] 12a (lote 203, en `main` el 24). `servicios/proyeccion.py`: el mes actual día a día desde «Puedes gastar», 3 meses adelante con el mes típico y los cobros conocidos, compra de prueba en cuotas, mes y día más justos.
    - [x] 12b (lote 214). Maqueta `Saldo Futuro.dc.html`, elegida la 1b: tarjeta «Cómo sigue tu plata» en la hoja de Inicio (mes actual), con la línea del mes y los 3 meses que vienen, que abre el detalle de 1a. Datos por `fetch` desde `inicio/proyeccion/`. `sw.js` v89.
13. [x] **I2 · La esfera responde preguntas** · Decidido el 23 de octubre. Va después de I1, porque «el mes más justo» sale de su proyección. Se pregunta por voz o por texto desde la esfera de todas las pantallas, con hasta 4 turnos. La respuesta siempre se escucha y también se ve escrita. Modelo Sonnet (`IA_MODELO_PREGUNTAS`), 30 preguntas por usuario al día. Responde: si alcanza para algo en N cuotas, cuánto queda este mes, cuánto se gastó en una categoría, cuándo termina una deuda y cómo van las metas.
    - [x] 13a. Maqueta en `Esfera Preguntas.dc.html` (23 de octubre). Teléfono: 2a (esfera grande al centro, una respuesta a la vez, las palabras se iluminan mientras habla; al grabar, onda, contador y barra «Grabando» con botón cuadrado). Estados: 3a (cuarta pregunta, «Empezar otra conversación»), 3b (tope diario, esfera gris), 3c (micrófono sin permiso, queda escribir), 3d («No alcancé a entenderte», no descuenta pregunta) y 3e (la voz falló, la respuesta queda escrita). Escritorio: 4a, panel de 420 px que sale de la tarjeta de salud de la barra lateral, con «Toca para preguntar».
    - [x] 13b (lote 204, en `main` el 24). `servicios/preguntas.py`: `simular_compra`, `queda_mes`, `gasto_categoria`, `fin_deuda` y `metas`, con esquemas para Anthropic, alias para los nombres y `restaurar()`.
    - [x] 13c (lote 205, en `main` el 24). Servidor: `ia_preguntas.py` con Sonnet y herramientas, conversación de 4 en el caché, tope de 30 al día, `esfera/preguntar/` por la cola y política 1.9.
    - [x] 13c2 (lote 206, en `main` el 24). Pantalla en Inicio (teléfono): «Pregúntame algo», conversación 2a con texto, respuesta escrita y hablada con palabras que se iluminan, estados 3a, 3b y 3e. `sw.js` v85.
    - [x] 13d (lote 208). Preguntar por voz: micrófono en la barra, grabación con onda y contador (2a), `esfera/preguntar/voz/` con ElevenLabs `scribe_v2` en memoria, estados 3c y 3d, `microphone=(self)`. La política 1.9 ya lo cubría. `sw.js` v86. Antes, el lote 207 fue el parche de Pillow 13, fuera de la ruta.
    - [x] 13e. La esfera de las demás pantallas. Partido en dos:
      - [x] 13e1 (lote 211). Teléfono: el panel se carga desde `base.html` en toda pantalla con esfera (Cuotas, Metas, Préstamos, Suscripciones), con ideas propias de cada una.
      - [x] 13e2 (lote 212). Escritorio: panel de 420 px de la maqueta 4a, que se abre desde la tarjeta de salud («Toca para preguntar») en las pantallas con esfera. La esfera del panel lee el resumen antes de la primera pregunta. `sw.js` v87.
    - Ajustes fuera de la ruta: lote 209 (la voz dice la moneda) y lote 210 (`cuotas_por_mes`).
14. [ ] **I3 · Anotar sin abrir la app** · Decidido el 25 de octubre, maqueta `Anotar Rapido.dc.html` (1a, 1b, 1d, 1e y la confirmación 2a):
    - Android: mantener presionado el ícono (`shortcuts` del manifiesto) → «Anotar gasto» / «Anotar ingreso» → pantalla mínima con un campo de texto libre o voz («5 lucas en café»), vista previa de monto y categoría.
    - iPhone: Atajo que pide el texto, llama a la API con la clave personal y muestra «Anotado: $X en Categoría». Se puede llamar con Siri.
    - Confirmación 2a: recibo con el monto grande, la categoría elegida y otras dos para cambiarla ahí mismo, «Deshacer» y «Listo» con cierre a los 4 segundos. Se guarda directo como gasto pagado.
    - Texto: primero reglas propias (número o «lucas», «ayer», palabra clave → categoría con las reglas de la cartola). Si no alcanzan, Haiku, solo con el análisis con IA activado.
    - Cambio del 25 de octubre: en vez de la pantalla de Android y el Atajo del iPhone, un bot de Telegram que sirve igual en los dos.
    - [x] 14a (lote 223, falta generar la migración con `makemigrations`). Bot de Telegram: «Conectar Telegram» en Anotar desde afuera con un enlace de un solo uso (10 minutos), `telegram/webhook/` con secreto, texto y audios (ElevenLabs, solo con IA), «Deshacer» en cada anotación, `/desconectar` y `configurar_telegram`.
    - [x] 14b (lote 278, política 1.10). Política de privacidad: Telegram como proveedor (los mensajes al bot pasan por sus servidores).
    - [ ] 14c. Confirmación 2a en el bot: botones con otras dos categorías para cambiarla ahí mismo.
15. [x] **B12 · API pequeña y versionada** · Va antes que 14a:
    - [x] 15a (lote 217, falta generar la migración con `makemigrations`). Clave personal en Perfil: una por persona, guardada como hash, se muestra una sola vez, con «usada hace…» y «Revocar». `/api/v1/` con `Authorization: Bearer`, sin CSRF, con tope por clave. `POST /api/v1/movimientos/` (texto libre o monto, descripción, categoría, tipo y fecha) responde el movimiento y «Anotado: $X en Categoría». `DELETE /api/v1/movimientos/<id>/` para deshacer, solo lo anotado por la API en las últimas 24 horas. `POST /api/v1/pagos/<tipo>/<id>/` para marcar un pago. El intérprete de texto queda en `servicios/anotar_texto.py` para que lo use también 14a.
    - [x] 15b (lote 218). Haiku cuando las reglas no encuentran el monto, `POST /api/v1/pagos/<tipo>/<id>/` (cuota, servicio, gasto, pendiente) y «Anotar desde afuera» en la hoja Más y el menú de la cuenta.
16. [ ] **Rediseño 2c en la app** · Decidido el 8 de noviembre. Maquetas: `Fintora Prototipo 2c.dc.html` (teléfono), `Fintora Escritorio 2c.dc.html`, `Fintora Landing 2c.dc.html` y `Fintora Login 2c v2.dc.html`. Solo cambia la vista: los números salen de lo que ya calcula la app, sin copiar la lógica de las maquetas.
    - Compras en cuotas: `DeudaForm` tal cual (valor de la cuota, cuántas, fecha del primer pago y categoría; el total lo calcula `save()`), pagos por período con `PagoCuota`, `periodos_atrasados` y `texto_urgencia`.
    - Total mensual: «Este mes pagas» es `total_cuotas_mes` de `views/cuotas.py`; Mes a mes es `serie_cuotas()`; en Inicio la cifra sale de `resumen_mes()` (gastos + cuotas del mes + `atrasado_arrastrado` + lo que debo a personas) y las cuotas de meses anteriores se muestran aparte.
    - [x] 16a (lote 236). Base detrás de la cookie `diseno=2c` (`/diseno/2c/` y `/diseno/actual/`): `tema-2c.css` con todas sus reglas bajo `html.t2c` (tokens, Familjen Grotesk, barra lateral, encabezado, barra de abajo, botón de anotar, modales y avisos). `sw.js` v98. La barra de estado se resolvió en el 16b.
    - [x] 16b (lote 237). Inicio 2c en `dashboard_2c.html` con la cuenta de `resumen_mes()`, lo atrasado de meses anteriores aparte, `serie_cuotas()` y «Escuchar mi mes». Con el 2c la barra de estado del iPhone pasa a `default` (la franja protegida no se tocó). `sw.js` v99.
    - [x] 16c (lote 238). Pagos · Este mes en `por_pagar_2c.html`, con las pestañas de Pagos (`_pagos_pestanas.html`) y las cuotas de meses anteriores para pagarlas ahí mismo. `sw.js` v100.
    - [x] 16d (lote 239). Pagos · Cuotas en `deudas_2c.html`: Editar en un panel con `DeudaForm` tal cual, Mes a mes de `serie_cuotas()` con detalle por mes y compras pagadas. `sw.js` v101.
    - 16e. Pagos · Suscripciones y Préstamos. Partido en dos:
      - [x] 16e1 (lote 240). Suscripciones en `suscripciones_2c.html`, con el mismo contexto, formulario y `suscripciones.js`. `sw.js` v102.
      - [x] 16e2 (lote 241). Préstamos dentro de las pestañas de Pagos, con la piel 2c de los componentes `.sec-*`. Su HTML queda igual.
    - [x] 16f (lote 241). Plan (Metas, Plan para tu plata, Estadísticas, Análisis IA) con la piel 2c en `tema-2c.css`. Queda pendiente, si se quiere, una pantalla nueva con su maqueta de escritorio.
    - [x] 16g (lote 241). Perfil, Categorías, Cartola y Anotar desde afuera con la piel 2c. `sw.js` v103. Igual que el 16f, la pantalla nueva queda opcional.
    - [x] 16h (lote 244). Landing con la piel 2c (`landing-2c.css`) detrás de la cookie, con el mismo HTML. `sw.js` v106.
    - [x] 16i (cerrado con el paso 18: el acceso 2c es el único y `test_login_esfera.py` se borró en el lote 276). Entrar y las demás pantallas de acceso, con `test_auth_diseno.py` y `test_login_esfera.py` al día.

## Reglas de cada lote

- Una carpeta `entrega-loteNNN-…/` con los archivos completos y un `LEER-PRIMERO.md`: qué cambia, cómo se comprobó y qué revisar después de desplegar.
- Sin comentarios en el código. Todo en español.
- Subir la versión de `static/js/sw.js` cuando cambia algo de `static/`.
- Antes de mover una regla de CSS, revisar las reglas que quedan entre su lugar viejo y el nuevo (lote 170), y correr la comparación de estilos del lote 171.
- Cada hoja propia nueva va dentro de `@layer app`; `test_capas_css.py` lo exige.
