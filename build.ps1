# Génère dist/BlacklisterIP.exe (portable, un seul fichier)
param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($Clean) {
    Remove-Item -Recurse -Force build, dist, __pycache__ -ErrorAction SilentlyContinue
}

pyinstaller `
    --onefile `
    --windowed `
    --name BlacklisterIP `
    --collect-data customtkinter `
    --paths app `
    app/main.py

Write-Host "`nExecutable genere : dist/BlacklisterIP.exe" -ForegroundColor Green
Write-Host "Copiez dist/BlacklisterIP.exe (et son dossier 'data' cree au premier lancement) pour le rendre portable." -ForegroundColor Green
