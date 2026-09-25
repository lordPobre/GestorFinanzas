# Cobertura de cartolas

Estado de cada formato que el selector de "Importar cartola" ofrece.
Tres estados posibles:

- **Verificado** — el lector se escribió mirando un documento real de ese
  emisor y tiene test propio.
- **Motor genérico** — no tiene lector propio: cae en el motor universal
  (cuentas, por cadena de saldos) o en el de tarjetas (por total facturado).
  Si el formato encaja, lee bien; si no, se niega con mensaje claro. Nunca
  entrega movimientos que no pueda verificar.
- **Sin probar** — está en la lista por nombre, pero nadie ha subido todavía
  un documento de ese emisor.

## Cartolas de cuenta

| Emisor | Lector | Estado |
|---|---|---|
| Banco de Chile | `banco_chile.py` | Verificado |
| BancoEstado CuentaRUT | `banco_estado.py` | Verificado |
| BancoEstado (otras cuentas) | `universal.py` | Sin probar |
| Banco Santander | `universal.py` | Sin probar |
| Banco BCI | `universal.py` | Sin probar |
| Scotiabank | `universal.py` | Sin probar |
| Banco Itaú | `universal.py` | Sin probar |
| Banco Security | `universal.py` | Sin probar |
| Banco BICE | `universal.py` | Sin probar |
| Banco Consorcio | `universal.py` | Sin probar |
| Banco Internacional | `universal.py` | Sin probar |
| Banco Falabella | `universal.py` | Sin probar |
| Banco Ripley | `universal.py` | Sin probar |
| Coopeuch | `universal.py` | Sin probar |
| BTG Pactual | `universal.py` | Sin probar |
| Tenpo | `universal.py` | Sin probar · riesgo alto |
| MACH | `universal.py` | Sin probar · riesgo alto |
| Mercado Pago | `universal.py` | Sin probar · riesgo alto |
| Global66 | `universal.py` | Sin probar · riesgo alto |
| Chek / Copec Pay | `universal.py` | Sin probar · riesgo alto |
| Caja Los Héroes | `universal.py` | Sin probar |
| Cartola genérica | `generico.py` | Último recurso |

"Riesgo alto" son los prepago: varios no imprimen columna de saldo, y sin
saldo corrido el motor universal no tiene de dónde deducir el signo. Para
esos, la exportación CSV del propio emisor es el camino corto.

## Estados de cuenta de tarjeta

| Emisor | Lector | Estado |
|---|---|---|
| CMR / Banco Falabella | `cmr.py` | Verificado |
| Tarjeta Ripley | `retail.py` (lector propio) | Verificado |
| Tarjeta Cencosud (Paris · Jumbo · Easy) | `retail.py` | Sin probar |
| Tarjeta La Polar | `retail.py` | Sin probar |
| Tarjeta ABCDIN | `retail.py` | Sin probar |
| Tarjeta Hites | `retail.py` | Sin probar |
| Tarjeta Tricot | `retail.py` | Sin probar |
| Tarjeta Corona | `retail.py` | Sin probar |
| Tarjeta Dijon | `retail.py` | Sin probar |
| Tarjeta Johnson | `retail.py` | Sin probar |
| Tarjeta Líder / BancoEstado | `retail.py` | Sin probar |
| Tarjeta Unimarc | `retail.py` | Sin probar |
| Cuenta Entel | `retail.py` | Sin probar |
| Otra tarjeta de casa comercial | `retail.py` | Último recurso |

## Archivos exportados (CSV, Excel)

`tabla.py` no depende del emisor: reconoce las columnas por su nombre. Cubre
cargos/abonos en columnas separadas, monto con signo, y monto sin signo con
columna de saldo. Alias reconocidos: fecha, descripción/detalle/glosa/
concepto/comercio, cargo/débito/giro/egreso, abono/crédito/depósito/ingreso,
monto/valor/importe, saldo.

## Cómo se agrega un formato sin tener el documento

Cuando un archivo no se puede leer, la pantalla de importar muestra la forma
del texto extraído con los datos borrados: los dígitos pasan a 9 y las
palabras que no son parte de la estructura del documento, a X. Queda el orden
de las columnas, las etiquetas y la forma de fechas y montos, y no queda
ningún dato personal. Con eso pegado en el chat se escribe el lector.

## Prioridad pendiente

Por cantidad de gente que los usa: Santander, BCI y Scotiabank (cuenta
corriente y cuenta vista son formatos distintos), luego Tenpo, MACH y
Mercado Pago por CSV, después Cencosud, La Polar y Hites.
