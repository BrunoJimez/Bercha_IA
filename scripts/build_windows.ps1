$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildEnvironment = Join-Path $ProjectRoot ".build-venv"
$OutputDirectory = Join-Path $ProjectRoot "dist"
$ExecutablePath = Join-Path $OutputDirectory "Bercha-LivreNexo.exe"

if (Test-Path $ExecutablePath) {
    $ResolvedExecutable = (Resolve-Path $ExecutablePath).Path
    $RunningBuild = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $ResolvedExecutable }
    if ($RunningBuild) {
        throw "Feche o Bercha LivreNexo antes de recompilar: $ResolvedExecutable"
    }
}

if (-not (Test-Path $BuildEnvironment)) {
    python -m venv $BuildEnvironment
}

$PythonExecutable = Join-Path $BuildEnvironment "Scripts\python.exe"
& $PythonExecutable -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar o pip." }
& $PythonExecutable -m pip install -e "$ProjectRoot[dev,pdf]"
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependências de build." }
& $PythonExecutable -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "Bercha-LivreNexo" `
    --paths (Join-Path $ProjectRoot "src") `
    --distpath $OutputDirectory `
    (Join-Path $ProjectRoot "scripts\gui_launcher.py")
if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar o executável com PyInstaller." }

Write-Host "Executável criado em $ExecutablePath"
