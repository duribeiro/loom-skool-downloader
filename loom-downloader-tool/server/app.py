import logging
import signal
import sys
import os
import shutil # <--- Usado para verificar se o FFmpeg existe
from flask import Flask
from flask_cors import CORS

from dashboard import iniciar_dashboard
from services import limpar_pasta, PASTA_TEMP_RAIZ
from routes import download_bp

# Configura o Logger do Flask para não poluir o terminal (só mostra erros graves)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
CORS(app) # Permite que a extensão do Chrome fale com este servidor
app.register_blueprint(download_bp)

# --- 1. VERIFICAÇÃO DE REQUISITOS ---
def verificar_ffmpeg():
    """Verifica se o FFmpeg está instalado e acessível no sistema."""
    if shutil.which("ffmpeg") is None:
        print("\n" + "="*50)
        print("❌ ERRO CRÍTICO: FFmpeg não encontrado!")
        print("="*50)
        print("O programa precisa do FFmpeg para converter os vídeos.")
        print("1. Baixe em: https://ffmpeg.org/download.html")
        print("2. Adicione-o às Variáveis de Ambiente (PATH) do Windows.")
        print("="*50 + "\n")
        sys.exit(1) # Encerra o programa com código de erro

# --- 2. FUNÇÃO PARA ENCERRAR COM SEGURANÇA (KILL SWITCH) ---
def fechar_forçado(signum, frame):
    """
    É chamada quando você aperta Ctrl+C.
    Garante que a pasta temporária seja limpa antes de fechar.
    """
    print("\n\n🔴 Encerrando servidor... Limpando arquivos temporários...")
    try:
        limpar_pasta(PASTA_TEMP_RAIZ)
    except:
        pass
    print("👋 Até logo!")
    os._exit(0) # Mata o processo imediatamente

# Registra os sinais de interrupção do sistema
signal.signal(signal.SIGINT, fechar_forçado)
signal.signal(signal.SIGTERM, fechar_forçado)

if __name__ == "__main__":
    # 1. Verifica se tem as ferramentas necessárias
    verificar_ffmpeg()

    # 2. Limpeza ao INICIAR (para apagar lixo de sessões anteriores que travaram)
    print("🧹 Limpando área de trabalho temporária...")
    limpar_pasta(PASTA_TEMP_RAIZ)
    
    # 3. Inicia a interface visual (Dashboard)
    iniciar_dashboard()
    
    # 4. Inicia o servidor Web
    # use_reloader=False é importante para não duplicar o dashboard
    app.run(port=5000, use_reloader=False)