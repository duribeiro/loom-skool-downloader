import logging
import signal
import socket
import sys
import os
import shutil  # <--- Usado para verificar se o FFmpeg existe
from flask import Flask
from flask_cors import CORS

from dashboard import iniciar_dashboard
from services import limpar_pasta, PASTA_TEMP_RAIZ
from routes import download_bp

PORTA = 5000

# Configura o Logger do Flask para não poluir o terminal (só mostra erros graves)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
CORS(app)  # Permite que a extensão do Chrome fale com este servidor
app.register_blueprint(download_bp)


# --- 1. VERIFICAÇÃO DE REQUISITOS ---
def verificar_ffmpeg():
    """Verifica se o FFmpeg está instalado e acessível no sistema."""
    if shutil.which("ffmpeg") is None:
        print("\n" + "=" * 50)
        print("❌ ERRO CRÍTICO: FFmpeg não encontrado!")
        print("=" * 50)
        print("O programa precisa do FFmpeg para converter os vídeos.")
        print("1. Baixe em: https://ffmpeg.org/download.html")
        print("2. Adicione-o às Variáveis de Ambiente (PATH) do Windows.")
        print("=" * 50 + "\n")
        sys.exit(1)  # Encerra o programa com código de erro


def porta_ocupada(porta):
    """
    Diz se JÁ existe algo escutando na porta.

    Sem isso, subir um segundo servidor com o primeiro ainda vivo falhava de
    um jeito obscuro — e você ficava com o processo ANTIGO (código velho)
    atendendo os cliques, achando que tinha reiniciado. Melhor recusar cedo,
    com uma mensagem que diz exatamente o que fazer.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as teste:
        teste.settimeout(1)
        return teste.connect_ex(("127.0.0.1", porta)) == 0


# --- 2. ENCERRAR COM SEGURANÇA ---
_ja_encerrando = False


def encerrar(motivo="sinal recebido"):
    """Limpa a pasta temporária e mata o processo. Idempotente."""
    global _ja_encerrando
    if _ja_encerrando:
        return
    _ja_encerrando = True

    print(f"\n\n🔴 Encerrando servidor ({motivo})... Limpando arquivos temporários...")
    try:
        limpar_pasta(PASTA_TEMP_RAIZ)
    except Exception:
        pass
    print("👋 Até logo!")
    os._exit(0)  # Mata o processo imediatamente, sem deixar zumbi


def _tratar_sinal(signum, frame):
    encerrar(motivo=f"sinal {signal.Signals(signum).name}")


# Registra os sinais de interrupção do sistema
signal.signal(signal.SIGINT, _tratar_sinal)
signal.signal(signal.SIGTERM, _tratar_sinal)


if __name__ == "__main__":
    # 1. Verifica se tem as ferramentas necessárias
    verificar_ffmpeg()

    # 2. Recusa subir se a porta já estiver ocupada (evita o "servidor zumbi")
    if porta_ocupada(PORTA):
        print("\n" + "=" * 50)
        print(f"❌ A porta {PORTA} já está em uso.")
        print("=" * 50)
        print("Provavelmente já existe um servidor rodando (talvez um que")
        print("não morreu de verdade). Feche-o antes de subir outro:")
        print("")
        print("  PowerShell:")
        print(f"    Get-NetTCPConnection -LocalPort {PORTA} -State Listen |")
        print("      ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }")
        print("=" * 50 + "\n")
        sys.exit(1)

    # 3. Limpeza ao INICIAR (apaga lixo de sessões anteriores que travaram)
    print("🧹 Limpando área de trabalho temporária...")
    limpar_pasta(PASTA_TEMP_RAIZ)

    # 4. Inicia a interface visual (Dashboard)
    iniciar_dashboard()

    # 5. Inicia o servidor Web.
    # use_reloader=False é importante para não duplicar o dashboard.
    # O try/except é uma rede de segurança: no Windows o Ctrl+C nem sempre
    # chega como SIGINT ao handler acima — às vezes vira KeyboardInterrupt
    # dentro do app.run(). Os dois caminhos terminam em encerrar().
    try:
        app.run(port=PORTA, use_reloader=False)
    except KeyboardInterrupt:
        encerrar(motivo="Ctrl+C")
    except Exception as erro:
        encerrar(motivo=f"erro fatal: {type(erro).__name__}: {erro}")
