import os
from flask import Blueprint, request, jsonify
from concurrent.futures import ThreadPoolExecutor

# Importa a "Base de Dados" visual (lista global) do dashboard
from dashboard import DASHBOARD_DATA

# Importa nossos serviços via __init__.py
from services import (
    extrair_metadados,
    limpar_nome_arquivo,
    limpar_pasta,
    processar_download,
    converter_final,
    salvar_aula_md,
    PASTA_TEMP_RAIZ
)

# Cria o Blueprint (um módulo da aplicação Flask)
download_bp = Blueprint('download', __name__)

# Configura o Executor de Threads
# max_workers=3 significa que baixamos no máximo 3 aulas SIMULTANEAMENTE.
# O resto fica na fila esperando uma vaga.
executor = ThreadPoolExecutor(max_workers=3)

# --- 1. A LÓGICA DO TRABALHADOR (WORKER) ---
# Esta função roda em "segundo plano" (background) para não travar o servidor.
def worker_download(url, pasta_destino, nome_arquivo_sugerido, item_dashboard,
                    desc=None, resources=None):
    """
    Executa o ciclo completo de vida de uma aula:
    Preparar -> (baixar vídeo) -> (converter) -> (gravar texto) -> Limpar

    Três casos, todos suportados:
    - vídeo + texto: baixa o .mp4 e grava o .md
    - só vídeo: baixa o .mp4
    - só texto (url vazia): grava apenas o .md
    """

    # Atualiza o status visual para "Baixando"
    item_dashboard['status'] = 'baixando'

    # A. Resolver o Nome do Arquivo
    # Se a extensão não mandou nome, tentamos pegar do título da página (fallback)
    if not nome_arquivo_sugerido and url:
        titulo_extraido, _ = extrair_metadados(url)
        nome_arquivo_sugerido = titulo_extraido

    # Limpa caracteres proibidos (ex: remove "?", "/", ":")
    nome_limpo = limpar_nome_arquivo(nome_arquivo_sugerido)
    item_dashboard['nome'] = nome_limpo  # Atualiza o nome bonitinho no painel

    # Define onde ficarão os arquivos temporários (.ts)
    caminho_pasta_temp = os.path.join(PASTA_TEMP_RAIZ, nome_limpo)

    # B. Função de Callback
    # O downloader chama isso a cada pedacinho baixado para atualizar a barra
    def atualizar_progresso(total=None):
        if total:
            item_dashboard['total'] = total
        else:
            item_dashboard['progresso'] += 1

    # C. Gravar o texto da aula (independe do vídeo; aula só-texto também tem)
    try:
        caminho_md = salvar_aula_md(nome_limpo, pasta_destino, desc, resources)
        if caminho_md:
            item_dashboard['tem_texto'] = True
    except Exception as erro:
        print(f"⚠️  Não foi possível gravar o texto de '{nome_limpo}': "
              f"{type(erro).__name__}: {erro}")

    # D. Baixar o vídeo, se houver
    video_ok = False
    if not url:
        # Aula só de texto: sucesso se o .md foi gravado.
        item_dashboard['total'] = 1
        item_dashboard['progresso'] = 1
        sucesso_operacao = bool(item_dashboard.get('tem_texto'))
        item_dashboard['status'] = 'sucesso' if sucesso_operacao else 'erro'
        return

    _, url_m3u8 = extrair_metadados(url)

    if url_m3u8:
        download_ok = processar_download(
            url_m3u8,
            caminho_pasta_temp,
            nome_limpo,
            pasta_destino,
            atualizar_progresso
        )

        if download_ok:
            item_dashboard['status'] = 'convertendo'
            if converter_final(nome_limpo, pasta_destino, caminho_pasta_temp):
                limpar_pasta(caminho_pasta_temp)
                video_ok = True

    # E. Finalização e Relatório
    if video_ok:
        item_dashboard['status'] = 'sucesso'
        item_dashboard['progresso'] = item_dashboard['total']  # Garante barra 100%
    else:
        item_dashboard['status'] = 'erro'
        # Em caso de erro, limpamos a temp para não deixar lixo corrompido ocupando espaço
        limpar_pasta(caminho_pasta_temp)

# --- 2. DEFINIÇÃO DA ROTA (O RECEPCIONISTA) ---
@download_bp.route('/baixar', methods=['POST'])
def rota_receber_pedido():
    """
    Recebe o JSON vindo da extensão do Chrome.
    Exemplo de JSON: { "url": "...", "folder": "Curso/Modulo1", "filename": "Aula 1" }
    """
    dados_request = request.json

    # Cria o objeto de dados que vai aparecer no Dashboard (Terminal)
    novo_item_dashboard = {
        'nome': dados_request.get('filename', 'Verificando...'),
        'status': 'fila',       # Começa na fila
        'progresso': 0,
        'total': 1,             # Valor provisório até começar
        'url': dados_request.get('url'),
        'folder': dados_request.get('folder')
    }

    # Adiciona na lista global (para o dashboard.py ler)
    DASHBOARD_DATA.append(novo_item_dashboard)

    # Envia para a fila de execução (Thread)
    # O servidor responde "OK" imediatamente, sem esperar o download acabar.
    # desc/resources são opcionais: quando presentes, geram o .md da aula.
    executor.submit(
        worker_download,
        novo_item_dashboard['url'],
        novo_item_dashboard['folder'],
        novo_item_dashboard['nome'],
        novo_item_dashboard,
        dados_request.get('desc'),
        dados_request.get('resources')
    )

    return jsonify({"status": "ok", "mensagem": "Adicionado à fila"})