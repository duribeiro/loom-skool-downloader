#!/usr/bin/env bash
#
# Prepara o ambiente do Loom Downloader com um comando (Linux / macOS).
# Equivalente ao setup.ps1 do Windows.
#
# Uso:  ./setup.sh
#
# É idempotente: rodar várias vezes é seguro e NUNCA destrói um venv existente.

set -euo pipefail

# Âncora tudo na pasta do script, para poder rodar de qualquer diretório
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAMINHO_VENV="$RAIZ/venv"
PYTHON_VENV="$CAMINHO_VENV/bin/python"
REQUIREMENTS="$RAIZ/requirements.txt"

# Cores só quando a saída é um terminal de verdade (não quebra logs/pipes)
if [ -t 1 ]; then
    CIANO='\033[36m'; VERDE='\033[32m'; VERMELHO='\033[31m'; AMARELO='\033[33m'; FIM='\033[0m'
else
    CIANO=''; VERDE=''; VERMELHO=''; AMARELO=''; FIM=''
fi

escrever_passo() { printf "\n${CIANO}=== %s ===${FIM}\n" "$1"; }
escrever_ok()    { printf "  ${VERDE}[OK]${FIM} %s\n" "$1"; }
escrever_erro()  { printf "  ${VERMELHO}[ERRO]${FIM} %s\n" "$1"; }

printf "\nLoom Downloader - Setup\n"

# --- 1. PYTHON ---------------------------------------------------------------
escrever_passo "1/5  Verificando Python"

PYTHON_BIN=""
for candidato in python3 python; do
    if command -v "$candidato" >/dev/null 2>&1; then
        PYTHON_BIN="$candidato"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    escrever_erro "Python nao encontrado no PATH."
    echo "  Debian/Ubuntu:  sudo apt install python3 python3-venv"
    echo "  Fedora:         sudo dnf install python3"
    echo "  macOS:          brew install python"
    exit 1
fi

VERSAO="$("$PYTHON_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if ! "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    escrever_erro "Python $VERSAO encontrado, mas o projeto precisa de 3.10 ou superior."
    exit 1
fi
escrever_ok "Python $VERSAO ($PYTHON_BIN)"

# --- 2. FFMPEG (antes de instalar qualquer coisa) ----------------------------
# Checado agora, e nao no boot do servidor, para falhar cedo e barato.
escrever_passo "2/5  Verificando FFmpeg"

if ! command -v ffmpeg >/dev/null 2>&1; then
    escrever_erro "FFmpeg nao encontrado no PATH."
    echo "  O projeto NAO funciona sem ele: e quem junta os fragmentos em .mp4."
    echo ""
    echo "  Debian/Ubuntu:  sudo apt install ffmpeg"
    echo "  Fedora:         sudo dnf install ffmpeg"
    echo "  Arch:           sudo pacman -S ffmpeg"
    echo "  macOS:          brew install ffmpeg"
    exit 1
fi
escrever_ok "FFmpeg encontrado"

# --- 3. VENV -----------------------------------------------------------------
escrever_passo "3/5  Ambiente virtual"

if [ -d "$CAMINHO_VENV" ]; then
    # Guarda deliberada: um venv existente NUNCA e apagado por este script.
    # Se ele estiver corrompido, apague a mao e rode de novo.
    escrever_ok "venv ja existe - preservado"
else
    echo "  Criando venv..."
    if ! "$PYTHON_BIN" -m venv "$CAMINHO_VENV"; then
        escrever_erro "A criacao do venv falhou."
        echo "  No Debian/Ubuntu pode faltar o pacote:  sudo apt install python3-venv"
        exit 1
    fi
    if [ ! -x "$PYTHON_VENV" ]; then
        escrever_erro "venv criado mas $PYTHON_VENV nao existe."
        exit 1
    fi
    escrever_ok "venv criado"
fi

# --- 4. DEPENDENCIAS ---------------------------------------------------------
escrever_passo "4/5  Instalando dependencias"

if [ ! -f "$REQUIREMENTS" ]; then
    escrever_erro "requirements.txt nao encontrado em $REQUIREMENTS"
    exit 1
fi

"$PYTHON_VENV" -m pip install --quiet --upgrade pip
"$PYTHON_VENV" -m pip install --quiet -r "$REQUIREMENTS"

# Prova real: importar de fato, em vez de confiar no codigo de saida do pip
if ! "$PYTHON_VENV" -c "import flask, flask_cors, requests, rich" 2>/dev/null; then
    escrever_erro "Dependencias instaladas mas nao importaveis."
    exit 1
fi
escrever_ok "flask, flask-cors, requests, rich"

# --- 5. EXTENSAO (passo manual, nao automatizavel) ---------------------------
escrever_passo "5/5  Extensao do Chrome"
echo "  Este passo e manual - o Chrome nao permite automatizar:"
echo ""
echo "    1. Abra:  chrome://extensions"
echo "    2. Ligue o 'Modo desenvolvedor' (canto superior direito)"
echo "    3. Clique em 'Carregar sem compactacao'"
echo "    4. Selecione esta pasta:"
printf "       ${AMARELO}%s${FIM}\n" "$RAIZ/extension"

# --- PRONTO ------------------------------------------------------------------
echo ""
printf '%.0s-' {1..60}; echo ""
printf "${VERDE}Setup concluido.${FIM}\n"
echo ""
echo "Para subir o servidor:"
printf "    ${AMARELO}cd \"%s\"${FIM}\n" "$RAIZ"
printf "    ${AMARELO}./venv/bin/python server/app.py${FIM}\n"
echo ""
echo "Depois, abra uma aula no Skool e clique em 'Baixar Aula'."
printf '%.0s-' {1..60}; echo ""
echo ""
