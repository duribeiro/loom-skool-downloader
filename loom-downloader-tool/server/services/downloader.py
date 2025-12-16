import os
import re
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from .utils import HEADERS, limpar_nome_arquivo

# --- 1. CONFIGURAÇÃO DE CAMINHOS ---
# Precisamos saber onde é a pasta "output" para verificar se o arquivo já existe.
# Usamos a mesma lógica do converter.py para garantir consistência.
dir_atual = os.path.dirname(os.path.abspath(__file__)) 
dir_server = os.path.dirname(dir_atual)
dir_raiz = os.path.dirname(dir_server)
PASTA_OUTPUT = os.path.join(dir_raiz, "output")

def _baixar_segmento(dados_segmento):
    """
    Função auxiliar que baixa um pequeno pedaço (.ts) do vídeo.
    É executada em paralelo (várias ao mesmo tempo).
    """
    url, caminho_arquivo, callback_progresso = dados_segmento
    
    # Retomada Inteligente: Se o pedaço já existe e tem dados, não baixamos de novo.
    if os.path.exists(caminho_arquivo) and os.path.getsize(caminho_arquivo) > 0:
        if callback_progresso: 
            callback_progresso()
        return

    try:
        # stream=True é importante para baixar arquivos aos poucos e não lotar a memória RAM
        with requests.get(url, headers=HEADERS, stream=True, timeout=20) as resposta:
            if resposta.status_code == 200:
                with open(caminho_arquivo, 'wb') as arquivo:
                    for pedaco_bytes in resposta.iter_content(chunk_size=8192): 
                        arquivo.write(pedaco_bytes)
                
                # Avisa o painel que mais um pedaço foi concluído
                if callback_progresso: 
                    callback_progresso()
    except Exception:
        # Se falhar um pedaço, o FFmpeg costuma conseguir pular, ou tentamos de novo depois.
        pass

def processar_download(url_master, pasta_temp, nome, pasta_rel, callback_progresso=None):
    """
    Gerencia todo o processo:
    1. Verifica se já temos o vídeo final.
    2. Baixa a playlist principal (master.m3u8).
    3. Identifica a melhor qualidade de vídeo e o áudio.
    4. Baixa todos os fragmentos (.ts) em paralelo.
    """

    # --- 2. VERIFICAÇÃO DE EXISTÊNCIA (O "Pulo do Gato") 🐈 ---
    if nome and pasta_rel:
        # Remove barra inicial se houver (ex: "/Curso" vira "Curso")
        caminho_relativo_limpo = pasta_rel[1:] if pasta_rel.startswith(os.sep) else pasta_rel
        
        # Monta o caminho exato onde o arquivo final estaria
        nome_arquivo_final = f"{limpar_nome_arquivo(nome)}.mp4"
        caminho_final_previsto = os.path.join(PASTA_OUTPUT, caminho_relativo_limpo, nome_arquivo_final)
        
        # Se existe e é um arquivo válido (maior que 1MB)
        if os.path.exists(caminho_final_previsto) and os.path.getsize(caminho_final_previsto) > 1_000_000:
            print(f"⏩ DOWNLOAD PULADO: O arquivo já existe em: {caminho_final_previsto}")
            # Simulamos progresso completo para o dashboard ficar verde
            if callback_progresso:
                callback_progresso(total=1)
            return True # Retorna True indicando "Sucesso" (mesmo sem baixar)

    # --- 3. PREPARAÇÃO ---
    os.makedirs(pasta_temp, exist_ok=True)
    
    try: 
        resposta_master = requests.get(url_master, headers=HEADERS)
        texto_master = resposta_master.text
    except: 
        return False

    # Define a URL base para completar os links relativos dentro da playlist
    base_url = url_master.rsplit('/', 1)[0] + '/'
    assinatura_url = urlparse(url_master).query # Tokens de segurança da URL
    
    # --- 4. SELEÇÃO DE QUALIDADE ---
    # Procura linhas que indicam vídeo e pega a largura de banda (qualidade)
    videos_encontrados = re.findall(r'#EXT-X-STREAM-INF:.*BANDWIDTH=(\d+).*\n(.*\.m3u8)', texto_master)
    audio_encontrado = re.search(r'TYPE=AUDIO.*URI="(.*?)"', texto_master)
    
    if not videos_encontrados or not audio_encontrado: 
        return False

    # Ordena do maior bitrate para o menor e pega o primeiro (Melhor Qualidade)
    melhor_video_m3u8 = sorted(videos_encontrados, key=lambda x: int(x[0]), reverse=True)[0][1]
    arquivo_audio_m3u8 = audio_encontrado.group(1)

    # Listas para guardar o trabalho a fazer
    fila_downloads = []
    arquivos_playlists = {} # Vai guardar o conteúdo modificado das playlists
    
    # Função interna para preparar as listas de download
    def preparar_playlist(arquivo_m3u8, tipo):
        url_completa = f"{base_url}{arquivo_m3u8}?{assinatura_url}"
        try:
            resposta = requests.get(url_completa, headers=HEADERS)
            conteudo_playlist = resposta.text
            
            # Nome do arquivo local (ex: video.m3u8)
            nome_arquivo_playlist = os.path.basename(arquivo_m3u8.split('?', 1)[0])
            
            # Lê linha por linha para achar os arquivos .ts
            for linha in conteudo_playlist.splitlines():
                linha = linha.strip()
                if ".ts" in linha:
                    # Extrai apenas o nome do arquivo .ts
                    nome_ts = re.search(r'(.+?\.ts)', linha).group(1).strip()
                    
                    # Monta a URL de download do fragmento
                    if "Signature=" in linha:
                        url_ts = f"{base_url}{linha}"
                    else:
                        url_ts = f"{base_url}{linha}?{assinatura_url}"
                    
                    caminho_destino_ts = os.path.join(pasta_temp, os.path.basename(nome_ts))
                    
                    # Adiciona à fila de trabalho
                    fila_downloads.append((url_ts, caminho_destino_ts, callback_progresso))
            
            # Guarda o conteúdo para salvar em disco depois
            arquivos_playlists[tipo] = (nome_arquivo_playlist, conteudo_playlist)
        except: 
            pass
    
    # Prepara Vídeo e Áudio
    preparar_playlist(melhor_video_m3u8, "video")
    preparar_playlist(arquivo_audio_m3u8, "audio")
    
    # --- 5. SALVAR ARQUIVOS DE CONTROLE ---
    # Salvamos o master.m3u8 e as playlists de video/audio na pasta temp
    # O FFmpeg vai precisar ler esses arquivos locais para juntar tudo depois.
    with open(os.path.join(pasta_temp, "master.m3u8"), "w") as f: 
        f.write(texto_master)
        
    if "video" in arquivos_playlists:
        nome, conteudo = arquivos_playlists["video"]
        with open(os.path.join(pasta_temp, nome), "w") as f: f.write(conteudo)
        
    if "audio" in arquivos_playlists:
        nome, conteudo = arquivos_playlists["audio"]
        with open(os.path.join(pasta_temp, nome), "w") as f: f.write(conteudo)

    # Define o tamanho total da barra de progresso
    if callback_progresso: 
        callback_progresso(total=len(fila_downloads))

    # --- 6. DOWNLOAD EM MASSA (PARALELO) ---
    # Usamos 12 "trabalhadores" para baixar rápido
    with ThreadPoolExecutor(max_workers=12) as executor:
        executor.map(_baixar_segmento, fila_downloads)
    
    return True