# Índice de `static/css/finapp.css`

Las secciones van en este orden dentro del archivo. Para saltar a una, busca con Ctrl+F el selector de la segunda columna.

| Sección | Empieza en |
|---|---|
| Variables y tema | `:root` |
| Base: elementos HTML, enlaces, títulos | `*` |
| Tipografía y textos de apoyo | `.display` |
| Superficies: glass, card, brillo al pasar | `.glass` |
| Tarjetas de saldo y aviso de atraso | `.balance-card` |
| Botones | `.btn` |
| Filas deslizables de pagos | `.swipe` |
| Listas de filas | `.row-list` |
| Carrusel del inicio | `.saludo-card` |
| Movimientos deslizables | `.mov-list` |
| Metas: filas, aportes y tarjeta | `.metas-lista` |
| Mini tarjetas | `.mini-cards` |
| Tarjetas de color de las cabeceras | `.tarjetas-color` |
| Insignias, barras de progreso y pagos | `.badge` |
| Formularios: campos, selectores, chips, interruptores | `.field` |
| Vista previa, vacíos y cabeceras de sección | `.preview-box` |
| Grillas de contenido | `.grid-metrics` |
| Estructura: barra lateral, principal, barra superior | `.layout` |
| Calendario | `.cal-head` |
| Modales, hojas y confirmación | `.modal-overlay` |
| Teclado de monto y métricas | `.amount-display` |
| Análisis y flujo | `.flujo-panel` |
| Perfil y foto | `.perfil-cab` |
| Navegación de mes | `.mes-nav` |
| Registro rápido | `.registro-overlay` |
| Avisos emergentes | `.toast-container` |
| Cuotas: panel y detalle | `.deuda-panel` |
| Suscripciones | `.subs-cabecera` |
| Foco visible y pantallas táctiles | `summary` |
| Barra inferior, botón flotante y ajustes generales para teléfono | `.bottomnav` |
| Análisis con IA | `.ia-head` |
| Préstamos | `.prestamo-card` |
| Tarjetas de cuota y filas de pago | `.deuda-card` |
| Recorrido guiado | `.tour-capa` |
| Primeros pasos | `.pasos-card` |
| Importar cartola | `.cartola-layout` |
| Encuesta y resultados | `.aviso-encuesta` |
| Acceso, registro y recuperar contraseña | `.auth` |
| Páginas legales | `.legal` |
| Bienvenida | `.ob-pagina` |
| Clases reutilizables del lote 6 | `.tramo-pagado` |
| Acceso en el teléfono (lote 8) | `.auth-ventaja-icono` |

Los estilos nuevos van en la sección de su pantalla, no al final del archivo.

Cada pantalla tiene sus ajustes de teléfono en un `@media (max-width: 720px)` al final de su propia sección. Desde el lote 170 eso vale para el saludo, los movimientos, las metas, las cuotas y las suscripciones. La sección de la barra inferior guarda solo lo general: barra lateral, márgenes de `.main`, formularios, la barra inferior, el botón flotante y los títulos.

Antes de mover una regla dentro del archivo hay que revisar las reglas que quedan entre su lugar viejo y el nuevo. Si alguna pone la misma propiedad, con la misma especificidad, sobre el mismo elemento, cambia cuál gana.

Todo el archivo va dentro de `@layer app` (lote 169).
