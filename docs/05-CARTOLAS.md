# 05 · Importación de cartolas

Esta función permite subir el extracto del banco o de la tarjeta y convertirlo en movimientos, sin pedir la clave del banco. Es la puerta de entrada más cómoda para alguien que recién empieza, y la más delicada, porque procesa un documento con datos sensibles.

## Recorrido

```
/cartola/          el usuario elige el banco (o "detectar") y sube el archivo
  ↓ leer_cartola()    PDF → texto (pypdf) → lector ; CSV/Excel → tabla.py
  ↓ enriquecer()      categoría, cuotas, suscripción, duplicados, traspasos
  ↓ sesión            la cartola leída (no el archivo) queda en la sesión
/cartola/revisar/  tabla editable: qué importar, descripción, categoría, y si es
                   suscripción, compra en cuotas o plata que te deben
  ↓ POST
/cartola/confirmar/  todo en una transacción atómica → se borra de la sesión
```

- **El archivo no se guarda nunca.** Con un tope de 6 MB, Django lo mantiene en memoria. Se lee y se cierra en el `finally` de la vista.
- **Lo que sí se guarda un rato** es el resultado de la lectura (fecha, descripción, monto, tipo de cada fila), en la sesión del usuario, hasta que confirma, descarta o vence la sesión (8 h). Ver el hallazgo C1 en [13 · Deuda técnica](13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md#cumplimiento).
- **Nada entra a la base sin confirmación.** La revisión muestra todo marcado salvo lo que ya existe.

## Qué crea la confirmación

Por cada fila marcada se crea una `Transaccion` pagada, con fecha de pago igual a la fecha del movimiento y `es_cuota=True` si la glosa trae “cuota N de M”. Opcionalmente, según lo que la persona marque:

| Casilla | Crea |
| --- | --- |
| Suscripción | `Suscripcion` (se busca por nombre para no duplicar), con el día de cobro de la fecha, como máximo 28 |
| Compra en cuotas | `Deuda` por las cuotas que faltan (total − actual + 1), empezando en esa fecha. Ver el error E2 |
| Me deben | `Prestamo` a una persona existente o nueva. Si era una cuota, por las cuotas restantes |

## Cómo se lee un PDF

### Topes

`cartolas/base.py` rechaza con un mensaje claro los PDF con clave, los de más de 80 páginas, más de 1,5 millones de caracteres o más de 2000 movimientos. Así una cartola de varios años o un documento que no es una cartola no bloquean un worker.

### Elección del lector

1. Si el usuario eligió un banco, se usa ese lector.
2. Si no, se prueba cada lector registrado con `reconoce(texto)`. Cada uno busca sus pistas (nombre del banco, formato del encabezado).
3. Si ninguno lo reconoce, se prueba el genérico de cuentas y después el genérico de tarjetas de casas comerciales.
4. Si nada funciona, se muestra el error y la **muestra anónima** (ver más abajo).

Los lectores se registran con el decorador `@registrar(clave, nombre)` en el diccionario `BANCOS`. El selector de la pantalla se arma a partir de ese diccionario, separando cuentas y tarjetas (atributo `es_tarjeta`).

### Motor universal de cuentas (`universal.py`)

Sirve para cualquier cartola que traiga una columna de saldo:

1. Toma cada línea con una fecha (`dd/mm/aaaa`, `dd-mm-aa`, `12 ene 2026`, también con meses en inglés) y al menos dos cifras.
2. La última cifra es el saldo. Las una o dos anteriores son las candidatas a monto.
3. Ordena de la más nueva a la más antigua.
4. **Exige coherencia:** en al menos el 85 % de las filas consecutivas, la diferencia de saldos tiene que coincidir con uno de los candidatos. Si no, se niega a leer y pide el PDF para escribirle un lector propio.
5. El **signo** (entró o salió) sale de la diferencia de saldos, no del texto. Por eso no se confunde con cartolas que ponen los cargos en positivo.
6. Las filas que no cuadran quedan marcadas con un aviso, y se suma el descuadre total.
7. Busca el saldo anterior para resolver la fila más antigua. Si no lo encuentra, adivina por palabras (“abono”, “sueldo”, “transferencia de”…) y lo avisa.
8. El número de cuenta se muestra enmascarado (…últimos 4).

El motor está registrado para 19 instituciones, cada una con sus pistas de reconocimiento, más una entrada “Otro banco (intento genérico)” sin pistas.

### Lectores propios

| Archivo | Emisor | Por qué tiene lector propio |
| --- | --- | --- |
| `banco_chile.py` | Banco de Chile | Formato de columnas propio |
| `banco_estado.py` | BancoEstado CuentaRUT | Las filas no traen el año, las descripciones se parten en dos líneas y hay número de operación en la glosa. Cuadra contra los totales que declara el documento |
| `cmr.py` | CMR Falabella | Estado de cuenta de tarjeta: no hay saldo corrido, se cuadra contra el total facturado |
| `retail.py` | Ripley (propio) y un motor para tarjetas de casas comerciales | Mismo principio que CMR |
| `tabla.py` | CSV y Excel de cualquier emisor | Reconoce las columnas por su nombre (ver abajo) |

### CSV y Excel (`tabla.py`)

No depende del banco. Reconoce las columnas por alias: fecha; descripción, detalle, glosa, concepto o comercio; cargo, débito, giro o egreso; abono, crédito, depósito o ingreso; monto, valor o importe; saldo. Cubre tres formas:

- Cargos y abonos en columnas separadas.
- Un monto con signo.
- Un monto sin signo más una columna de saldo, en cuyo caso el signo sale de la cadena de saldos.

## Enriquecimiento (`cartolas/analisis.py`)

| Qué | Cómo |
| --- | --- |
| **Categoría** | Palabras clave de comercios chilenos: supermercados y *delivery* → Comida; bencineras, autopistas, apps de transporte y aerolíneas → Transporte; eléctricas, sanitarias, gas y telecomunicaciones → Servicios; *streaming* → Ocio; SaaS → Tecnología; farmacias, isapres y clínicas → Salud; *retail* y *marketplaces* → Compras; etc. En los ingresos: remuneración → Sueldo, bono o aguinaldo → Bono, transferencia → Transferencia, devolución → Venta |
| **Cuotas** | “cuota 3/12”, “cuotas 3 de 12” o “03/12” al final de la glosa, con un total de 2 a 48. Una cuota sin categoría pasa a Compras |
| **Suscripción probable** | Egresos que no son cuota y cumplen alguna de estas condiciones: empiezan con PAC o PAT, traen una marca recurrente (*streaming*, SaaS, seguros, isapre, gimnasio) o el mismo comercio aparece en 2 o más meses distintos entre los últimos 400 egresos del usuario |
| **Duplicados** | Si la misma combinación de fecha, tipo, monto y descripción ya está en la base, la fila viene desmarcada. Cuenta las repeticiones, así que dos cafés iguales el mismo día no se pierden |
| **Traspasos propios** | “Pago tarjeta”, “traspaso”, “entre cuentas”, “depósito a plazo”, “fondo mutuo”… llevan el aviso “parece plata que moviste entre tus propias cuentas” |

## Muestra anónima

Cuando un PDF no se puede leer, la pantalla muestra las primeras 45 líneas del texto extraído, con los **dígitos cambiados por 9** y las **palabras que no son de estructura cambiadas por X**. Se conservan términos como fecha, saldo, cargo, abono, los nombres de bancos y los meses.

Queda la forma del documento (orden de las columnas, etiquetas, formato de fechas y montos) sin ningún dato personal. Con esa muestra se escribe un lector nuevo sin ver la cartola real. Se guarda en la sesión solo para mostrarla una vez.

## Cobertura por emisor

`docs/CARTOLAS-COBERTURA.md` es la tabla viva. La mantiene quien agrega un lector y se conserva como anexo. Tiene tres estados:

- **Verificado:** el lector se escribió con un documento real y tiene prueba propia.
- **Motor genérico:** cae en el motor universal o en el de tarjetas. Si el formato encaja, lee bien; si no, se niega con un mensaje claro.
- **Sin probar:** está en la lista, pero nadie ha subido todavía un documento de ese emisor.

Hoy están verificados Banco de Chile, BancoEstado CuentaRUT, CMR Falabella y Ripley. Los prepago (Tenpo, MACH, Mercado Pago, Global66, Chek) tienen riesgo alto, porque varios no imprimen el saldo corrido. Para ellos, el CSV del propio emisor es el camino corto.

## Prioridad

Por cantidad de personas que los usan: Santander, BCI y Scotiabank (cuenta corriente y cuenta vista son formatos distintos). Después, el CSV de Tenpo, MACH y Mercado Pago. Luego, las tarjetas Cencosud, La Polar y Hites.

## Cómo agregar un lector

1. Pedir la muestra anónima (o el PDF, si la persona lo ofrece), nunca una cartola sin anonimizar por un canal inseguro.
2. Crear `finanzas/cartolas/<emisor>.py` con una clase decorada con `@registrar('<clave>', '<Nombre visible>')`, con `reconoce(texto)` y `parsear(texto) → Cartola`. Si es una tarjeta, agregar `es_tarjeta = True`.
3. Importarlo en `cartolas/__init__.py`.
4. Si el documento trae saldo, preferir `resolver_signos()` de `base.py`: el signo por cadena de saldos es lo que da garantías.
5. Escribir la prueba con texto de ejemplo inventado que imite la forma de la muestra, como `test_cartola_cuentarut.py`.
6. Actualizar `docs/CARTOLAS-COBERTURA.md`.
