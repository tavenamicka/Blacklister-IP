# Génère dist/BlacklisterIP.exe (portable, un seul fichier)
param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($Clean) {
    Remove-Item -Recurse -Force build, dist, __pycache__, app/_build_info.py -ErrorAction SilentlyContinue
}

# Version/date affichées dans "A propos" (cf. app/app_info.py) : figées ici au moment du build,
# PyInstaller embarque app/_build_info.py comme un module Python normal (pas besoin de --add-data).
$version = (git describe --tags --always --dirty 2>$null)
if (-not $version) { $version = "dev" }
$buildDate = Get-Date -Format "yyyy-MM-dd"
Set-Content -Path "app/_build_info.py" -Encoding utf8 -Value @"
VERSION = "$version"
BUILD_DATE = "$buildDate"
"@

pyinstaller `
    --onefile `
    --windowed `
    --name BlacklisterIP `
    --collect-data customtkinter `
    --paths app `
    app/main.py

Write-Host "`nExecutable genere : dist/BlacklisterIP.exe" -ForegroundColor Green
Write-Host "Copiez dist/BlacklisterIP.exe (et son dossier 'data' cree au premier lancement) pour le rendre portable." -ForegroundColor Green
