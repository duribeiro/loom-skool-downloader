import os
import time
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from .utils import HEADERS, limpar_nome_arquivo
from .caminhos import PASTA_OUTPUT

# Quantas vezes tentar baixar um segmento antes de desistir dele.
TENTATIVAS_POR_SEGMENTO = 3


# --- PARSER DE PLAYLIST HLS --------------------------------------------------
# Uma playlist HLS tem gramática própria: linhas de tag começam com '#', e a
# URI de um stream vem na linha seguinte à sua tag #EXT-X-STREAM-INF. Casar isso
# com regex e '.*\n' é frágil (quebra com espaço, ordem de atributos, CRLF).
# Lemos linha a linha, respeitando o formato.

def _dividir_atributos(texto):
    """
    Divide a lista de atributos de uma tag HLS em pares (chave, valor).

    Não dá para um split simples por vírgula: um valor entre aspas pode conter
    vírgula (ex: CODECS="avc1.4d401f,mp4a.40.2"). Então varremos caractere a
    caractere, ignorando as vírgulas que estão dentro de aspas.
    """
    pares = []
    atual = ""
    dentro_de_aspas = False
    for caractere in texto:
        if caractere == '"':
            dentro_de_aspas = not dentro_de_aspas
            atual += caractere
        elif caractere == "," and not dentro_de_aspas:
            pares.append(atual)
            atual = ""
        else:
            atual += caractere
    if atual:
        pares.append(atual)

    atributos = {}
    for par in pares:
        if "=" in par:
            chave, valor = par.split("=", 1)
            atributos[chave.strip()] = valor.strip().strip('"')
    return atributos


def _parsear_master(texto_master):
    """
    Lê o master.m3u8 e devolve (streams_de_video, uri_do_audio).

    streams_de_video é uma lista de (bandwidth:int, uri:str).
    uri_do_audio é a URI da faixa de áudio, ou None.
    """
    linhas = texto_master.splitlines()
    streams_video = []
    uri_audio = None

    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()

        if linha.startswith("#EXT-X-STREAM-INF:"):
            atributos = _dividir_atributos(linha.split(":", 1)[1])
            try:
                bandwidth = int(atributos.get("BANDWIDTH", 0))
            except ValueError:
                bandwidth = 0

            # A URI do stream é a próxima linha que não é vazia nem comentário.
            uri = None
            j = i + 1
            while j < len(linhas):
                proxima = linhas[j].strip()
                if proxima and not proxima.startswith("#"):
                    uri = proxima
                    break
                j += 1
            if uri:
                streams_video.append((bandwidth, uri))
            i = j
            continue

        if linha.startswith("#EXT-X-MEDIA:"):
            atributos = _dividir_atributos(linha.split(":", 1)[1])
            if atributos.get("TYPE") == "AUDIO" and atributos.get("URI"):
                uri_audio = atributos["URI"]

        i += 1

    return streams_video, uri_audio


def _extrair_segmentos(texto_playlist):
    """
    Devolve as URIs de segmento de uma mediaplaylist, na ordem.

    Numa mediaplaylist, segmento é toda linha que não é vazia nem comentário.
    Não exigimos a extensão '.ts': se o Loom trocar por .m4s/.aac, continua
    funcionando.
    """
    segmentos = []
    for linha in texto_playlist.splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#"):
            segmentos.append(linha)
    return segmentos


# --- DOWNLOAD DE SEGMENTOS ---------------------------------------------------

def _baixar_segmento(dados_segmento):
    """
    Baixa um pedaço (.ts) do vídeo. Roda em paralelo com vários outros.

    Devolve True se o segmento está em disco ao final, False se falhou depois de
    todas as tentativas. Diferente da versão antiga, uma falha NÃO é engolida em
    silêncio: ela vira um False que o chamador contabiliza.
    """
    url, caminho_arquivo, callback_progresso = dados_segmento

    # Retomada: se o pedaço já existe e tem dados, não baixa de novo.
    if os.path.exists(caminho_arquivo) and os.path.getsize(caminho_arquivo) > 0:
        if callback_progresso:
            callback_progresso()
        return True

    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS_POR_SEGMENTO + 1):
        try:
            # stream=True baixa aos poucos, sem lotar a RAM.
            with requests.get(url, headers=HEADERS, stream=True, timeout=20) as resposta:
                if resposta.status_code != 200:
                    ultimo_erro = f"HTTP {resposta.status_code}"
                    continue
                with open(caminho_arquivo, "wb") as arquivo:
                    for pedaco_bytes in resposta.iter_content(chunk_size=8192):
                        arquivo.write(pedaco_bytes)
            if callback_progresso:
                callback_progresso()
            return True
        except Exception as erro:
            ultimo_erro = f"{type(erro).__name__}: {erro}"
            if tentativa < TENTATIVAS_POR_SEGMENTO:
                time.sleep(0.5 * tentativa)  # pequeno backoff antes de tentar de novo

    # Falhou de vez. Remove um arquivo parcial para não virar "sucesso" na retomada.
    if os.path.exists(caminho_arquivo):
        try:
            os.remove(caminho_arquivo)
        except OSError:
            pass
    print(f"⚠️  Segmento falhou após {TENTATIVAS_POR_SEGMENTO} tentativas "
          f"({ultimo_erro}): {os.path.basename(caminho_arquivo)}")
    return False


def processar_download(url_master, pasta_temp, nome, pasta_rel, callback_progresso=None):
    """
    Gerencia todo o processo:
    1. Verifica se já temos o vídeo final.
    2. Baixa a playlist principal (master.m3u8).
    3. Identifica a melhor qualidade de vídeo e o áudio.
    4. Baixa todos os fragmentos (.ts) em paralelo.

    Devolve True em sucesso, False se algo impediu o download.
    """

    # --- VERIFICAÇÃO DE EXISTÊNCIA (O "Pulo do Gato") 🐈 ---
    if nome and pasta_rel:
        caminho_relativo_limpo = pasta_rel[1:] if pasta_rel.startswith(os.sep) else pasta_rel
        nome_arquivo_final = f"{limpar_nome_arquivo(nome)}.mp4"
        caminho_final_previsto = os.path.join(PASTA_OUTPUT, caminho_relativo_limpo, nome_arquivo_final)

        if os.path.exists(caminho_final_previsto) and os.path.getsize(caminho_final_previsto) > 1_000_000:
            print(f"⏩ DOWNLOAD PULADO: O arquivo já existe em: {caminho_final_previsto}")
            if callback_progresso:
                callback_progresso(total=1)
            return True

    # --- PREPARAÇÃO ---
    os.makedirs(pasta_temp, exist_ok=True)

    try:
        resposta_master = requests.get(url_master, headers=HEADERS)
        texto_master = resposta_master.text
    except Exception as erro:
        print(f"❌ Não foi possível baixar o master.m3u8: {type(erro).__name__}: {erro}")
        return False

    base_url = url_master.rsplit("/", 1)[0] + "/"
    assinatura_url = urlparse(url_master).query  # tokens de segurança da URL

    # --- SELEÇÃO DE QUALIDADE (parser HLS, sem regex) ---
    streams_video, uri_audio = _parsear_master(texto_master)

    if not streams_video:
        print("❌ Nenhum stream de vídeo encontrado no master.m3u8.")
        return False
    if not uri_audio:
        print("❌ Nenhuma faixa de áudio encontrada no master.m3u8.")
        return False

    # Maior bandwidth = melhor qualidade.
    melhor_video_m3u8 = max(streams_video, key=lambda s: s[0])[1]
    arquivo_audio_m3u8 = uri_audio

    fila_downloads = []
    arquivos_playlists = {}  # conteúdo das playlists, para gravar depois

    def preparar_playlist(arquivo_m3u8, tipo):
        url_completa = f"{base_url}{arquivo_m3u8}?{assinatura_url}"
        try:
            resposta = requests.get(url_completa, headers=HEADERS)
            conteudo_playlist = resposta.text
        except Exception as erro:
            print(f"❌ Falha ao baixar a playlist de {tipo}: {type(erro).__name__}: {erro}")
            return

        nome_arquivo_playlist = os.path.basename(arquivo_m3u8.split("?", 1)[0])

        for segmento in _extrair_segmentos(conteudo_playlist):
            # Se o segmento já traz a própria assinatura, não anexamos a nossa.
            if "Signature=" in segmento:
                url_ts = f"{base_url}{segmento}"
            else:
                url_ts = f"{base_url}{segmento}?{assinatura_url}"

            nome_ts = os.path.basename(segmento.split("?", 1)[0])
            caminho_destino_ts = os.path.join(pasta_temp, nome_ts)
            fila_downloads.append((url_ts, caminho_destino_ts, callback_progresso))

        arquivos_playlists[tipo] = (nome_arquivo_playlist, conteudo_playlist)

    preparar_playlist(melhor_video_m3u8, "video")
    preparar_playlist(arquivo_audio_m3u8, "audio")

    if "video" not in arquivos_playlists or "audio" not in arquivos_playlists:
        print("❌ Não foi possível preparar as playlists de vídeo e/ou áudio.")
        return False

    # --- SALVAR ARQUIVOS DE CONTROLE ---
    # O FFmpeg lê estes arquivos locais para juntar tudo depois.
    with open(os.path.join(pasta_temp, "master.m3u8"), "w") as f:
        f.write(texto_master)
    for tipo in ("video", "audio"):
        nome_pl, conteudo_pl = arquivos_playlists[tipo]
        with open(os.path.join(pasta_temp, nome_pl), "w") as f:
            f.write(conteudo_pl)

    if callback_progresso:
        callback_progresso(total=len(fila_downloads))

    # --- DOWNLOAD EM MASSA (PARALELO) ---
    with ThreadPoolExecutor(max_workers=12) as executor:
        resultados = list(executor.map(_baixar_segmento, fila_downloads))

    # Falha de segmento vira buraco no vídeo. Antes isso era invisível; agora avisa.
    total = len(resultados)
    falhas = resultados.count(False)
    if falhas:
        print(f"⚠️  ATENÇÃO: {falhas} de {total} segmentos falharam em '{nome}'. "
              f"O vídeo pode ter trechos faltando.")

    return True
