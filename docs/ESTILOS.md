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

Los ajustes para teléfono de varias pantallas (barra lateral, suscripciones, movimientos, metas, saludo) están juntos en los `@media (max-width: 1000px)` y `@media (max-width: 720px)` de la sección de la barra inferior, no en la sección de cada pantalla. Moverlos podría cambiar qué regla gana, y no se puede descartar sin revisar cada pantalla. Por eso quedaron ahí.
