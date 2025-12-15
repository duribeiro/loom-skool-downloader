from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
from loom_downloader_full_clean import extrair_metadados, processar_download, converter_final, limpar_arquivos_temporarios

app = Flask(__name__)
CORS(app)

def tarefa_download_em_background(url_embed, nome_curso, nome_aula):
    # Se a extensão não mandar o nome da aula, tenta pegar sozinho
    if not nome_aula:
        titulo_temp, _ = extrair_metadados(url_embed)
        nome_aula = titulo_temp
    
    # Se a extensão não mandar o nome do curso, joga na pasta padrão
    caminho_pasta = nome_curso if nome_curso else "Downloads Loom"

    print(f"\n📩 Processando: {caminho_pasta} -> {nome_aula}.mp4")
    
    # Extrai URL Mestra real
    _, url_mestra = extrair_metadados(url_embed)
    
    if url_mestra:
        # 1. Baixa os pedacinhos .ts
        if processar_download(url_mestra, nome_aula):
            # 2. Junta tudo num MP4 dentro da pasta do curso
            # O parâmetro 'caminho_relativo' vai criar a pasta com o nome do curso
            sucesso = converter_final(nome_aula, caminho_relativo=caminho_pasta)
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