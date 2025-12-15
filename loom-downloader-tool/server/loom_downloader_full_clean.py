import requests
import re
import os
import html
import subprocess
import shutil
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURAÇÕES ---
PASTA_OUTPUT = "output"
PASTA_TEMP_RAIZ = "hls-temp"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.loom.com/",
    "Origin": "https://www.loom.com"
}

def limpar_nome_arquivo(nome):
    nome = html.unescape(nome)
    return re.sub(r'[<>:"/\\|?*]', '', nome).strip()

def limpar_pasta_temporaria_especifica(caminho):
    if os.path.exists(caminho):
        try: shutil.rmtree(caminho)
        except: pass

def extrair_metadados(embed_url):
    try:
        r = requests.get(embed_url, headers=HEADERS)
        c = r.text
        mt = re.search(r'<title>(.*?)</title>', c)
        t = limpar_nome_arquivo(mt.group(1).replace(" | Loom", "")) if mt else "sem_titulo"
        mu = re.search(r'"url":"(https://[^"]+playlist\.m3u8[^"]+)"', c)
        return t, mu.group(1).replace('\\/', '/') if mu else None
    except: return None, None

def baixar_segmento(args):
    url, path, callback = args
    if os.path.exists(path) and os.path.getsize(path) > 0:
        if callback: callback() # Avisa que já existia (conta como progresso)
        return
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=20) as r:
            if r.status_code == 200:
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                if callback: callback() # Avisa que baixou um novo
    except:
        pass

def processar_download(url_master, nome_video, pasta_temp, callback_progresso=None):
    os.makedirs(pasta_temp, exist_ok=True)
    try: master = requests.get(url_master, headers=HEADERS).text
    except: return False

    base = url_master.rsplit('/', 1)[0] + '/'
    assinatura = urlparse(url_master).query
    
    videos = re.findall(r'#EXT-X-STREAM-INF:.*BANDWIDTH=(\d+).*\n(.*\.m3u8)', master)
    audio_match = re.search(r'TYPE=AUDIO.*URI="(.*?)"', master)
    if not videos or not audio_match: return False

    melhor_video = sorted(videos, key=lambda x: int(x[0]), reverse=True)[0][1]
    arquivo_audio = audio_match.group(1)

    filas = [] # Lista de tuplas (url, caminho, callback)
    
    def prep(m3u8):
        u = f"{base}{m3u8}?{assinatura}"
        c = requests.get(u, headers=HEADERS).text
        for l in c.splitlines():
            l = l.strip()
            if ".ts" in l:
                nome_ts = re.search(r'(.+?\.ts)', l).group(1).strip()
                url = f"{base}{l}" if "Signature=" in l else f"{base}{l}?{assinatura}"
                # Adiciona à fila passando o callback
                filas.append((url, os.path.join(pasta_temp, os.path.basename(nome_ts)), callback_progresso))
    
    prep(melhor_video)
    prep(arquivo_audio)
    
    with open(os.path.join(pasta_temp, "master.m3u8"), "w") as f: f.write(master)

    # Define o total para o servidor saber quanto falta
    if callback_progresso: 
        callback_progresso(total=len(filas))

    # Inicia o download (sem barra visual aqui, apenas lógica)
    with ThreadPoolExecutor(max_workers=12) as ex:
        ex.map(baixar_segmento, filas)
    
    return True

def converter_final(nome, pasta_rel, pasta_temp):
    dest = os.path.join(PASTA_OUTPUT, pasta_rel)
    os.makedirs(dest, exist_ok=True)
    final = os.path.abspath(os.path.join(dest, f"{limpar_nome_arquivo(nome)}.mp4"))
    
    cmd = ["ffmpeg", "-y", "-allowed_extensions", "ALL", "-i", "master.m3u8", "-c", "copy", "-bsf:a", "aac_adtstoasc", final]
    try:
        subprocess.run(cmd, cwd=pasta_temp, check=True, capture_output=True)
        return True
    except: return False