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
    montar_markdown,
    PASTA_OUTPUT,
    baixar_youtube,
    eh_url_youtube,
    titulo_do_youtube,
    canal_do_youtube,
    baixar_vimeo,
    eh_url_vimeo,
    titulo_do_vimeo,
    baixar_skool,
    eh_url_skool_video,
    baixar_anexos,
    PASTA_TEMP_RAIZ
)

# Cria o Blueprint (um módulo da aplicação Flask)
download_bp = Blueprint('download', __name__)

# Configura o Executor de Threads
# max_workers=3 significa que baixamos no máximo 3 aulas SIMULTANEAMENTE.
# O resto fica na fila esperando uma vaga.
executor = ThreadPoolExecutor(max_workers=3)

# --- 0. ORGANIZAÇÃO EM PASTA POR AULA ---
# Uma aula pode render vários arquivos (mp4 + md + anexos). Soltos no módulo, eles
# se misturam com os das aulas vizinhas. A partir de DOIS arquivos, a aula ganha
# pasta própria; com um só, ele continua solto (pasta com um arquivo é ruído).

def _quantos_artefatos(url, desc, resources, anexos, nome):
    """Prevê quantos arquivos esta aula vai gerar, ANTES de gravar qualquer um.

    O .md é previsto chamando o MESMO `montar_markdown` que grava depois — prever
    por regra própria (ex.: "tem desc?") sairia do ar assim que a regra de lá
    mudasse, e a pasta passaria a ser criada na hora errada.
    """
    tem_video = 1 if url else 0
    tem_md = 1 if montar_markdown(nome, desc, resources, permitir_vazio=not url) else 0
    return tem_video + tem_md + len(anexos or [])


def _adotar_arquivos_soltos(pasta_pai_abs, pasta_aula_abs, nome_limpo):
    """Move para a pasta da aula o que já havia sido baixado solto.

    Sem isto, mudar o layout faria o servidor NÃO encontrar o .mp4 antigo (ele
    procura no caminho novo) e rebaixar tudo do zero — 277 vídeos já em disco.
    Mover é instantâneo e preserva o trabalho já feito.
    """
    if not os.path.isdir(pasta_pai_abs):
        return 0

    movidos = 0
    for nome_arquivo in os.listdir(pasta_pai_abs):
        origem = os.path.join(pasta_pai_abs, nome_arquivo)
        if not os.path.isfile(origem):
            continue

        base, _ = os.path.splitext(nome_arquivo)
        # O .mp4/.md da aula, e os anexos que foram gravados com o prefixo dela.
        pertence = base == nome_limpo or nome_arquivo.startswith(f"{nome_limpo} - ")
        if not pertence:
            continue

        os.makedirs(pasta_aula_abs, exist_ok=True)
        destino = os.path.join(pasta_aula_abs, nome_arquivo)
        if os.path.exists(destino):
            continue          # já existe no lugar novo: não sobrescreve nada
        try:
            os.replace(origem, destino)
            movidos += 1
        except OSError as erro:
            print(f"⚠️  Não consegui mover '{nome_arquivo}' para a pasta da aula: {erro}")

    if movidos:
        print(f"📁 {movidos} arquivo(s) já baixado(s) movido(s) para a pasta de '{nome_limpo}'")
    return movidos


# --- 1. A LÓGICA DO TRABALHADOR (WORKER) ---
# Esta função roda em "segundo plano" (background) para não travar o servidor.
def worker_download(url, pasta_destino, nome_arquivo_sugerido, item_dashboard,
                    desc=None, resources=None, referer=None, anexos=None):
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
    # Se o pedido não trouxe nome (ex.: link colado no popup), descobrimos o título.
    # YouTube -> yt-dlp; Loom/embed -> extrator do Loom. Rotear aqui evita que uma
    # URL de YouTube caia no extrator do Loom e volte lixo.
    if not nome_arquivo_sugerido and url:
        if eh_url_youtube(url):
            nome_arquivo_sugerido = titulo_do_youtube(url)
        elif eh_url_vimeo(url):
            nome_arquivo_sugerido = titulo_do_vimeo(url, referer)
        elif eh_url_skool_video(url):
            # A URL do Skool é um .m3u8 puro: não tem título embutido para extrair.
            # Na prática a extensão sempre manda o nome da aula, então isto é só
            # uma rede de segurança para não cair no extrator do Loom e voltar lixo.
            nome_arquivo_sugerido = "Aula do Skool"
        else:
            titulo_extraido, _ = extrair_metadados(url)
            nome_arquivo_sugerido = titulo_extraido

    # Limpa caracteres proibidos (ex: remove "?", "/", ":")
    nome_limpo = limpar_nome_arquivo(nome_arquivo_sugerido)
    item_dashboard['nome'] = nome_limpo  # Atualiza o nome bonitinho no painel

    # YouTube: organiza por canal — output/YouTube/<Canal>/<Titulo>.mp4, a mesma
    # logica de pastas do Skool. O canal vem do proprio yt-dlp, entao vale para
    # qualquer entrada (botao na pagina, popup ou link colado). Se o canal nao
    # resolver, grava direto na pasta raiz (sem subpasta), sem quebrar nada.
    if url and eh_url_youtube(url):
        canal = canal_do_youtube(url)
        if canal:
            pasta_destino = os.path.join(pasta_destino, limpar_nome_arquivo(canal))
            item_dashboard['folder'] = pasta_destino

    # A partir de dois arquivos, a aula ganha pasta própria (mp4 + md + anexos ficam
    # juntos em vez de espalhados pelo módulo). Com um só, segue solto.
    aula_tem_pasta = _quantos_artefatos(url, desc, resources, anexos, nome_limpo) >= 2
    if aula_tem_pasta:
        pasta_pai = pasta_destino
        pasta_destino = os.path.join(pasta_destino, nome_limpo)
        item_dashboard['folder'] = pasta_destino

        # Recolhe o que já estava solto de execuções anteriores, para não rebaixar.
        pasta_pai_limpa = pasta_pai[1:] if pasta_pai.startswith(os.sep) else pasta_pai
        pasta_aula_limpa = pasta_destino[1:] if pasta_destino.startswith(os.sep) else pasta_destino
        _adotar_arquivos_soltos(os.path.join(PASTA_OUTPUT, pasta_pai_limpa),
                                os.path.join(PASTA_OUTPUT, pasta_aula_limpa),
                                nome_limpo)

    # Define onde ficarão os arquivos temporários (.ts)
    caminho_pasta_temp = os.path.join(PASTA_TEMP_RAIZ, nome_limpo)

    # B. Função de Callback
    # O downloader chama isso a cada pedacinho baixado para atualizar a barra
    def atualizar_progresso(total=None):
        if total:
            item_dashboard['total'] = total
        else:
            item_dashboard['progresso'] += 1

    # O yt-dlp avisa quando entra na fusão vídeo+áudio. Sem isto o painel ficava com
    # a barra em 100% e o rótulo "Baixando" durante todo o merge do ffmpeg, parecendo
    # travado. O caminho do Loom já sinalizava isso na mão (item E, mais abaixo).
    def marcar_convertendo():
        item_dashboard['status'] = 'convertendo'

    # C. Gravar o texto da aula (independe do vídeo; aula só-texto também tem).
    # Sem vídeo, gravamos o .md mesmo vazio (placeholder) — assim uma aula do
    # curso nunca é omitida em silêncio.
    try:
        caminho_md = salvar_aula_md(nome_limpo, pasta_destino, desc, resources,
                                    permitir_vazio=not url)
        if caminho_md:
            item_dashboard['tem_texto'] = True
    except Exception as erro:
        print(f"⚠️  Não foi possível gravar o texto de '{nome_limpo}': "
              f"{type(erro).__name__}: {erro}")

    # C.2. Arquivos anexos da aula. Vem ANTES do vídeo de propósito: em cursos como a
    # Biblioteca de Templates o anexo é o produto e o vídeo só o explica — se o vídeo
    # falhar, o material principal já está salvo.
    try:
        if anexos:
            baixados, falhas_anexo = baixar_anexos(anexos, pasta_destino, nome_limpo,
                                                   prefixar=not aula_tem_pasta)
            if baixados:
                item_dashboard['anexos'] = baixados
            if falhas_anexo:
                print(f"⚠️  {falhas_anexo} anexo(s) falharam em '{nome_limpo}'.")
    except Exception as erro:
        print(f"⚠️  Não foi possível baixar anexos de '{nome_limpo}': "
              f"{type(erro).__name__}: {erro}")

    # D. Baixar o vídeo, se houver
    video_ok = False
    if not url:
        # Aula só de texto: sucesso se o .md foi gravado.
        item_dashboard['total'] = 1
        item_dashboard['progresso'] = 1
        # Anexo conta como entrega: uma aula que só carrega um arquivo (comum na
        # Biblioteca de Templates) não é erro se o arquivo veio.
        sucesso_operacao = bool(item_dashboard.get('tem_texto')
                                or item_dashboard.get('anexos'))
        item_dashboard['status'] = 'sucesso' if sucesso_operacao else 'erro'
        return

    if eh_url_youtube(url):
        # YouTube: o yt-dlp resolve formato + fusão vídeo/áudio com ffmpeg.
        # Não passa pelo HLS nem pelo converter — grava direto o .mp4 final.
        video_ok = baixar_youtube(url, pasta_destino, nome_limpo, atualizar_progresso,
                                  ao_converter=marcar_convertendo)
    elif eh_url_vimeo(url):
        # Vimeo (privado no Skool): mesmo motor do YouTube, mas com o Referer da
        # página — é o que libera o vídeo restrito por domínio.
        video_ok = baixar_vimeo(url, pasta_destino, nome_limpo, referer, atualizar_progresso,
                                ao_converter=marcar_convertendo)
    elif eh_url_skool_video(url):
        # Vídeo hospedado no próprio Skool (Mux). A extensão já resolveu o token e
        # mandou o .m3u8 pronto — aqui é só baixar. Não passa pelo motor HLS do Loom:
        # o master do Mux tem URIs absolutas e nomes de segmento que colidem entre
        # vídeo e áudio (ver services/skool.py).
        video_ok = baixar_skool(url, pasta_destino, nome_limpo, atualizar_progresso,
                                ao_converter=marcar_convertendo)
    else:
        # Loom (e afins via embed): extrai o .m3u8 e baixa o HLS.
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
        dados_request.get('resources'),
        dados_request.get('referer'),
        dados_request.get('anexos')
    )

    return jsonify({"status": "ok", "mensagem": "Adicionado à fila"})