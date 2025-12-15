import os
import re
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from .utils import HEADERS

def _baixar_chunk(args):
    url, path, callback = args
    # Se já existe e tem tamanho, pula (Retomada inteligente)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        if callback: callback()
        return
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=20) as r:
            if r.status_code == 200:
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                if callback: callback()
    except: pass

def processar_download(url_master, pasta_temp, callback_progresso=None):
    os.makedirs(pasta_temp, exist_ok=True)
    try: master = requests.get(url_master, headers=HEADERS).text
    except: return False

    base = url_master.rsplit('/', 1)[0] + '/'
    assinatura = urlparse(url_master).query
    
    # Regex para achar qualidades de vídeo
    videos = re.findall(r'#EXT-X-STREAM-INF:.*BANDWIDTH=(\d+).*\n(.*\.m3u8)', master)
    audio_match = re.search(r'TYPE=AUDIO.*URI="(.*?)"', master)
    
    if not videos or not audio_match: return False

    # Pega sempre a melhor qualidade
    melhor_video = sorted(videos, key=lambda x: int(x[0]), reverse=True)[0][1]
    arquivo_audio = audio_match.group(1)

    filas = []
    playlists = {}
    
    def prep(m3u8, chave):
        u = f"{base}{m3u8}?{assinatura}"
        try:
            c = requests.get(u, headers=HEADERS).text
            playlist_nome = os.path.basename(m3u8.split('?', 1)[0])
            for l in c.splitlines():
                l = l.strip()
                if ".ts" in l:
                    nome_ts = re.search(r'(.+?\.ts)', l).group(1).strip()
                    url_ts = f"{base}{l}" if "Signature=" in l else f"{base}{l}?{assinatura}"
                    filas.append((url_ts, os.path.join(pasta_temp, os.path.basename(nome_ts)), callback_progresso))
            playlists[chave] = (playlist_nome, c)
        except: pass
    
    prep(melhor_video, "video")
    prep(arquivo_audio, "audio")
    
    with open(os.path.join(pasta_temp, "master.m3u8"), "w") as f: f.write(master)
    if "video" in playlists:
        nome, conteudo = playlists["video"]
        with open(os.path.join(pasta_temp, nome), "w") as f: f.write(conteudo)
    if "audio" in playlists:
        nome, conteudo = playlists["audio"]
        with open(os.path.join(pasta_temp, nome), "w") as f: f.write(conteudo)

    if callback_progresso: 
        callback_progresso(total=len(filas))

    with ThreadPoolExecutor(max_workers=12) as ex:
        ex.map(_baixar_chunk, filas)
    
    return True
