$ErrorActionPreference = 'Stop'
$raiz = git rev-parse --show-toplevel 2>$null
if (-not $raiz -or -not (Test-Path (Join-Path $raiz 'manage.py'))) {
    Write-Host 'Corre el script desde la carpeta del proyecto (donde está manage.py). No se cambió nada.' -ForegroundColor Yellow
    exit 1
}
Set-Location $raiz

$extensiones = '.py', '.html', '.txt', '.js', '.css', '.json', '.webmanifest', '.md', '.yml', '.yaml', '.toml', '.svg', '.example', '.cfg', '.ini'
$utf8 = New-Object System.Text.UTF8Encoding $false

$archivos = git ls-files --cached --others --exclude-standard | Where-Object {
    $_ -notmatch '(^|/)migrations/' -and
    $_ -notmatch 'renombrar-fintora\.ps1$' -and
    $extensiones -contains [System.IO.Path]::GetExtension($_).ToLower() -and
    (Test-Path -LiteralPath $_)
}

$cambiados = @()
foreach ($a in $archivos) {
    $ruta = (Resolve-Path -LiteralPath $a).Path
    $texto = [System.IO.File]::ReadAllText($ruta, $utf8)
    $nuevo = $texto.Replace('Rekon', 'Fintora').Replace('REKON', 'FINTORA')
    if ($nuevo -cne $texto) {
        [System.IO.File]::WriteAllText($ruta, $nuevo, $utf8)
        $cambiados += [pscustomobject]@{ Archivo = $a; Cambios = ([regex]::Matches($texto, 'Rekon|REKON')).Count }
    }
}

$cambiados | Format-Table -AutoSize
'{0} archivos cambiados, {1} reemplazos' -f $cambiados.Count, ($cambiados | Measure-Object Cambios -Sum).Sum

$quedan = Select-String -LiteralPath $archivos -Pattern 'rekon' -CaseSensitive
if ($quedan) {
    ''
    'Para revisar a mano:'
    $quedan | ForEach-Object { '{0}:{1}: {2}' -f $_.Path.Replace("$raiz\", '').Replace("$raiz/", ''), $_.LineNumber, $_.Line.Trim() }
}
