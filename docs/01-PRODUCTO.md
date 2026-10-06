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

Se muestra en grande en el inicio. Tres botones cambian lo que dice: **Gastos** (gastos únicos más cuotas del mes, con el desglose de cada parte), **Ingresos** y **Puedes gastar**, que pasa a «Te falta» cuando queda en negativo. Siempre abre en Puedes gastar. Al lado va una lectura de la **salud del mes** (*muy buena*, *buena*, *justa* o *apretada*), con la razón. El detalle del cálculo está en [02 · Arquitectura](02-ARQUITECTURA.md#el-cálculo-del-mes).

## Funciones

| Pantalla | Qué permite |
| --- | --- |
| **Inicio** | La cifra del mes, calendario de cobros, pagos pendientes (cuotas, suscripciones, gastos y cuentas por pagar) con botón de pagar, gráfico de 6 meses, gasto por categoría, avisos (presupuesto, gasto contra el mes anterior, cuotas por vencer, cuándo termina una compra), metas, últimos movimientos y primeros pasos para cuentas nuevas. Navegación entre meses. Desde el día 7, la campana avisa qué categorías van más rápido que tu promedio |
| **Esfera de estado** | En el teléfono, detrás de la hoja de Inicio, Cuotas, Me deben, Suscripciones y Metas. Su color resume la pantalla (verde, amarillo o rojo; gris si no hay datos) y al tocarla una voz lee el resumen. Al entrar, saluda por el nombre y dice si el estado del mes cambió desde la última vez. En el computador, la tarjeta de salud de la barra lateral muestra la esfera con la puntuación |
| **Movimientos** | «Ver todo» muestra el mes completo con lo que entró y salió, agrupado por día. Filtros Todo, Únicos, Cuotas e Ingresos con su cantidad y suma. Tocar abre la edición de ingresos y gastos; deslizar paga o borra. Borrar una cuota anula ese pago |
| **Registrar** | Botón central siempre a mano: gasto o ingreso en dos toques, con teclado de monto y categoría. Un gasto puede quedar “por pagar” |
| **Compras en cuotas** | Se escribe la cuota y la cantidad, no el total. La app deja una cuota en cada mes, marca las atrasadas, paga la más antigua y muestra cuánto falta y cuándo termina |
| **Suscripciones** | Se anotan una vez y se generan solas cada mes. Reconoce unas 40 marcas (Netflix, Spotify, ChatGPT, gimnasio…), detecta suscripciones duplicadas en la misma categoría y muestra lo que se ahorraría al año cancelando una. Sugiere como suscripción los cobros que se repiten cada mes en movimientos y cartolas. Arriba de la lista, «Para ahorrar» agrupa los servicios parecidos y dice cuánto se ahorra al año quedándose con el más barato |
| **Plan para tu plata** | Reparte lo que sobra al mes entre ahorro, deudas y libre. Proyecta el fondo para imprevistos como una cuenta de ahorro con tasa y, desde que se completa, un depósito a plazo renovable. Son estimaciones antes de impuestos. Opcionalmente, una explicación en palabras simples hecha con IA |
| **¿Y si compro en cuotas?** | En el Plan: con el valor de la cuota y cuántas son, muestra 12 barras con lo que quedaría libre cada mes con y sin la compra, y marca el mes más justo. No guarda nada |
| **Me deben** | Préstamos a personas, de pago único o en cuotas, con abonos parciales, montos sugeridos, cuánto falta, en qué cuota va y cuánto paga este mes. Cobro por WhatsApp. En el computador, la lista de personas y el detalle van lado a lado |
| **Metas de ahorro** | Monto, fecha y aportes. Calcula cuánto aportar al mes y avisa si una meta lleva meses sin aportes. Al abrir una meta, un anillo muestra el avance y los chips de aporte rápido dicen hasta dónde llegarías |
| **Categorías** | 12 de gasto y 7 de ingreso fijas, más las propias con color e ícono |
| **Estadísticas** | 12 meses de ingresos y gastos, mejor y peor mes, tasa de ahorro, ranking de categorías contra el mes anterior |
| **Análisis** | Diagnóstico propio: carga de cuotas sobre el ingreso, flujo libre, riesgo de 0 a 100 con sus factores, proyección de la deuda a 7 meses. Opcionalmente, una interpretación en lenguaje natural hecha con IA |
| **Importar cartola** | PDF del banco o de la tarjeta, o CSV/Excel. Lee, categoriza, detecta cuotas, suscripciones, duplicados y traspasos propios, y deja revisar antes de guardar. El archivo no se guarda |
| **Exportar** | Excel con subtotales por mes, CSV, y la descarga completa de los datos en JSON |
| **Perfil** | Datos, foto, moneda (8 opciones), presupuesto, aviso mensual por correo, verificación en dos pasos, Face ID o huella, sesiones abiertas, **actividad de la cuenta** de los últimos 90 días, resumen de las 4 protecciones (contraseña, Face ID, dos pasos, correo confirmado), cambio de correo con confirmación, política aceptada, borrar la cuenta |
| **Recorrido guiado** | Tour por las pantallas reales después de la bienvenida |
| **Encuesta** | NPS y opinión por pantalla, a los 14 días de uso, como máximo una vez cada 6 meses |

Fuera de la cuenta:

| Página | Para qué |
| --- | --- |
| **Landing** (`/`) | Presenta la app a quien llega sin sesión, con preguntas frecuentes, ayuda y un **chat con IA** que responde sobre Fintora y, si no sabe,  El teléfono de la portada recorre cuatro pantallas en loop y una sección presenta la esfera |
| **Privacidad, términos y seguridad** | Públicas, en lenguaje claro. Privacidad y términos van versionados. Seguridad (`/seguridad/`) muestra las notas de SSL Labs y Mozilla Observatory y explica las protecciones |
| **Páginas de error** | 400, 403, 404 y 500 propias, en español y sin datos técnicos |

## Accesos

Usuario y contraseña, **Google**, y **Face ID o huella** (passkeys), que solo se ofrece en celular y tablet. Opcionalmente, **verificación en dos pasos** con una app de autenticación y códigos de respaldo. La sesión vence a las 8 horas sin uso y, en todo caso, a los 7 días. Si alguien entra desde un aparato nuevo, llega un aviso por correo.

## Correos que envía

Confirmación del correo al registrarse, recuperación de contraseña, **aviso mensual** de lo que queda por pagar (el día que la persona elige), aviso de cuenta inactiva a los 12 meses, aviso de acceso desde un aparato nuevo, confirmación y aviso del cambio de correo, y aviso a quien intenta registrarse con un correo que ya tiene cuenta. Los correos HTML usan el diseño oscuro de la app, con 480 px de ancho y la cabecera como imagen adjunta.

## Diferenciales

1. **Las cuotas como ciudadanas de primera.** La mayoría de las apps de presupuesto las tratan como un gasto más. Aquí cada cuota vive en su mes, se paga, se atrasa y se arrastra.
2. **Sin conexión bancaria**, y aun así sin tipear todo: la cartola en PDF resuelve la carga inicial.
3. **Privacidad demostrable**: dentro de la app nada de terceros en el navegador, la IA recibe números y no textos, y se borra todo con un botón. Las páginas públicas solo cargan analítica si se configura y, salvo Plausible, solo con consentimiento. Ver [07 · Privacidad](07-PRIVACIDAD-Y-CUMPLIMIENTO.md).
4. **Hecha para el teléfono** sin pasar por la tienda de apps.
5. **Decidir antes de comprar en cuotas**: el simulador muestra en qué mes no alcanzaría la plata antes de hacer la compra.
6. **Encuentra lo que se olvidó anotar**: detecta suscripciones en los cobros repetidos y avisa cuando una categoría va más rápido que lo normal.

## Estado

- En producción en Railway, abierta al público, con cuentas reales. El simulacro de restauración del 24 de septiembre de 2026 contó **9 usuarios y 64 movimientos**.
- Un solo responsable y titular de todos los derechos: Carlos López Figueroa. Desarrollada con asistencia de Claude (Anthropic).
- 419 pruebas automáticas, CI en cada cambio, monitoreo de errores y de disponibilidad, respaldos diarios verificados.
- Lo que falta corregir está en [13 · Deuda técnica](13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md).

## Costos de operación

| Concepto | Costo |
| --- | --- |
| Railway (web, Postgres y tareas) | Plan Hobby, unos USD 5 al mes de crédito de uso |
| Cloudflare R2 | Plan gratuito con el volumen actual |
| Resend | Plan gratuito con el volumen actual |
| Anthropic | Por uso: 6 interpretaciones por hora por usuario y el chat con un tope diario de 300 llamadas |
| ElevenLabs | La voz de la esfera, un crédito por carácter (un resumen tiene unos 200). El plan gratuito solo admite voces predeterminadas y no permite uso comercial: en producción hace falta un plan de pago |
| Plausible | De pago, solo si se activa `PLAUSIBLE_DOMINIO`. Google Analytics y los píxeles de Meta, TikTok y X no tienen costo |
| Dominio | El de `perseustechnology.dev` para el correo. El dominio propio de la app es aparte |

## Lo que no hace, a propósito

- No mueve dinero, no paga y no se conecta a cuentas bancarias.
- No da asesoría financiera: el análisis es una estimación automática (lo dicen los términos).
- No comparte cuentas entre personas: no hay hogares ni parejas.
- No lleva registro de lo que la persona le debe a otros (solo de lo que le deben a ella) ni de inversiones.
