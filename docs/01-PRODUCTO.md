# 01 · Producto

## Qué es

**Fintora** es una aplicación web de finanzas personales para Chile, instalable en el teléfono. Responde una pregunta: **¿cuánto puedo gastar este mes?** Para eso lleva en un solo lugar lo que entra, lo que sale y lo que ya está comprometido: las cuotas, las suscripciones y las cuentas por pagar.

- **Gratis.** No hay plan de pago.
- **No se conecta al banco** y nunca pide su clave. Todo lo anota o lo sube la persona.
- **En español de Chile**, con pesos sin decimales, cuotas y cartolas de bancos y casas comerciales locales.

## Para quién

Personas que pagan en cuotas (lo habitual en Chile con tarjetas de *retail*), tienen varias suscripciones, prestan plata a conocidos y hoy lo llevan en una planilla, en notas o en la cabeza. El problema que resuelve es que el saldo de la cuenta miente: no descuenta la cuota que se cobra el 15 ni la suscripción del 20.

## La cifra

```
Libre = Entró − Gastos − Cuotas del mes − Cuotas atrasadas
```

Se muestra en el inicio con cuánto queda **por día** hasta fin de mes y una lectura de la **salud del mes** (*muy buena*, *buena*, *justa* o *apretada*), con la razón. El detalle del cálculo está en [02 · Arquitectura](02-ARQUITECTURA.md#el-cálculo-del-mes).

## Funciones

| Pantalla | Qué permite |
| --- | --- |
| **Inicio** | La cifra del mes, calendario de cobros, pagos pendientes (cuotas, suscripciones, gastos y cuentas por pagar) con botón de pagar, gráfico de 6 meses, gasto por categoría, avisos (presupuesto, gasto contra el mes anterior, cuotas por vencer, cuándo termina una compra), metas, últimos movimientos y primeros pasos para cuentas nuevas. Navegación entre meses |
| **Registrar** | Botón central siempre a mano: gasto o ingreso en dos toques, con teclado de monto y categoría. Un gasto puede quedar “por pagar” |
| **Compras en cuotas** | Se escribe la cuota y la cantidad, no el total. La app deja una cuota en cada mes, marca las atrasadas, paga la más antigua y muestra cuánto falta y cuándo termina |
| **Suscripciones** | Se anotan una vez y se generan solas cada mes. Reconoce unas 40 marcas (Netflix, Spotify, ChatGPT, gimnasio…), detecta suscripciones duplicadas en la misma categoría y muestra lo que se ahorraría al año cancelando una |
| **Me deben** | Préstamos a personas, de pago único o en cuotas, con abonos parciales, montos sugeridos y cuánto falta |
| **Metas de ahorro** | Monto, fecha y aportes. Calcula cuánto aportar al mes y avisa si una meta lleva meses sin aportes |
| **Categorías** | 12 de gasto y 7 de ingreso fijas, más las propias con color e ícono |
| **Estadísticas** | 12 meses de ingresos y gastos, mejor y peor mes, tasa de ahorro, ranking de categorías contra el mes anterior |
| **Análisis** | Diagnóstico propio: carga de cuotas sobre el ingreso, flujo libre, riesgo de 0 a 100 con sus factores, proyección de la deuda a 7 meses. Opcionalmente, una interpretación en lenguaje natural hecha con IA |
| **Importar cartola** | PDF del banco o de la tarjeta, o CSV/Excel. Lee, categoriza, detecta cuotas, suscripciones, duplicados y traspasos propios, y deja revisar antes de guardar. El archivo no se guarda |
| **Exportar** | Excel con subtotales por mes, CSV, y la descarga completa de los datos en JSON |
| **Perfil** | Datos, foto, moneda (8 opciones), presupuesto, aviso mensual por correo, verificación en dos pasos, Face ID o huella, sesiones abiertas, política aceptada, borrar la cuenta |
| **Recorrido guiado** | Tour por las pantallas reales después de la bienvenida |
| **Encuesta** | NPS y opinión por pantalla, a los 14 días de uso, como máximo una vez cada 6 meses |

Fuera de la cuenta:

| Página | Para qué |
| --- | --- |
| **Landing** (`/`) | Presenta la app a quien llega sin sesión, con preguntas frecuentes, ayuda y un **chat con IA** que responde sobre Fintora y, si no sabe, ofrece un formulario que llega por correo |
| **Privacidad y términos** | Públicas, en lenguaje claro, versionadas |

## Accesos

Usuario y contraseña, **Google**, y **Face ID o huella** (passkeys). Opcionalmente, **verificación en dos pasos** con una app de autenticación y códigos de respaldo.

## Correos que envía

Confirmación del correo al registrarse, recuperación de contraseña, **aviso mensual** de lo que queda por pagar (el día que la persona elige) y aviso de cuenta inactiva a los 12 meses.

## Diferenciales

1. **Las cuotas como ciudadanas de primera.** La mayoría de las apps de presupuesto las tratan como un gasto más. Aquí cada cuota vive en su mes, se paga, se atrasa y se arrastra.
2. **Sin conexión bancaria**, y aun así sin tipear todo: la cartola en PDF resuelve la carga inicial.
3. **Privacidad demostrable**: nada de terceros en el navegador, la IA recibe números y no textos, y se borra todo con un botón. Ver [07 · Privacidad](07-PRIVACIDAD-Y-CUMPLIMIENTO.md).
4. **Hecha para el teléfono** sin pasar por la tienda de apps.

## Estado

- En producción en Railway, abierta al público, con cuentas reales. El simulacro de restauración del 24 de septiembre de 2026 contó **9 usuarios y 64 movimientos**.
- Un solo desarrollador y responsable.
- 211 pruebas automáticas, CI en cada cambio, monitoreo de errores y de disponibilidad, respaldos diarios verificados.
- Lo que falta corregir está en [13 · Deuda técnica](13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md).

## Costos de operación

| Concepto | Costo |
| --- | --- |
| Railway (web, Postgres y tareas) | Plan Hobby, unos USD 5 al mes de crédito de uso |
| Cloudflare R2 | Plan gratuito con el volumen actual |
| Resend | Plan gratuito con el volumen actual |
| Anthropic | Por uso: 6 interpretaciones por hora por usuario y el chat con un tope diario de 300 llamadas |
| Dominio | El de `perseustechnology.dev` para el correo. El dominio propio de la app es aparte |

## Lo que no hace, a propósito

- No mueve dinero, no paga y no se conecta a cuentas bancarias.
- No da asesoría financiera: el análisis es una estimación automática (lo dicen los términos).
- No comparte cuentas entre personas: no hay hogares ni parejas.
- No lleva registro de lo que la persona le debe a otros (solo de lo que le deben a ella) ni de inversiones.
