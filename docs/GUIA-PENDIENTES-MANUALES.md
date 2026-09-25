# Pendientes manuales, paso a paso

Lo que no se resuelve con código: se hace en el panel de cada proveedor. Van
en orden; cada punto dice cuánto toma y cómo saber que quedó bien.

---

## 1. Cerrar el acceso público de las fotos (10 min)

**Solo después de desplegar el lote C.** Si lo haces antes, las fotos dejan
de verse.

1. Despliega el lote C y abre tu perfil. Clic derecho en tu foto → *Copiar
   dirección de la imagen*. Tiene que contener `X-Amz-Signature`.
2. Cloudflare → **R2** → bucket de las fotos → **Settings**.
3. En **Public access**, desactiva el **R2.dev subdomain** y quita el
   **Custom domain** si tenías uno.
4. En Railway, borra la variable `R2_PUBLIC_DOMAIN` de los servicios web,
   `inactivas` y `avatares`. Ya no se usa.

**Cómo saber que quedó:** la foto se sigue viendo en la app, y la dirección
pública antigua (la que empezaba con tu dominio de fotos) devuelve error.

---

## 2. Avisar a los usuarios del cambio de política (15 min, antes del 1 de octubre)

La política dice que los cambios se avisan por correo antes de que entren en
vigencia. Envíalo desde tu correo, con todos los destinatarios en **CCO**.
Las direcciones salen de *Mis datos* del panel o de la base
(`SELECT email FROM auth_user WHERE email <> ''`).

Texto sugerido:

> **Asunto:** Rekon actualiza su política de privacidad
>
> Hola:
>
> El 1 de octubre de 2026 entra en vigencia la versión 1.2 de la política de
> privacidad de Rekon. Los cambios son:
>
> - Puedes entrar con Face ID o huella. Tu cara y tu huella nunca salen de tu
>   teléfono: Rekon solo recibe una firma que confirma que eres tú.
> - Se guarda un registro de seguridad de tu cuenta (accesos, intentos
>   fallidos y cambios de seguridad) durante 12 meses.
> - Se hace una copia de respaldo diaria de la base, que se conserva 30 días
>   en un almacenamiento privado.
> - Tu foto de perfil ahora es privada y se muestra con enlaces que caducan.
> - Las tipografías e íconos se cargan desde nuestro propio servidor, sin
>   pasar por Google ni otros terceros.
>
> La política completa está en https://TU-DOMINIO/privacidad/. La próxima vez
> que entres a la app te pediremos que la aceptes.
>
> Si tienes preguntas, responde este correo.

---

## 3. Acuerdos de tratamiento de datos (DPA) (30 min)

Un DPA es el contrato en que el proveedor se compromete a tratar tus datos
solo para darte el servicio. La ley exige tenerlo con cada encargado.

Por cada proveedor:

1. Entra a su sitio → sección **Legal** (suele estar al pie de página) y busca
   **Data Processing Addendum** o **DPA**.
2. Revisa cómo se acepta. En algunos va incluido en los términos que ya
   aceptaste al crear la cuenta; en otros se firma o se acepta desde el panel.
3. Descarga el PDF y guárdalo en una carpeta `legal/dpa/` fuera del
   repositorio, con la fecha en el nombre.
4. En `docs/REGISTRO-TRATAMIENTOS.md`, tabla **Encargados del tratamiento**,
   cambia *Pendiente de documentar* por *DPA aceptado el AAAA-MM-DD*.

| Proveedor | Dónde buscar |
| --- | --- |
| Railway | Legal → DPA |
| Cloudflare | Legal → Customer DPA (cubre R2) |
| Resend | Legal → DPA |
| Anthropic | Legal → Commercial Terms / DPA (cubre la API) |

Si alguno exige firmarlo aparte y no lo encuentras, escríbeles a soporte
pidiendo "the DPA for my account". Suelen responder en uno o dos días.

---

## 4. Completar `BRECHAS.md` (2 min)

En la tabla **Contactos**, reemplaza *Anotar aquí un teléfono directo* por tu
número. Es lo que se usa el día de un incidente, cuando corren las 72 horas.

---

## 5. SPF, DKIM y DMARC del correo (20 min + espera de DNS)

Sin esto, los correos de recuperación y los avisos caen en spam o se rechazan.

**En Resend:**

1. **Domains** → **Add Domain** → escribe tu dominio.
2. Resend muestra 3 o 4 registros DNS: uno **MX** y uno **TXT** para SPF
   (normalmente en el subdominio `send`), y uno **TXT** para DKIM
   (`resend._domainkey`).

**En tu proveedor de DNS** (donde compraste el dominio o Cloudflare):

3. Crea cada registro exactamente como lo muestra Resend: tipo, nombre y
   valor. Si el panel agrega el dominio solo al nombre, escribe solo la parte
   de adelante (`send`, `resend._domainkey`).
4. Agrega además el de **DMARC**:

| Tipo | Nombre | Valor |
| --- | --- | --- |
| TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:TU-CORREO` |

5. Vuelve a Resend y presiona **Verify**. Puede tardar entre minutos y unas
   horas.

6. En Railway, deja `CORREO_FROM` con una dirección de ese dominio, por
   ejemplo `Rekon <no-responder@tudominio.cl>`.

**Cómo saber que quedó:** pide una recuperación de contraseña a una cuenta de
Gmail. En el correo recibido → *Mostrar original* tienen que aparecer
`SPF: PASS`, `DKIM: PASS` y `DMARC: PASS`.

**Dos o cuatro semanas después**, si los informes de DMARC no muestran
problemas, cambia `p=none` por `p=quarantine`.

---

## 6. Monitor externo de `/salud/` (10 min)

Sirve para enterarte de una caída antes que tus usuarios.

1. Crea una cuenta gratuita en UptimeRobot o Better Stack.
2. **New monitor** → tipo **Keyword** (o HTTP con palabra clave).
3. URL: `https://TU-DOMINIO/salud/`
4. Palabra clave: `"estado": "ok"`, con la condición *no existe* (en
   UptimeRobot: **Keyword not exists**). Así la alerta salta solo cuando la
   respuesta deja de decir `ok`.
5. Intervalo: 5 minutos.
6. Contacto de alerta: tu correo y, si el plan lo permite, tu teléfono.

**Cómo saber que quedó:** el monitor queda en verde. Para probar la alerta,
pausa el servicio web unos minutos en Railway y revisa que llegue el aviso.

---

## 7. Alertas de Sentry (5 min)

1. Sentry → tu proyecto → **Alerts** → **Create Alert** → **Issues**.
2. Condición: *A new issue is created*.
3. Acción: *Send a notification to* tu correo.
4. Guarda con el nombre `Error nuevo en Rekon`.

**Cómo saber que quedó:** en staging, provoca un error (por ejemplo, abre una
URL que haga fallar una vista) y revisa que llegue el correo en un par de
minutos.

---

## 8. Primer simulacro de restauración (30 min)

Sigue la sección **Simulacro mensual** de `docs/RESPALDOS.md`. En resumen:

1. Descarga la copia más reciente del bucket de respaldos.
2. Crea un Postgres nuevo y vacío en Railway.
3. Restaura con `pg_restore --no-owner --no-privileges --dbname "$URL" archivo.dump`.
4. Cuenta usuarios y movimientos y compáralos con producción.
5. Borra la base de prueba y el archivo descargado.
6. Anota la fecha y el resultado en la tabla de `RESPALDOS.md`.

Después, agéndalo en tu calendario para el primer lunes de cada mes.

---

## 9. Fijar las dependencias (5 min)

Desde tu copia local del repositorio:

```bash
pip install pip-tools
pip-compile --generate-hashes --output-file requirements.txt requirements.in
git add requirements.txt
git commit -m "Dependencias fijadas con hashes"
git push
```

**Cómo saber que quedó:** `requirements.txt` tiene líneas con `--hash=sha256:`
y el CI termina en verde.

---

## Resumen

- [x] 1. Fotos privadas en R2
- [x] 2. Correo a los usuarios por la política 1.2 (enviado el 2026-09-24)
- [x] 3. DPA de Railway, Cloudflare, Resend y Anthropic
- [x] 4. Teléfono en `BRECHAS.md`
- [x] 5. SPF, DKIM y DMARC (2026-09-25: `perseustechnology.dev`, SPF/DKIM/DMARC en PASS con Gmail; `p=none`, informes a `soporte@`. Entre el 2026-10-09 y el 2026-10-23 revisar informes, confirmar DKIM de Zoho y pasar a `p=quarantine`)
- [x] 6. Monitor externo (2026-09-25: UptimeRobot, alerta DOWN y UP recibidas por correo)
- [x] 7. Alertas de Sentry
- [x] 8. Simulacro de restauración (2026-09-24: 9 usuarios, 64 movimientos, coincide con producción)
- [x] 9. `requirements.txt` con hashes
