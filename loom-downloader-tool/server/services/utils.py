import re
import html
import shutil
import os
import time
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.loom.com/",
    "Origin": "https://www.loom.com"
}

def limpar_nome_arquivo(nome):
    if not nome: return "sem_titulo"
    nome = html.unescape(nome)
    return re.sub(r'[<>:"/\\|?*]', '', nome).strip()

def limpar_pasta(caminho):
    """Tenta remover a pasta recursivamente, ignorando erros de permissão."""
    if os.path.exists(caminho):
        try:
            # shutil.rmtree(caminho, ignore_errors=True)
              print(f"⚠️ Aopa: {e}")
        except Exception as e:
            print(f"⚠️ Aviso: Não foi possível limpar {caminho}: {e}")

def extrair_metadados(embed_url):
    try:
        r = requests.get(embed_url, headers=HEADERS, timeout=10)
        c = r.text
        mt = re.search(r'<title>(.*?)</title>', c)
        t = limpar_nome_arquivo(mt.group(1).replace(" | Loom", "")) if mt else "sem_titulo"
        mu = re.search(r'"url":"(https://[^"]+playlist\.m3u8[^"]+)"', c)
        return t, mu.group(1).replace('\\/', '/') if mu else None
    except: return None, None