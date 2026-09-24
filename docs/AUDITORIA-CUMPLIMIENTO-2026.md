# Auditoría de cumplimiento y madurez — GestorFinanzas

Revisión de `lordPobre/GestorFinanzas` (`main`, commit `a940fb68`) el 16 de
septiembre de 2026. Complementa `AUDITORIA-SEGURIDAD.md`, que cubrió cuatro
vulnerabilidades concretas y ya están cerradas. Este documento mira lo que
falta para que la app sea un producto que se pueda defender ante un auditor,
un usuario que reclama y un desarrollador nuevo.

Leído en esta revisión: `core/settings.py`, `core/urls.py`, `finanzas/middleware.py`,
`finanzas/seguridad.py`, `finanzas/cifrado.py`, `finanzas/almacenamiento.py`,
`finanzas/forms.py`, `finanzas/ia.py`, `requirements.txt`, `railway.json`,
`build.sh`, el árbol completo del repositorio y el inventario de pruebas.

---

## Veredicto

La seguridad de aplicación está por encima del promedio de un proyecto de
este tamaño: CSP con nonce, Argon2, 2FA, aislamiento por usuario probado con
tests, bloqueo de intentos en caché compartida, cabeceras completas. Lo que
falta no es más código de seguridad.

Lo que falta es **todo lo que rodea al código**: evidencia de cumplimiento
legal, automatización del control de calidad, observabilidad y documentación.
Un auditor de la Ley 21.719 no revisa `settings.py`; pide el registro de
tratamientos, la política de privacidad y el procedimiento de notificación de
brechas. Hoy no existe ninguno de los tres.

| Área | Estado | Comentario |
| --- | --- | --- |
| Seguridad de aplicación | Verde | Sólida. Quedan detalles, no agujeros. |
| Cumplimiento legal (datos personales) | **Rojo** | Sin política, sin registro, sin derechos ARCOP. Vigencia: 1-dic-2026. |
| Observabilidad y operación | **Rojo** | Sin monitoreo, sin alertas, sin health check, logs no persistentes. |
| Proceso de ingeniería | **Rojo** | Sin CI, sin linter, sin README, sin staging. |
| Pruebas | Amarillo | 26 tests buenos, pero solo de lógica de negocio. |
| Arquitectura | Amarillo | `views.py` con 129 KB. Funciona, pero el costo de cambio sube. |
| Accesibilidad | Amarillo | Nunca auditada. |
| Funcionalidad | Amarillo | Falta lo que el usuario pide y lo que la ley obliga a ofrecer. |

---

## A. Cumplimiento legal — lo urgente por calendario

La Ley 21.719 se publicó el 13 de diciembre de 2024 y entra en plena vigencia
el **1 de diciembre de 2026**: quedan diez semanas y media. Reemplaza el marco
de la Ley 19.628, crea la Agencia de Protección de Datos Personales con
facultad de fiscalizar y multar, y llega a 20.000 UTM en las infracciones
gravísimas. Aplica a toda organización que trate datos personales en Chile, sin
umbral de tamaño. El Gobierno ha evaluado postergarla, pero mientras no haya
modificación legal la fecha vigente es esa.

La app trata nombre, correo, foto del rostro, IP, y el historial financiero
completo de personas naturales. Eso es tratamiento de datos personales, y una
parte es información sensible por lo que revela.

### A1. No existe política de privacidad ni términos de uso

No hay ninguna plantilla ni vista que los sirva: el registro pide correo y
contraseña sin declarar qué se hace con los datos, cuánto se guardan, quién
los procesa ni cómo ejercer derechos. Es el incumplimiento más visible y el
más barato de cerrar.

**Qué hacer.** Dos páginas públicas (`/privacidad/`, `/terminos/`), enlazadas
en el pie y en el registro, con: identidad del responsable, finalidades, base
de licitud, categorías de datos, plazos de conservación, subprocesadores con
país, transferencias internacionales, derechos y canal de contacto.

### A2. No hay registro de actividades de tratamiento

La ley fiscaliza evidencia, no intenciones. No existe inventario de qué dato
vive dónde, con qué finalidad y por cuánto tiempo.

**Qué hacer.** Un `docs/REGISTRO-TRATAMIENTOS.md` con una fila por flujo:
registro de usuario, movimientos, cartolas bancarias, foto de perfil, análisis
con IA, correo de avisos, logs de seguridad, respaldos.

### A3. Los derechos ARCOP no tienen dónde ejercerse

- **Acceso / portabilidad:** `exportar.py` genera Excel y CSV de movimientos,
  lo que cubre parte. No hay exportación íntegra del expediente (perfil,
  personas, préstamos, suscripciones, metas, sesiones, 2FA).
- **Supresión:** no hay ninguna vista de eliminar cuenta. Hoy la única forma
  de que un usuario desaparezca es que tú entres a la base. Esto es a la vez
  un incumplimiento y un vacío funcional.
- **Oposición:** el análisis con IA no se puede desactivar por usuario.

**Qué hacer.** Vista `eliminar_cuenta` con reautenticación, confirmación
escrita y borrado en cascada verificado (incluida la foto en R2 —
`limpiar_avatares_huerfanos.py` ya sabe hacer esa parte); un botón "descargar
todos mis datos" que emita un JSON completo; un interruptor de perfil para el
análisis con IA.

### A4. No hay procedimiento de notificación de brechas

La ley obliga a reportar vulneraciones a la Agencia dentro de plazo (72 horas
en el estándar que sigue la norma). Sin monitoreo (ver D1) es probable que una
brecha no se detecte a tiempo, y sin procedimiento escrito no se sabría a
quién avisar ni con qué contenido.

**Qué hacer.** Un runbook de una página: cómo se detecta, quién decide, qué se
comunica, a quién, en cuánto tiempo, y cómo se registra el incidente.

### A5. Subprocesadores y transferencia internacional sin documentar

La app entrega datos a Railway (cómputo y base), Cloudflare R2 (fotos),
Resend o Mailgun (correo) y Anthropic (análisis). Todos fuera de Chile.
Ninguno está declarado ni tiene acuerdo de tratamiento documentado.

**Mitigante real que conviene dejar por escrito:** `ia.py` envía solo
agregados numéricos —ingreso, gasto, cuota, DTI, tendencia— sin nombre,
correo ni descripciones de movimientos. Es una decisión de diseño correcta y
reduce mucho la exposición. Aun así, un perfil financiero es dato personal
cuando se puede asociar a la persona, y la transferencia debe declararse.

### A6. Sin política de conservación ni borrado automático

Nada caduca: ni cuentas abandonadas, ni cartolas importadas, ni logs. La ley
exige plazos definidos.

### A7. Sin responsable designado ni consentimiento registrado

No hay delegado o responsable de protección de datos identificable, ni
evidencia de que el usuario aceptó la política (fecha, versión, IP).

**Qué hacer.** Casilla de aceptación en el registro que guarde versión y
fecha en `UserProfile`.

### A8. Las fotos de perfil se sirven desde un bucket público

`almacenamiento.py` usa `querystring_auth=False` y dominio público. Las URL no
son adivinables por el nombre aleatorio, pero una vez filtrada una URL la
imagen es accesible para siempre y sin autenticación. Son rostros: dato
personal, y para el estándar biométrico, delicado.

**Qué hacer.** Evaluar URL firmadas con vida larga y renovación en servidor, o
servir la foto a través de una vista propia que verifique la sesión.

---

## B. Seguridad técnica — lo que falta sobre una base ya buena

### B1. El cifrado de campos es código muerto

`finanzas/cifrado.py` implementa `TextoCifrado` con Fernet, está bien
razonado, y **no está aplicado a ningún modelo** — el propio `.env.example` lo
reconoce. Las descripciones de movimientos, los nombres de personas y las
notas de abonos están en texto plano. Es la información que más revela:
"préstamo para el abogado del divorcio" es justo el ejemplo que el módulo
usa para justificarse.

**Qué hacer.** Decidir y dejar el resultado por escrito: aplicarlo a los tres
o cuatro campos de texto libre con una migración de datos, o borrar el módulo.
Tener el mecanismo sin conectar es lo peor de las dos opciones: cuesta
mantenimiento y no protege nada.

### B2. Sin escaneo de dependencias ni SBOM

`requirements.txt` usa rangos (`Django>=5.0,<5.2`) sin fijar versiones ni
hashes: dos despliegues del mismo commit pueden instalar versiones distintas.
No hay `pip-audit`, Dependabot ni inventario de componentes. Diez paquetes de
terceros, incluidos `pypdf` y `Pillow`, que procesan archivos que sube el
usuario — históricamente los vectores más ricos de esa lista.

**Qué hacer.** `requirements.lock` con versiones exactas generado desde el
`.txt`, Dependabot activado y `pip-audit` en CI.

### B3. Sin análisis estático de seguridad ni `check --deploy` automático

`python manage.py check --deploy` no corre en ningún momento del despliegue, y
no hay `bandit` ni `semgrep`. Un `SESSION_COOKIE_SECURE` que se caiga en un
refactor no lo avisaría nadie.

### B4. Entrada no confiable sin límites duros

Las cartolas en PDF y Excel se parsean con `pypdf` y `openpyxl`. El tamaño
está topado en 6 MB, lo que es razonable, pero no hay límite de páginas, de
hojas ni de tiempo de parseo: un PDF construido para expandirse puede ocupar
el worker el `--timeout 60` completo. Con dos workers, dos peticiones así
dejan la app sin capacidad.

**Qué hacer.** Topes explícitos de páginas y filas, y rechazo temprano por
tipo real de archivo, no por extensión.

### B5. Gestión de secretos sin rotación

Ocho secretos viven como variables de entorno en el panel del hosting:
`SECRET_KEY`, credenciales de R2, de correo, de
Google, de Anthropic. No hay registro de cuándo se creó cada uno ni
procedimiento de rotación. Las claves de R2 estuvieron publicadas en el
historial de git y **se rotaron en septiembre de 2026**: el historial sigue
conteniendo el token viejo, que ya no sirve para nada. Lo que queda pendiente
es el registro: no hay constancia de cuándo se creó cada secreto ni cada
cuánto toca cambiarlo.

**Qué hacer.** Anotar en `docs/SECRETOS.md` qué secreto existe, dónde vive,
cuándo se rotó y cada cuánto toca. La rotación de R2 ya está hecha.

### B6. Sesiones sin control por parte del usuario

No hay listado de sesiones activas ni forma de cerrar las demás. En una app
con datos financieros y sesión de 8 horas con renovación en cada petición, es
una carencia esperable de auditoría.

### B7. El admin queda fuera de la CSP

`middleware.py` excluye `/admin` por compatibilidad. Correcto como decisión,
pero si el admin se usa, la ruta más sensible es la única sin protección de
política de contenido. Con `ADMIN_URL` vacío en producción el punto
desaparece; conviene dejarlo así por escrito.

### B8. El límite de intentos en 2FA ya existe

Corregido respecto de la primera redacción de este informe: `verificar_codigo`
en `views.py` sí aplica `esta_bloqueado` y `registrar_fallo` con la clave
`2fa:<uid>`, tanto para el código TOTP como para los de respaldo. Lo que falta
es solo una prueba automática que lo fije.

---

## C. Proceso de ingeniería

### C1. No hay integración continua

El repositorio no tiene `.github/workflows`. Las 26 pruebas existen y solo
corren si alguien se acuerda de ejecutarlas. El despliegue de Railway va
directo desde `main`: nada impide desplegar un commit que rompe los tests.

**Qué hacer.** Un workflow que en cada push corra `manage.py test`,
`manage.py check --deploy`, `ruff` y `pip-audit`. Es la mejora con mejor
relación esfuerzo/beneficio de toda esta lista.

### C2. Sin linter, formateador ni pre-commit

No hay `pyproject.toml`, `ruff.toml` ni `setup.cfg`. El estilo se sostiene por
disciplina.

### C3. Sin README

El repositorio no tiene README ni LICENSE. Un desarrollador nuevo —o tú en un
año— no tiene por dónde empezar: no está escrito cómo se levanta el entorno,
qué variables hacen falta (eso vive solo en `.env.example`), cómo se corren
las pruebas ni cómo se despliega. La documentación que existe
(`DESPLIEGUE-RAILWAY.md`, `RESPALDOS.md`, `MIGRACION-POSTGRES.md`,
`AUDITORIA-SEGURIDAD.md`, `ANALISIS-ARQUITECTURA-2026.md`) **no está en el
repositorio**: vive fuera, así que no viaja con el código.

**Qué hacer.** README como puerta de entrada y una carpeta `docs/` en el repo
con lo que hoy está suelto. `cifrado.py` ya cita un `SEGURIDAD-AVANZADA.md`
que no existe en ninguna parte — señal de que la documentación se está
perdiendo.

### C4. Sin entorno de staging

Un solo entorno. Cada cambio se prueba en producción, contra los datos
reales, con los usuarios dentro. Las migraciones corren en `preDeployCommand`
sin ensayo previo y sin plan de reversa escrito.

**Qué hacer.** Un segundo servicio de Railway apuntando a una rama `staging`
con base propia. Es la diferencia entre "creo que funciona" y "lo vi
funcionar".

### C5. Sin versionado ni bitácora de cambios

No hay tags, releases ni CHANGELOG. Ante un incidente no hay forma rápida de
decir qué versión está arriba ni qué cambió respecto a la anterior.

### C6. `views.py` con 129 KB y `models.py` con 64 KB

Funciona y está bien comentado, pero cada cambio obliga a navegar un archivo
enorme, y dos personas no pueden trabajar en él sin chocar. No es urgente ni
es un fallo. Es deuda con interés: el costo de cada cambio futuro sube.

**Qué hacer.** Cuando toque tocar un área, extraerla: `views_deudas.py`,
`views_metas.py`, `views_perfil.py`. Nunca un refactor grande de una vez.

---

## D. Operación

### D1. No hay monitoreo de errores ni alertas

Sin Sentry ni equivalente. Si una vista revienta para un usuario, nadie se
entera salvo que él lo cuente. `ia.py` traga todas las excepciones con
`except Exception: return None`: si la API de Anthropic cambia o la clave
caduca, el análisis deja de funcionar en silencio, indefinidamente.

**Qué hacer.** Sentry en plan gratuito y alerta al correo. Y registrar la
excepción en `ia.py` antes de devolver `None`.

### D2. Sin health check ni monitoreo de disponibilidad

`railway.json` no declara `healthcheckPath` y no hay endpoint de salud. Con
`restartPolicyMaxRetries: 3`, si la app arranca pero queda inservible (base
inalcanzable), el hosting la considera sana.

**Qué hacer.** Una vista `/salud/` que verifique base y caché, declararla en
`railway.json` y apuntar un monitor externo.

### D3. Los registros de seguridad no persisten

Ya está identificado en `settings.py`: sin `LOG_DIR` en un volumen, los logs
solo van a consola y el panel del hosting los rota. No hay historial de
accesos fallidos, y la ley fiscaliza justamente evidencia datada.

### D4. Respaldos sin restauración probada

Existe `respaldar.py` y `RESPALDOS.md`. No hay constancia de que una
restauración se haya ensayado nunca. Un respaldo no verificado no es un
respaldo. Además, el cron del plan Hobby está limitado a una ejecución diaria,
que es también el techo del aviso mensual por correo.

**Qué hacer.** Restaurar el último respaldo en el entorno de staging y anotar
la fecha y el resultado. Repetir cada trimestre.

### D5. Sin objetivos de servicio definidos

No hay RPO ni RTO escritos: cuánto dato es aceptable perder y en cuánto tiempo
hay que estar de vuelta. Sin eso no se puede evaluar si un respaldo diario
basta.

---

## E. Funcionalidad

### E1. El servidor rechaza la fecha futura que acabas de pedir

`TransaccionForm.clean_fecha` lanza un error de validación para cualquier
fecha posterior a hoy. El campo de fecha que ahora aparece en el panel de
registro permite elegir el próximo mes, pero **al guardar el formulario lo
rechaza**: "No puedes anotar un movimiento con fecha futura".

La restricción se puso por una razón buena, que el comentario explica: un
gasto futuro descuadra "lo que te queda este mes". Pero un ingreso ya
calculado del mes siguiente es un caso legítimo, y es exactamente el que
pediste.

**Qué hacer.** Permitir fecha futura cuando `tipo == 'INGRESO'` y revisar que
los cálculos del mes filtren por rango de mes en lugar de acumular todo lo
anterior. Requiere verificar `resumen_mes` en `views.py` antes de tocar la
validación.

### E2. Sin eliminación de cuenta ni exportación íntegra

Ya está en A3. Es a la vez obligación legal y función que los usuarios
esperan.

### E3. Sin verificación del correo al registrarse

No hay evidencia de doble opt-in. Un correo no verificado significa que el
aviso mensual puede ir a una dirección ajena, y que la recuperación de
contraseña apunta a un buzón que no se sabe de quién es.

### E4. Accesibilidad nunca auditada

`USE_I18N` está activo pero no hay archivos de traducción, así que el idioma
está fijado en el código. Y no hay constancia de revisión WCAG: contraste en
tema oscuro, foco visible al navegar con teclado, etiquetas de los botones de
icono, área táctil mínima. Para una app que usa mucho color como señal
—verde ingreso, coral gasto, ámbar aviso— el contraste y la redundancia del
color merecen una pasada.

---

## Lo que está bien y no hay que tocar

Para no gastar esfuerzo donde ya está resuelto:

- CSP con nonce por respuesta, `frame-ancestors 'none'`, `form-action 'self'`,
  `Permissions-Policy` restrictiva. Mejor que la mayoría de apps Django.
- Argon2 como hasher principal, validadores de contraseña con mínimo 8,
  `PASSWORD_RESET_TIMEOUT` bajado a una hora con criterio explícito.
- Cabeceras de producción completas: HSTS con preload, redirección SSL,
  cookies seguras, `nosniff`, `X-Frame-Options`, COOP, referrer policy.
- `SECRET_KEY` sin valor por defecto en producción, con guardia al final del
  archivo y excepción razonada para `collectstatic`.
- Aislamiento por usuario con tests que lo prueban, incluida la no filtración
  por redirección.
- Lectura correcta de `X-Forwarded-For` contando desde el final según
  `PROXIES_CONFIABLES`.
- Caché en base de datos en producción, para que los contadores de bloqueo
  signifiquen lo que dicen con varios workers.
- `ADMIN_URL` configurable y desactivable.
- `obtener_almacen()` como callable, que evita que las credenciales vuelvan a
  filtrarse a una migración.
- La IA recibe solo agregados numéricos, sin texto libre ni identificadores.
- Tests de rendimiento que verifican que el prefetch evita consultas N+1.

---

## Plan sugerido

Ordenado por riesgo y por lo que desbloquea, no por dificultad.

### Semanas 1–2

| Qué | Por qué ahora | Esfuerzo |
| --- | --- | --- |
| ~~Confirmar rotación de las claves de R2~~ | Hecho en septiembre de 2026 | — |
| CI con tests, `check --deploy`, `ruff`, `pip-audit` | Todo lo demás se apoya en esto | 1 día |
| Sentry + alerta, y log en `ia.py` | Hoy los fallos son invisibles | 3 h |
| Vista `/salud/` + `healthcheckPath` | Reinicios que hoy no ocurren | 2 h |
| Arreglar E1 (fecha futura para ingresos) | Función entregada a medias | 3 h |
| README + `docs/` en el repositorio | La documentación no viaja con el código | 4 h |

### Semanas 3–6

| Qué | Esfuerzo |
| --- | --- |
| Política de privacidad y términos, enlazados y aceptados en el registro | 3 días |
| Eliminar cuenta + exportar todos mis datos | 3 días |
| Registro de actividades de tratamiento y lista de subprocesadores | 1 día |
| Runbook de notificación de brechas | 4 h |
| Límite de intentos en 2FA y códigos de respaldo, con test | 4 h |
| Restaurar un respaldo en staging y dejarlo anotado | 4 h |

### Semanas 7–10

| Qué | Esfuerzo |
| --- | --- |
| Entorno de staging con base propia | 1 día |
| Decidir el destino de `TextoCifrado` y ejecutarlo | 2 días |
| Topes de páginas y filas al parsear cartolas | 1 día |
| Política de conservación y borrado de cuentas inactivas | 1 día |
| Verificación de correo al registrarse | 1 día |
| Revisión de accesibilidad y corrección de contraste y foco | 2 días |
| Sesiones activas visibles y cierre remoto | 1 día |

### Continuo

Extraer un módulo de `views.py` cada vez que se toque un área. Volumen para
los logs de seguridad cuando el plan del hosting lo permita. Repetir la prueba
de restauración cada trimestre.

---

## Una observación de jefe de proyecto

El proyecto tiene un patrón claro: las decisiones técnicas están bien
razonadas y documentadas en comentarios extensos dentro del código, y casi
nada de eso existe como artefacto consultable. El razonamiento sobre por qué
no se cifran los montos es de nivel profesional, y está enterrado en el
docstring de un módulo que no se usa. La consecuencia práctica es que el
conocimiento del sistema vive en una sola cabeza y en comentarios dispersos:
si mañana entra alguien más, o si pasan seis meses, ese razonamiento no está
disponible.

Sacar la documentación al repositorio y automatizar las verificaciones no hace
la app más segura de inmediato. Hace que siga siéndolo el mes que viene.
