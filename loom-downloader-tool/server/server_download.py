from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
from loom_downloader_full_clean import extrair_metadados, processar_download, converter_final, limpar_arquivos_temporarios, limpar_nome_arquivo

app = Flask(__name__)
CORS(app)

def tarefa_download_em_background(url_embed, estrutura_pastas, nome_aula_manual):
    print(f"\n📩 Processando: {estrutura_pastas} -> {nome_aula_manual}")
    
    # 1. Extraímos a URL Mestra usando o link do embed
    titulo_detectado, url_mestra = extrair_metadados(url_embed)
    
    # Se a extensão mandou um nome de aula, usamos ele. Se não, usamos o do Loom.
    nome_final = nome_aula_manual if nome_aula_manual else titulo_detectado
    
    if url_mestra:
        if processar_download(url_mestra, nome_final):
            # Passamos a estrutura de pastas (Curso/Modulo) para o conversor
            sucesso = converter_final(nome_final, caminho_relativo=estrutura_pastas)
            if sucesso:
                limpar_arquivos_temporarios()
    else:
        print("❌ Falha ao obter URL Mestra.")

@app.route('/baixar', methods=['POST'])
def receber_pedido():
    dados = request.json
    url = dados.get('url')
    # Recebe os novos dados da extensão
    pasta = dados.get('folder', '') # Ex: "Nome do Curso/Nome do Modulo"
    nome_arquivo = dados.get('filename', '') # Ex: "Nome da Aula"
    
    if not url:
        return jsonify({"status": "erro"}), 400
    
    thread = threading.Thread(target=tarefa_download_em_background, args=(url, pasta, nome_arquivo))
    thread.start()
    
    return jsonify({"status": "sucesso", "mensagem": f"Baixando: {nome_arquivo}"})

if __name__ == "__main__":
    print("🌐 Servidor v2.0 Ativo! (Suporte a Pastas)")
    app.run(port=5000)