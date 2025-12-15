import os
from flask import Blueprint, request, jsonify
from concurrent.futures import ThreadPoolExecutor

# Importa a "Base de Dados" visual do dashboard
from dashboard import DASHBOARD_DATA

# Importa nossos serviços via __init__.py
from services import (
    extrair_metadados, 
    limpar_nome_arquivo, 
    limpar_pasta, 
    processar_download, 
    converter_final, 
    PASTA_TEMP_RAIZ
)

# Cria o Blueprint (um pedaço da aplicação)
download_bp = Blueprint('download', __name__)

# Configura o Executor de Threads aqui (3 downloads simultâneos)
executor = ThreadPoolExecutor(max_workers=3)

# --- LÓGICA DO TRABALHADOR (WORKER) ---
def worker(url, pasta_destino, nome_arq, item_data):
    # 1. Atualiza Status Visual
    item_data['status'] = 'baixando'
    
    # 2. Resolver Nome do Arquivo
    if not nome_arq:
        t, _ = extrair_metadados(url)
        nome_arq = t
    
    nome_limpo = limpar_nome_arquivo(nome_arq)
    item_data['nome'] = nome_limpo # Atualiza o nome no painel
    
    # Define caminhos
    pasta_temp = os.path.join(PASTA_TEMP_RAIZ, nome_limpo)
    
    # 3. Callback para atualizar a barra de progresso
    def callback_progresso(total=None):
        if total: 
            item_data['total'] = total
        else: 
            item_data['progresso'] += 1
    
    # 4. Processo de Download
    _, m3u8 = extrair_metadados(url)
    sucesso = False
    
    if m3u8:
        # Tenta baixar
        if processar_download(m3u8, pasta_temp, callback_progresso):
            item_data['status'] = 'convertendo'
            # Tenta converter
            if converter_final(nome_limpo, pasta_destino, pasta_temp):
                limpar_pasta(pasta_temp) # Limpa se der certo
                sucesso = True
    
    # 5. Finalização
    if sucesso:
        item_data['status'] = 'sucesso'
        item_data['progresso'] = item_data['total'] # Garante barra cheia
    else:
        item_data['status'] = 'erro'
        limpar_pasta(pasta_temp) # Limpa para não deixar lixo corrompido

# --- DEFINIÇÃO DA ROTA ---
@download_bp.route('/baixar', methods=['POST'])
def rota_baixar():
    d = request.json
    
    # Cria o objeto que vai aparecer no Dashboard
    novo_item = {
        'nome': d.get('filename', 'Verificando...'),
        'status': 'fila', 
        'progresso': 0, 
        'total': 1,
        'url': d.get('url'),
        'folder': d.get('folder')
    }
    
    # Adiciona na lista global do Dashboard
    DASHBOARD_DATA.append(novo_item)
    
    # Manda para a fila de execução
    executor.submit(
        worker, 
        novo_item['url'], 
        novo_item['folder'], 
        novo_item['nome'], 
        novo_item
    )
    
    return jsonify({"status": "ok"})