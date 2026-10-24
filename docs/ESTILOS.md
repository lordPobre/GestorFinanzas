# Estilos de Fintora

Dirección: **instrumento cálido**. La app se siente como un aparato de medición hecho a mano: fondo oscuro tibio, superficies tranquilas donde se lee y un solo elemento vivo, la esfera, que dice cómo va el mes.

Esta guía decide cuándo va cada una de las tres estéticas que hoy conviven (vidrio esmerilado, títulos técnicos y esfera orgánica). Una pantalla nueva o un cambio de diseño se revisa contra estas reglas antes de escribir CSS.

## 1. Tres reglas

1. **Mate para leer, vidrio para flotar.** Las listas, tarjetas y formularios van sobre superficies mate. El vidrio (`--vidrio`, `--desenfoque`) queda para lo que flota sobre el contenido: barra de abajo, barra lateral, hoja de Inicio, modales, panel Registrar y el panel de preguntas de la esfera.
2. **Lo técnico solo para lo que se mide.** La letra técnica (Chakra Petch, mayúsculas, esquinas) se usa en títulos de sección (`.sec-titulo`) y en nada más. Las cifras van en Manrope 800 con `font-variant-numeric: tabular-nums`. Los estados vivos (grabando, pensando, hablando) se muestran con movimiento, no con letra técnica.
3. **La esfera es lo único orgánico.** Nada más usa manchas, desenfoques en movimiento ni formas blandas. Si algo necesita llamar la atención, usa color de estado o el ámbar de acción, no otra forma orgánica.

## 2. Color

Los tokens viven en `static/css/finapp.css` y `static/css/tema-vidrio.css` (este último manda).

| Papel | Token | Uso |
|---|---|---|
| Fondo | `--bg` `#151412`, `--bg-elev`, `--surface` | Pantalla, tarjetas mate, campos |
| Líneas | `--line`, `--line-fuerte` | Bordes y separadores |
| Texto | `--text-primary`, `--text-secondary`, `--text-muted`, `--text-tenue` | En ese orden de importancia. `--text-tenue` nunca para texto que haya que leer |
| Acción | `--amber`, `--amber-claro`, `--tinta-ambar` | Botón principal, elemento activo del menú, enlaces. Un solo botón ámbar por vista |
| Estado bien | `--green`, `--green-texto` | Mes sano, al día, te alcanza |
| Estado cerca | `--amarillo`, `--amarillo-tenue` | Cerca del límite, vence pronto |
| Estado mal | `--coral`, `--coral-texto` | Pasaste el límite, atrasado, grabando |
| Apoyo | `--blue`, `--teal` | Solo para distinguir categorías y gráficos |

El ámbar dice «toca aquí» y los colores de estado dicen «así vas». No se mezclan: un botón no es verde porque el mes vaya bien, y un estado no se pinta ámbar.

El color del título y de la esfera sigue el estado del mes (`--titulo` en `titulos.css`, `data-estado` en `salud-esfera.css` e `inicio-esfera.css`). Gris (`neutro`) cuando no hay datos o cuando la esfera no puede responder.

## 3. Tipografía

- **Manrope** para todo: 500 y 600 en texto, 700 en etiquetas y botones, 800 en cifras y títulos de bloque.
- **Chakra Petch** 700 solo en `.sec-titulo` y `.page-title`.
- Cifras grandes con `letter-spacing: -.035em`. Texto largo con `text-wrap: pretty`.
- Tamaño mínimo en el teléfono: 12 px para notas, 14 px para texto que se lee, 44 px de alto para todo lo que se toca.

## 4. Superficies y forma

- Radios: `--r-sm` 12 px (campos, chips cuadrados), `--r-md` 16 px (filas), `--r-lg` 22 px (tarjetas), `--r-xl` 26 px (hojas y paneles). Botones y chips de texto en píldora (`999px`).
- Sombras solo en lo que flota: `--sombra-flota` y `--sombra-modal`. Las tarjetas mate no llevan sombra, llevan borde `--line`.
- `--vidrio-brillo` (el filo claro de arriba) solo sobre vidrio.

## 5. Movimiento

- Curvas: `--ease-out` para entrar y salir, `--ease-spring` solo para algo que se suelta (la hoja de Inicio).
- Duraciones: 150 a 250 ms en respuestas al toque, 300 ms en cambios de pantalla (`transiciones.css`), 450 a 500 ms en la hoja.
- La esfera es lo único que se mueve sin que la toquen: respira quieta, late más rápido al grabar, gira más rápido al pensar y pulsa al hablar.
- Todo movimiento se apaga con `prefers-reduced-motion`.

## 6. La esfera

- Un solo lugar visible por pantalla: grande en Inicio y la tarjeta de salud de la barra lateral en las demás (en escritorio), con el nombre de transición `esfera`.
- Tocarla siempre hace algo con la voz: escuchar el resumen o, desde I2, preguntar.
- La conversación con la esfera (I2) sigue `Esfera Preguntas.dc.html`: teléfono 2a, estados 3a a 3e y escritorio 4a.

## 7. Lo que hoy no cumple esta guía

Quedan anotados para lotes de CSS. No se cambian sin revisar la comparación de estilos del lote 171.

- Tarjetas de listas con `--vidrio` en lugar de superficie mate. Hay que revisar pantalla por pantalla cuáles flotan y cuáles no.
- La animación de luz y esquinas de `.sec-titulo` corre dos ciclos al entrar a cada pantalla. Si molesta junto con la esfera, se deja solo en Inicio.
- `--purple` y `--orange` apuntan al ámbar en `finapp.css`. Se pueden borrar cuando no queden reglas que los usen.
