<#
.SYNOPSIS
    Prepara o ambiente do Loom Downloader com um comando.

.DESCRIPTION
    Substitui os passos manuais de instalação. É idempotente: rodar várias
    vezes é seguro e NUNCA destrói um venv existente.

.EXAMPLE
    .\setup.ps1
#>

$ErrorActionPreference = "Stop"

# Âncora tudo na pasta do script, para poder rodar de qualquer diretório
$Raiz = $PSScriptRoot
$CaminhoVenv = Join-Path $Raiz "venv"
$PythonVenv = Join-Path $CaminhoVenv "Scripts\python.exe"
$Requirements = Join-Path $Raiz "requirements.txt"

function Escrever-Passo($texto) { Write-Host "`n=== $texto ===" -ForegroundColor Cyan }
function Escrever-Ok($texto)    { Write-Host "  [OK] $texto" -ForegroundColor Green }
function Escrever-Erro($texto)  { Write-Host "  [ERRO] $texto" -ForegroundColor Red }

Write-Host "`nLoom Downloader - Setup" -ForegroundColor White

# --- 1. PYTHON ---------------------------------------------------------------
Escrever-Passo "1/5  Verificando Python"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Escrever-Erro "Python nao encontrado no PATH."
    Write-Host "  Instale em: https://www.python.org/downloads/"
    Write-Host "  IMPORTANTE: marque 'Add Python to PATH' durante a instalacao."
    exit 1
}

$versaoTexto = (& python --version 2>&1) -replace '[^0-9.]', ''
$partes = @($versaoTexto -split '\.' | Select-Object -First 3)
$versao = [version]($partes -join '.')
if ($versao -lt [version]"3.10") {
    Escrever-Erro "Python $versao encontrado, mas o projeto precisa de 3.10 ou superior."
    exit 1
}
Escrever-Ok "Python $versao"

# --- 2. FFMPEG (antes de instalar qualquer coisa) ----------------------------
# Checado agora, e nao no boot do servidor, para falhar cedo e barato.
Escrever-Passo "2/5  Verificando FFmpeg"

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Escrever-Erro "FFmpeg nao encontrado no PATH."
    Write-Host "  O projeto NAO funciona sem ele: e quem junta os fragmentos em .mp4."
    Write-Host ""
    Write-Host "  Instale com um destes:"
    Write-Host "    winget install Gyan.FFmpeg"
    Write-Host "    choco install ffmpeg"
    Write-Host "    https://ffmpeg.org/download.html  (e adicione ao PATH)"
    Write-Host ""
    Write-Host "  Depois FECHE E ABRA o terminal para o PATH atualizar."
    exit 1
}
Escrever-Ok "FFmpeg encontrado"

# --- 3. VENV -----------------------------------------------------------------
Escrever-Passo "3/5  Ambiente virtual"

if (Test-Path $CaminhoVenv) {
    # Guarda deliberada: um venv existente NUNCA e apagado por este script.
    # Se ele estiver corrompido, apague a mao e rode de novo.
    Escrever-Ok "venv ja existe - preservado"
} else {
    Write-Host "  Criando venv..."
    & python -m venv $CaminhoVenv
    if (-not (Test-Path $PythonVenv)) {
        Escrever-Erro "A criacao do venv falhou."
        exit 1
    }
    Escrever-Ok "venv criado"
}

# --- 4. DEPENDENCIAS ---------------------------------------------------------
Escrever-Passo "4/5  Instalando dependencias"

if (-not (Test-Path $Requirements)) {
    Escrever-Erro "requirements.txt nao encontrado em $Requirements"
    exit 1
}

& $PythonVenv -m pip install --quiet --upgrade pip
& $PythonVenv -m pip install --quiet -r $Requirements
if ($LASTEXITCODE -ne 0) {
    Escrever-Erro "Falha ao instalar as dependencias."
    exit 1
}

# Prova real: importar de fato, em vez de confiar no codigo de saida do pip
& $PythonVenv -c "import flask, flask_cors, requests, rich" 2>$null
if ($LASTEXITCODE -ne 0) {
    Escrever-Erro "Dependencias instaladas mas nao importaveis."
    exit 1
}
Escrever-Ok "flask, flask-cors, requests, rich"

# --- 5. EXTENSAO (passo manual, nao automatizavel) ---------------------------
Escrever-Passo "5/5  Extensao do Chrome"
Write-Host "  Este passo e manual - o Chrome nao permite automatizar:"
Write-Host ""
Write-Host "    1. Abra:  chrome://extensions"
Write-Host "    2. Ligue o 'Modo desenvolvedor' (canto superior direito)"
Write-Host "    3. Clique em 'Carregar sem compactacao'"
Write-Host "    4. Selecione esta pasta:"
Write-Host "       $(Join-Path $Raiz 'extension')" -ForegroundColor Yellow

# --- PRONTO ------------------------------------------------------------------
Write-Host ""
Write-Host ("-" * 60)
Write-Host "Setup concluido." -ForegroundColor Green
Write-Host "`nPara subir o servidor:"
Write-Host "    cd `"$Raiz`"" -ForegroundColor Yellow
Write-Host "    .\venv\Scripts\python.exe server\app.py" -ForegroundColor Yellow
Write-Host "`nDepois, abra uma aula no Skool e clique em 'Baixar Aula'."
Write-Host ("-" * 60)
Write-Host ""
