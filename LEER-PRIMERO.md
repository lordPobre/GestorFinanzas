# Lote 79: seguridad, lote C (infraestructura)

Va encima del lote 78, que ya está en `main`. No trae migraciones.

## Qué cambia

- **Limpieza diaria.** El nuevo comando `limpieza_diaria` ejecuta `clearsessions` y borra los contadores de intentos vencidos y las filas de sesiones activas cuya sesión ya no existe. Se programa con `railway/limpieza.json`, todos los días a las 06:30 UTC.
- **Respaldo más liviano.** `pg_dump` guarda la estructura de `django_session`, `cache_finapp` y `finanzas_contador`, pero no sus datos. Las copias ya no llevan sesiones abiertas que alguien pueda reutilizar.
- **defusedxml en producción.** Pasa a `requirements.txt` y openpyxl lo usa solo al abrir los Excel. Si falta, `check --deploy` da error.
- **Cookies `__Host-`.** En producción, la de sesión se llama `__Host-sessionid` y la de CSRF `__Host-csrftoken`. El navegador solo las acepta con HTTPS, sin dominio y en `/`, así que un subdominio no puede pisarlas. **Al subir esto, todos tienen que volver a entrar una vez.**
- **Dominio canónico.** Cualquier visita que llegue por otro nombre (el `*.up.railway.app`, `www.`…) se redirige a `DOMINIO_CANONICO`. Si no está definida, se toma de `SITE_URL`. Los GET usan 301 y el resto 308, que conserva el método. `/salud/` y el healthcheck de Railway quedan fuera. En local y en los tests está apagada.
- **Comprobar `PROXIES_CONFIABLES`.** Nueva página, solo para el personal: `/perfil/diagnostico-ip/`. Muestra qué IP ve la app y, si hay Cloudflare delante, cuántos saltos hay que creer.
- **Gitleaks en el CI.** Un trabajo nuevo, `secretos`, revisa todo el historial en cada push. `.gitleaks.toml` ignora los valores de prueba conocidos.

## Archivos

Nuevos:
- `.gitleaks.toml`
- `railway/limpieza.json`
- `finanzas/comprobaciones.py`
- `finanzas/management/commands/limpieza_diaria.py`
- `finanzas/tests/test_seguridad_79.py`

Modificados (copiar encima):
- `.github/workflows/ci.yml`
- `requirements.txt`
- `core/settings.py`
- `finanzas/apps.py`
- `finanzas/middleware.py`
- `finanzas/urls.py`
- `finanzas/views/sistema.py`
- `finanzas/management/commands/respaldar_postgres.py`

Si tienes `requirements.in` en local, agrégale la línea `defusedxml` para que el próximo `pip-compile` no la quite.

## 1. Copiar
```powershell
Copy-Item -Path .\entrega-seguridad-79\* -Destination . -Recurse -Force
Copy-Item -Path .\entrega-seguridad-79\.g* -Destination . -Recurse -Force
Remove-Item .\entrega-seguridad-79 -Recurse -Force
git status --short
```
La segunda línea copia `.github` y `.gitleaks.toml`: PowerShell no copia con `*` los archivos que empiezan con punto.

## 2. Probar
```powershell
pip install --require-hashes -r requirements.txt
python manage.py test finanzas
python manage.py limpieza_diaria
```

## 3. En Railway, antes de subir
1. **Variables del servicio web:** `DOMINIO_CANONICO=fintora.cl` (o el dominio que uses). Comprueba que esté en `ALLOWED_HOSTS`.
2. **Servicio de limpieza:** New → GitHub Repo → este mismo repositorio. En Settings → Config-as-code pon `/railway/limpieza.json`. Copia las variables del servicio web (por lo menos `DATABASE_URL`, `SECRET_KEY`, `ALLOWED_HOSTS`).
3. **Gitleaks:** no hace falta nada si el repositorio es de tu cuenta personal. Si algún día pasa a una organización, la acción pide la variable `GITLEAKS_LICENSE`.

## 4. Subir
```powershell
git add -A
git commit -m "Seguridad lote C: limpieza diaria, respaldo sin sesiones, defusedxml, cookies __Host-, dominio canonico y gitleaks"
git push
```

## 5. Comprobar en producción
- Vuelve a entrar (las cookies cambian de nombre).
- Abre `https://<tu-app>.up.railway.app/`: tiene que llevarte a `https://fintora.cl/`.
- Abre `/perfil/diagnostico-ip/` con tu cuenta de personal:
  - si `coincide_con_cloudflare` es `false`, pon en Railway `PROXIES_CONFIABLES` con el valor de `proxies_confiables_sugerido` y vuelve a mirar;
  - si no usas Cloudflare, `cf_connecting_ip` sale vacío y basta con que `ip_usada` sea tu IP real.
- En GitHub → Actions, el trabajo `secretos` tiene que salir en verde. Si encuentra algo real, rota esa clave antes de agregarla a la lista de permitidos.
