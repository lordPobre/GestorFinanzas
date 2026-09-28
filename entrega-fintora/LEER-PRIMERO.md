# Entrega Fintora

Todo en una carpeta:

- `repo/`: código, pruebas, migraciones, configuración y documentación. Se copia encima del repositorio.
- `1-octubre/`: la política 1.3 y el correo de aviso. Se aplica el 1 de octubre, no antes.

Cada archivo de código parte de `main` del 28 de septiembre de 2026.

## 1. Copiar y limpiar

Desde la carpeta del repositorio, con `entrega-fintora` al lado:

```powershell
Copy-Item -Path ..\entrega-fintora\repo\* -Destination . -Recurse -Force
Copy-Item -Path ..\entrega-fintora\repo\.github -Destination . -Recurse -Force
Copy-Item -Path ..\entrega-fintora\repo\.env.example -Destination . -Force
git rm docs/ARQUITECTURA.md docs/DECISION-CIFRADO.md docs/DEUDA-TECNICA.md docs/REVISION-CODIGO-2026-09.md docs/ACTUALIZAR-DJANGO-5.2.md docs/MIGRACION-POSTGRES.md docs/DESPLIEGUE-RAILWAY.md docs/GUIA-PENDIENTES-MANUALES.md DESPLIEGUE-RAILWAY.md
git status --short
```

Se quedan como están: `BRECHAS.md`, `STAGING.md`, `CARTOLAS-COBERTURA.md`, `ESTILOS.md` y las dos auditorías. `RESPALDOS.md` se reemplaza.

En `README.md`, cambia la sección **Documentación** del final por:

```markdown
## Documentación

Todo está en [docs/README.md](docs/README.md): producto, arquitectura, modelo de datos, rutas, cartolas, seguridad, privacidad, frontend, despliegue, operación, pruebas, decisiones, deuda técnica y convenciones.
```

Busca también “DESPLIEGUE-RAILWAY” en el resto del README y cámbialo por `docs/09-INSTALACION-Y-DESPLIEGUE.md`.

## 2. Probar

```powershell
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test
```

Hay dos migraciones nuevas:

- **0116** agrega `Transaccion.suscripcion` y vincula los cobros existentes por su descripción. Si dos suscripciones de una misma persona tienen el mismo nombre, todos los cobros quedan en la primera.
- **0117** crea los `PagoCuota` que faltaban en las compras importadas desde cartolas (el error E2) y recalcula `cuotas_pagadas`. Vincula el movimiento importado cuando hay uno solo que calce.

Revisa a mano la pantalla de suscripciones en el teléfono: el botón nuevo de editar queda a la izquierda del interruptor.

## 3. Subir

```powershell
git add -A
git commit -m "Arreglos de la revisión y documentación completa"
git push
```

El CI corre ahora contra Postgres 18, con usuario y base `fintora`.

## 4. Railway

En cada servicio programado, *Settings → Config-as-code*:

| Servicio | Archivo |
| --- | --- |
| avisos | `/railway/avisos.json` |
| inactivas | `/railway/inactivas.json` |
| avatares | `/railway/avatares.json` |

Antes, compara el comando y el horario de cada JSON con lo que el servicio tiene hoy. Después, redespliega uno y confirma en el log que corre la tarea y termina, sin levantar gunicorn.

## 5. El 1 de octubre: política 1.3

```powershell
Copy-Item -Path ..\entrega-fintora\1-octubre\finanzas\* -Destination .\finanzas\ -Recurse -Force
git add -A
git commit -m "Política de privacidad 1.3"
git push
```

Ese mismo día envía `1-octubre/aviso-politica-1.3.txt`, con `{SITE_URL}` reemplazado por la dirección real. Va a todas las cuentas activas con correo, también a las que apagaron el aviso mensual. La 1.3 rige desde el 8 de octubre.

## PDF

El diseño `Documentacion Fintora` del proyecto ya tiene los cambios. Se abre y se exporta a PDF.

## Qué se arregló

El detalle está en `docs/13-DEUDA-TECNICA-Y-HOJA-DE-RUTA.md`, sección *Resuelto en la entrega de arreglos*: E1 a E8, S1 a S5, C1 a C3, I1 a I4 y D1 a D4. Las pruebas están en `finanzas/tests/test_correcciones.py`.

Quedan D5 a D12. Son mejoras que piden medir antes (tiempos de respuesta, cobertura real, resumen de ruff), sumar infraestructura (una cola) o comparar capturas (el CSS). Siguen en la hoja de ruta del mismo capítulo.
