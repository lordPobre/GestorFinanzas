# 04 · Rutas, vistas y API interna

Todas las rutas están en `finanzas/urls.py`, salvo el panel de administración, que vive en `core/urls.py`. Las vistas están en `finanzas/views/`, un archivo por pantalla o grupo de pantallas.

## Reglas comunes a todas las vistas

- **Sesión.** Toda vista con datos lleva `@login_required(login_url='/login/')`. Las públicas son la landing, el acceso, el registro, la recuperación de contraseña, la verificación de correo, el acceso con Google o Face ID, las páginas legales y la de seguridad, `/sw.js`, `/salud/`, `robots.txt`, `sitemap.xml`, `security.txt` y las dos rutas de ayuda.
- **Propiedad.** Todo objeto se busca con `get_object_or_404(Modelo, pk=..., usuario=request.user)`, o `persona__usuario=request.user` en los préstamos. Pedir el id de otra persona da 404, no 403, para no revelar que existe. `test_vistas.py` lo prueba en todas las pantallas.
- **Solo POST para cambiar.** Pagar, anular, eliminar, aportar, cancelar y confirmar solo actúan con POST. Con GET redirigen sin hacer nada. La protección CSRF de Django está activa en todas.
- **Dos formatos de respuesta.** Si la petición trae `X-Requested-With: XMLHttpRequest`, responde JSON (`{"ok": true|false, "msg": ..., ...}`) para que la pantalla se actualice sin recargar. Si no, deja un mensaje de Django y redirige.
- **Volver a donde estaba.** `comun.redirigir(request, por_defecto)` lee `next` del POST o del GET y lo pasa por `redirecciones.py`, igual que el login, el segundo paso, Google y Face ID. Solo acepta una consulta (`?month=9`), una ruta local (`/cuotas/`; nunca `//otro.sitio` ni `/\otro.sitio`) o el nombre de una URL. Cualquier otra cosa cae en `por_defecto`.
- **Montos escritos a la chilena.** `comun.monto_post` quita los puntos de miles y toma la coma como decimal: `12.500,50` → `12500.50`. Rechaza `NaN`, `Infinity`, el cero, los negativos y lo que pase de 99.999.999,99, y redondea a dos decimales.
- **Pagos sin duplicar.** Pagar una cuota o una suscripción, aportar a una meta y abonar un préstamo corren en una transacción que bloquea la fila (`select_for_update`). Un doble toque no paga dos veces.
- **Contexto compartido.** `comun.contadores(usuario)` agrega a casi todas las pantallas lo que usan el menú y el panel “Registrar”: cuotas activas, préstamos activos, total por cobrar, perfil, formulario de movimiento, categorías de gasto e ingreso, suscripciones sin pagar este mes y la salud financiera del mes (`salud_score`, `salud_label`, `salud_nota`).

## Mapa completo

`L` = pide sesión · `P` = solo POST · `J` = responde JSON si es AJAX · `T` = tiene tope de peticiones.

### Inicio y ayuda (`views/landing.py`, `views/panel.py`)

| Ruta | Nombre | Vista | Notas |
| --- | --- | --- | --- |
| `/` | `dashboard` | `landing.inicio` | Con sesión, el inicio (`panel.dashboard`). Sin sesión, la landing. Sin sesión y con `?fuente=pwa` (la app instalada), el acceso |
| `/ayuda/chat/` | `ayuda_chat` | `landing.ayuda_chat` | P · T 10/h por visitante. Recibe JSON `{"mensajes": [{"rol": "user"|"assistant", "texto": ...}]}` y devuelve `{"ok", "texto"}` o `{"ok", "sin_respuesta": true}` |
| `/inicio/voz/` | `voz_esfera` | `voz.hablar` | L · P · T 40/h. Campos `frase`, `cambio` y `nombre` (textos firmados) y `saludo`. Devuelve `audio/mpeg`; 400 si un texto no trae firma válida, 403 con la IA apagada, 503 si ElevenLabs no responde |
| `/ayuda/contacto/` | `ayuda_contacto` | `landing.ayuda_contacto` | P · T 3/h. Campos `correo`, `mensaje` y `sitio` (trampa para bots). Manda un correo a `legal.CORREO_CONTACTO`. 400 si el correo no es válido, 502 si no sale |

`panel.dashboard` acepta `?year=&month=` para ver otro mes, `?registrar=1` para abrir el panel de registro y `?tour=1` para arrancar el recorrido guiado. Al entrar, primero genera los cobros de suscripciones pendientes. Ver [02 · Arquitectura](02-ARQUITECTURA.md#el-cálculo-del-mes).

### Movimientos y cuentas por pagar (`views/movimientos.py`)

| Ruta | Nombre | Notas |
| --- | --- | --- |
| `/movimientos/nuevo/` | `registrar_transaccion` | L. GET formulario (`?tipo=INGRESO|EGRESO`). POST crea. Con `sin_pagar` o `es_pendiente`, el gasto queda por pagar |
| `/movimientos/nuevo-ingreso/` | `registrar_ingreso` | L. Atajo: redirige a `registrar_transaccion?tipo=INGRESO` |
| `/movimientos/<id>/editar/` | `editar_transaccion` | L |
| `/movimientos/<id>/eliminar/` | `eliminar_transaccion` | L · P |
| `/movimientos/<id>/pagar/` | `pagar_gasto` | L · P · J. Solo gastos únicos (no cuotas) |
| `/movimientos/<id>/anular-pago/` | `anular_pago_gasto` | L · P · J |
| `/cuentas-por-pagar/nueva/` | `crear_gasto_pendiente` | L. Crea el `GastoPendiente` y su egreso sin pagar (`Pendiente: {nombre}`) con la fecha de vencimiento |
| `/cuentas-por-pagar/<id>/pagar/` | `pagar_gasto_pendiente` | L · P · J. Marca el gasto y su movimiento |
| `/cuentas-por-pagar/<id>/anular-pago/` | `anular_gasto_pendiente` | L · P · J |
| `/cuentas-por-pagar/<id>/eliminar/` | `eliminar_gasto_pendiente` | L · P. Borra el gasto y su movimiento |

### Compras en cuotas (`views/cuotas.py`)

| Ruta | Nombre | Notas |
| --- | --- | --- |
| `/cuotas/` | `deudas` | L. Activas (atrasadas primero), saldadas y totales |
| `/cuotas/nueva/` | `crear_deuda` | L. `DeudaForm`: se escribe la cuota, no el total |
| `/cuotas/<id>/editar/` | `editar_deuda` | L |
| `/cuotas/<id>/pagar/` | `pagar_cuota` | L · P · J. `periodo` opcional; por defecto, el pendiente más antiguo. Crea el egreso (`Cuota N/T — acreedor`, `es_cuota=True`, fecha de cobro del mes, `fecha_pago` = hoy) y el `PagoCuota` |
| `/cuotas/<id>/anular-pago/` | `anular_cuota` | L · P · J. `periodo` opcional; por defecto, el último pagado. Borra el egreso y el pago |
| `/cuotas/<id>/eliminar/` | `eliminar_deuda` | L · P. Los egresos de las cuotas ya pagadas se conservan como historial |

### Suscripciones (`views/suscripciones.py`)

| Ruta | Nombre | Notas |
| --- | --- | --- |
| `/suscripciones/` | `suscripciones` | L. Orden: atrasada, pendiente, pagada, pausada. Detecta “duplicadas”: dos o más activas en la misma categoría |
| `/suscripciones/nueva/` | `crear_suscripcion` | L. Día de cobro de 1 a 28. Genera el cobro del mes |
| `/suscripciones/<id>/editar/` | `editar_suscripcion` | L. Nombre, monto, día y categoría. Renombra sus cobros y ajusta el del mes si no está pagado |
| `/suscripciones/<id>/pagar/` | `pagar_servicio` | L · P · J. Crea el `PagoServicio` y marca pagado el egreso del mes |
| `/suscripciones/<id>/anular-pago/` | `anular_pago_servicio` | L · P · J |
| `/suscripciones/<id>/cancelar/` | `cancelar_suscripcion` | L · P. Alterna entre pausar y reactivar |
| `/suscripciones/<id>/eliminar/` | `eliminar_suscripcion` | L · P |
| `/suscripciones/sugerencia/agregar/` | `agregar_sugerencia` | L · P. Crea la suscripción desde una sugerencia y le une los cobros detectados |
| `/suscripciones/sugerencia/descartar/` | `descartar_sugerencia` | L · P. Guarda la clave para no volver a sugerirla |


### Metas (`views/metas.py`)

| Ruta | Nombre | Notas |
| --- | --- | --- |
| `/metas/` | `metas` | L. Aportes de los últimos 6 meses por meta, promedio y meses sin aportar |
| `/metas/nueva/` | `crear_meta` | L |
| `/metas/<id>/aportar/` | `aportar_meta` | L · P · J. Crea un `AporteMeta` y suma al acumulado. No genera movimiento |
| `/metas/<id>/editar/` | `editar_meta` | L |
| `/metas/<id>/eliminar/` | `eliminar_meta` | L · P |

### Préstamos: Me deben y Debo (`views/prestamos.py`)

| Ruta | Nombre | Notas |
| --- | --- | --- |
| `/prestamos/` | `prestamos` | L. `?lado=debo` abre Debo; sin él, Me deben. `?persona=` elige la persona. Por defecto, la que más debe |
| `/prestamos/persona/nueva/` | `crear_persona` | L. Puede crear el primer préstamo en el mismo envío. `lado=LE_DEBO` la crea en Debo; cualquier otro valor, en Me deben |
| `/prestamos/persona/<id>/` | `detalle_persona` | L. Misma plantilla, con la persona fija y la pestaña de su lado |
| `/prestamos/persona/<id>/contacto/` | `editar_contacto` | L · P. Nombre y contacto (WhatsApp) |
| `/prestamos/persona/<id>/eliminar/` | `eliminar_persona` | L · P. Se lleva sus préstamos y abonos |
| `/prestamos/persona/<id>/nuevo/` | `crear_prestamo` | L |
| `/prestamos/<id>/abonar/` | `abonar_prestamo` | L · P · J. Si el abono supera lo pendiente, se recorta. No genera movimiento |
| `/prestamos/<id>/pagar-mes/` | `pagar_mes_prestamo` | L · P. Solo Debo (en Me deben, 404). Abona lo que falta del mes con la nota «Pago del mes» y vuelve al Inicio. Si no falta nada, no abona |
| `/prestamos/<id>/eliminar/` | `eliminar_prestamo` | L · P |

### Categorías, estadísticas y análisis

| Ruta | Nombre | Vista | Notas |
| --- | --- | --- | --- |
| `/categorias/` | `categorias` | `categorias.categorias` | L. Gasto del mes y uso de cada categoría, fija o propia. Estado del tope y promedio de los últimos 3 meses |
| `/categorias/nueva/` | `crear_categoria` | | L · P |
| `/categorias/tope/` | `guardar_tope` | `categorias.guardar_tope` | L · P. `categoria` (de gasto, fija o propia), `monto` y `avisar=1`. Con `quitar`, borra el tope |
| `/categorias/<id>/editar/` | `editar_categoria` | | L · P. Nombre, color e ícono |
| `/categorias/<id>/eliminar/` | `eliminar_categoria` | | L · P. Pasa sus movimientos a `Otros` u `Otros_Ingresos` y borra su tope |
| `/estadisticas/` | `estadisticas` | `estadisticas.estadisticas` | L. Últimos 12 meses, mejor y peor mes, tasa de ahorro y ranking por categoría contra el mes anterior |
| `/analisis/` | `analisis_predictivo` | `analisis.analisis_predictivo` | L. Motor propio y serie de cuotas (6 meses atrás, 6 adelante) |
| `/analisis/plan/` | `plan_plata` | `plan.plan_plata` | L. Reparto, fondo para imprevistos, depósito a plazo y simulador de cuotas |
| `/analisis/plan/ia/` | `plan_ia` | `plan.plan_ia` | L · P · J. Explicación del plan con IA. Respeta `profile.analisis_ia` |
| `/analisis/ia/` | `analisis_ia` | `analisis.analisis_ia` | L · P · J · T 6/h. Respeta `profile.analisis_ia`. Devuelve `{"ok", "ia": {diagnostico, recomendaciones, proyeccion_texto, mensaje_motivacional}}` |

### Cartolas (`views/cartola.py`)

| Ruta | Nombre | Notas |
| --- | --- | --- |
| `/cartola/` | `importar_cartola` | L · T 20/h. GET, el selector de banco. POST sube el archivo (máximo 6 MB) |
| `/cartola/revisar/` | `revisar_cartola` | L. Tabla editable de lo leído |
| `/cartola/confirmar/` | `confirmar_cartola` | L · P. Campos por fila `i`: `sel_i`, `desc_i`, `cat_i`, `sub_i`, `deuda_i`, `deben_i`, `deben_persona_i`, `deben_nombre_i`. Todo en una transacción |
| `/cartola/descartar/` | `descartar_cartola` | L |

El detalle está en [05 · Cartolas](05-CARTOLAS.md).

### Exportación

| Ruta | Nombre | Notas |
| --- | --- | --- |
| `/exportar/` | `exportar_excel` | L. `Fintora_movimientos_AAAA-MM-DD.xlsx` (openpyxl). Si openpyxl no está instalado, entrega el CSV |
| `/exportar/csv/` | `exportar_csv` | L. Separador `;` y UTF-8 con BOM, para que Excel en español lo abra bien |

### Cuenta y perfil (`views/cuenta.py`, `views/passkeys.py`, `google_login.py`)

| Ruta | Nombre | Notas |
| --- | --- | --- |
| `/login/` | `login` | `cuenta.entrar`. Contraseña, con topes. Si hay 2FA, deriva a `/verificar/` |
| `/logout/` | `logout` | `Salir`: cierra la sesión, responde `Clear-Site-Data: "cache"` y redirige a `/login/` |
| `/verificar/` | `verificar_codigo` | Segundo paso: código TOTP o de respaldo, dentro de 5 minutos desde la contraseña |
| `/registro/` | `registro` | T 5/h. Correo obligatorio, más la aceptación de la política. Si el correo ya tiene cuenta, no lo dice: manda un correo a esa dirección (2 al día como máximo) y vuelve al acceso con el mensaje de siempre |
| `/registro/confirmar/<token>/` | `verificar_correo` | T 20/h por IP. Enlace de confirmación, válido 48 h |
| `/recuperar/` | `recuperar` | 3 solicitudes cada 15 min por IP y 3 correos por hora por dirección. Siempre responde lo mismo |
| `/recuperar/<uidb64>/<token>/` | `restablecer` | T 20/h por IP. Válido 1 h. Si la cuenta tiene 2FA, también pide el código |
| `/entrar/google/` | `google_entrar` | Redirige a Google con `state`, `nonce` y PKCE (S256) |
| `/entrar/google/listo/` | `google_listo` | T 15/h. Vuelta desde Google |
| `/entrar/face-id/opciones/` | `passkey_entrar_opciones` | P · T 30/15 min. Desafío WebAuthn |
| `/entrar/face-id/verificar/` | `passkey_entrar_verificar` | P. Bloqueo por IP |
| `/bienvenido/` | `onboarding` | L. Primeros pasos |
| `/bienvenido/completar/` | `completar_onboarding` | L · P. Ingreso, primera compra en cuotas y presupuesto. Luego redirige a `/?tour=1` |
| `/perfil/` | `perfil` | L. POST con `accion`: `perfil`, `password`, `aviso_mensual`, `analisis_ia`, `aceptar_politica`, `aviso_dia` o `recordatorios` (`campo`, una de las cinco opciones `push_*`, y `activar=1`). Cambiar el correo pide la contraseña actual (o el código de la app si la cuenta entra solo con Google) y deja el correo nuevo en `email_pendiente` |
| `/perfil/confirmar-correo/<token>/` | `confirmar_cambio_correo` | Enlace al correo nuevo, válido 48 h. Cambia el correo y cierra las demás sesiones. Un pedido nuevo invalida el anterior |
| `/perfil/mis-datos/` | `mis_datos` | L. JSON con todos los datos de la cuenta |
| `/perfil/eliminar-cuenta/` | `eliminar_cuenta` | L. Hay que escribir ELIMINAR y la contraseña |
| `/perfil/sesiones/` | `sesiones_activas` | L. Cerrar una sesión o todas las demás |
| `/perfil/actividad/` | `actividad_cuenta` | L. Registro de seguridad de la cuenta, 90 días y hasta 150 filas, agrupado por día |
| `/perfil/recordatorios/suscribir/` | `push_suscribir` | L · P. JSON `{endpoint, keys: {p256dh, auth}}` del navegador. Solo servicios de avisos conocidos (Google, Mozilla, Apple, Microsoft) por HTTPS. Si el aparato ya estaba en otra cuenta, pasa a esta. Sin `VAPID_PRIVADA`: 404 |
| `/perfil/recordatorios/quitar/` | `push_quitar` | L · P. Borra el aparato por su `endpoint`, solo si es de la cuenta |
| `/perfil/recordatorios/probar/` | `push_probar` | L · P · T 1 cada 30 s. Aviso de prueba a todos los aparatos de la cuenta |
| `/perfil/dos-pasos/` | `configurar_2fa` | L. `accion`: `activar`, `desactivar` o `regenerar`. Desactivar y regenerar: 5 intentos fallidos cada 15 min |
| `/perfil/face-id/` | `passkeys` | L. Lista y quita dispositivos |
| `/perfil/face-id/opciones/` | `passkey_registro_opciones` | L · P · T 10/h. Pide la contraseña |
| `/perfil/face-id/verificar/` | `passkey_registro_verificar` | L · P |
| `/perfil/reenviar-confirmacion/` | `reenviar_verificacion` | L · P · T 4/h |

### Encuesta (`views/encuesta.py`)

| Ruta | Nombre | Notas |
| --- | --- | --- |
| `/encuesta/` | `encuesta` | L |
| `/encuesta/despues/` | `encuesta_posponer` | L · P. Cookie de 30 días |
| `/encuesta/resultados/` | `encuesta_resultados` | L, solo personal (`is_staff`; si no, 404). `?grupo=todos|nuevos|antiguos`, `?p=` pestaña, `?q=` búsqueda, `?n=` cantidad, `?formato=csv` |

### Sistema

| Ruta | Nombre | Notas |
| --- | --- | --- |
| `/privacidad/`, `/terminos/`, `/seguridad/` | `privacidad`, `terminos`, `seguridad` | Públicas (`legal.py`). Seguridad toma la fecha y los enlaces de `REVISION_SEGURIDAD` e `INFORME_*` |
| `/.well-known/security.txt` | `security_txt` | Contacto para reportar fallas. El vencimiento se renueva solo, 180 días adelante. `/security.txt` responde lo mismo |
| `/robots.txt`, `/sitemap.xml` | `robots_txt`, `sitemap_xml` | Dejan indexar la portada, las legales, entrar y registro |
| `/perfil/diagnostico-ip/` | `diagnostico_ip` | L, solo personal. Qué IP ve la app y cuántos saltos de proxy hay que creer (`PROXIES_CONFIABLES`) |
| `/sw.js` | `service_worker` | Sirve `static/js/sw.js` desde la raíz para que controle todo el sitio. Sin caché |
| `/salud/` | `salud` | Prueba la base y la caché. 200 `{"estado": "ok"}` o 503 `{"estado": "degradado", "partes": {...}}`. Exenta de la redirección a HTTPS: es la que usa Railway para saber si la app está viva |
| `/<ADMIN_URL>/` | admin | Solo existe si `ADMIN_URL` está definida. El login del admin se reemplaza por el de la app: el personal entra; una cuenta sin permiso recibe 404 y queda un evento `admin_denegado`. Una cuenta de personal sin verificación en dos pasos no entra: se la manda a activarla, y se revisa en cada página del admin |

### Páginas de error

`400.html`, `403.html`, `403_csrf.html`, `404.html` y `500.html` están en `finanzas/templates/` y Django las usa solas con `DEBUG` apagado. Heredan de `error_base.html`, que no usa la sesión ni la base, así que la de 500 se muestra aunque la base esté caída.

### Rutas antiguas

Veinticinco rutas del esquema anterior (`nueva-deuda/`, `registrar/`, `meta/aportar/<id>/`, `gasto-pendiente/pagar/<id>/`, etc.) siguen respondiendo con **308**, que conserva el método y la consulta. Así, los accesos directos y los formularios que quedaron abiertos en un teléfono siguen funcionando. La lista está en `RUTAS_ANTIGUAS` y `test_rutas.py` prueba cada una.
