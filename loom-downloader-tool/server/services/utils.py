import re
import html
import shutil
import os
import requests

# Cabeçalhos para fingir que somos um navegador real e não ser bloqueado
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.loom.com/",
    "Origin": "https://www.loom.com"
}

def limpar_nome_arquivo(nome):
    """
    Remove caracteres proibidos em nomes de arquivos do Windows/Linux.
    Ex: "Aula: 01?" vira "Aula 01"
    """
    if not nome: return "sem_titulo"
    
    # Decodifica entidades HTML (ex: &amp; vira &)
    nome = html.unescape(nome)
    
    # Remove caracteres proibidos (< > : " / \ | ? *)
    nome = re.sub(r'[<>:"/\\|?*]', '', nome)
    
    # Remove espaços duplos e espaços nas pontas
    return " ".join(nome.split())

def limpar_pasta(caminho):
    """
    Tenta remover uma pasta e todo o seu conteúdo recursivamente.
    Útil para limpar os arquivos temporários após o download.
    """
    if os.path.exists(caminho):
        try:
            shutil.rmtree(caminho, ignore_errors=True)
        except Exception as e:
            print(f"⚠️ Aviso: Não foi possível limpar {caminho}: {e}")

def extrair_metadados(url_loom):
    """
    Acessa a página do vídeo (embed) e tenta descobrir:
    1. O título original
    2. A URL da playlist (m3u8)
    """
    try:
        resposta = requests.get(url_loom, headers=HEADERS, timeout=10)
        conteudo_html = resposta.text
        
        # Busca o Título dentro da tag <title>
        match_titulo = re.search(r'<title>(.*?)</title>', conteudo_html)
        if match_titulo:
            titulo_bruto = match_titulo.group(1).replace(" | Loom", "")
            titulo_limpo = limpar_nome_arquivo(titulo_bruto)
        else:
            titulo_limpo = "sem_titulo"
            
        # Busca a URL do stream m3u8 dentro do JSON da página
        match_url = re.search(r'"url":"(https://[^"]+playlist\.m3u8[^"]+)"', conteudo_html)
        
        url_m3u8 = None
        if match_url:
            # Corrige as barras invertidas do JSON (ex: \/)
            url_m3u8 = match_url.group(1).replace('\\/', '/')
            
        return titulo_limpo, url_m3u8
        
    except Exception:
        return None, None