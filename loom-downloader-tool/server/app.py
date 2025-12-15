import logging
import signal # <--- NOVO
import sys    # <--- NOVO
import os
from flask import Flask
from flask_cors import CORS

from dashboard import iniciar_dashboard
from services import limpar_pasta, PASTA_TEMP_RAIZ
from routes import download_bp

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
CORS(app)
app.register_blueprint(download_bp)

# --- FUNÇÃO PARA MATAR O SERVIDOR NA MARRA ---
def fechar_forçado(signum, frame):
    print("\n\n🔴 Encerrando forçadamente... Limpando temporários...")
    limpar_pasta(PASTA_TEMP_RAIZ) # Tenta limpar antes de morrer
    os._exit(0) # Mata o processo imediatamente (Kill switch)

# Registra o sinal de Ctrl+C
signal.signal(signal.SIGINT, fechar_forçado)
signal.signal(signal.SIGTERM, fechar_forçado)

if __name__ == "__main__":
    # Limpeza ao INICIAR (para apagar lixo da vez passada)
    limpar_pasta(PASTA_TEMP_RAIZ)
    
    iniciar_dashboard()
    app.run(port=5000) 