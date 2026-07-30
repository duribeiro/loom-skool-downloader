import re
import html
import json
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

# --- EXTRAÇÃO DOS DADOS DA PÁGINA DO LOOM ------------------------------------
#
# A página do Loom carrega um objeto JSON completo em `window.__APOLLO_STATE__`
# com tudo que o player precisa. Lemos DESSE objeto, pela estrutura dele.
#
# Por que não por regex no texto: já quebrou. O Loom renomeou o arquivo da
# playlist de "playlist.m3u8" para "playlist-multibitrate.m3u8" e a extração
# parou de funcionar, sem erro nenhum. Casar texto depende do formato da string;
# ler a estrutura depende só do contrato dos dados, que muda muito menos.

TIPO_URL_ASSINADA = "CloudfrontSignedUrlPayload"
TIPO_VIDEO = "RegularUserVideo"


def _extrair_apollo_state(conteudo_html):
    """
    Recorta o objeto `window.__APOLLO_STATE__` do HTML e devolve como dict.

    O truque está em não tentar achar onde o objeto termina: contar chaves
    dá errado porque existem chaves dentro de strings. Achamos onde ele
    COMEÇA e deixamos o parser de JSON ler até o fim natural do objeto.
    """
    marcador = re.search(r'window\.__APOLLO_STATE__\s*=\s*', conteudo_html)
    if not marcador:
        return None

    try:
        dados, _ = json.JSONDecoder().raw_decode(conteudo_html, marcador.end())
        return dados
    except ValueError:
        return None


def _caminhar(no, aceita):
    """
    Percorre a árvore de dados e devolve o primeiro nó aceito por `aceita`.

    O Apollo guarda os dados numa estrutura aninhada e com chaves geradas
    dinamicamente (ex: 'RegularUserVideo:abc123'), então não dá para navegar
    por um caminho fixo — procuramos pelo formato do nó.
    """
    if isinstance(no, dict):
        resultado = aceita(no)
        if resultado is not None:
            return resultado
        for valor in no.values():
            achado = _caminhar(valor, aceita)
            if achado is not None:
                return achado
    elif isinstance(no, list):
        for item in no:
            achado = _caminhar(item, aceita)
            if achado is not None:
                return achado
    return None


def _procurar_url_do_stream(dados):
    """Acha a URL assinada do .m3u8 pelo __typename do nó."""
    def aceita(no):
        if no.get("__typename") != TIPO_URL_ASSINADA:
            return None
        url = no.get("url")
        if isinstance(url, str) and ".m3u8" in url:
            return url
        return None

    return _caminhar(dados, aceita)


def _procurar_titulo(dados):
    """Acha o nome do vídeo pelo __typename do nó."""
    def aceita(no):
        if no.get("__typename") != TIPO_VIDEO:
            return None
        nome = no.get("name")
        return nome if isinstance(nome, str) and nome.strip() else None

    return _caminhar(dados, aceita)


def _titulo_pela_tag_title(conteudo_html):
    """Reserva: pega o título da tag <title> quando o Apollo não tem o nome."""
    match = re.search(r'<title>(.*?)</title>', conteudo_html, re.S)
    if not match:
        return None
    return match.group(1).replace(" | Loom", "")


def _url_por_regex(conteudo_html):
    """
    ÚLTIMO RECURSO. Mantido de propósito: se o Loom mudar o formato do
    __APOLLO_STATE__, isto ainda pode salvar o download. Quando cair aqui,
    avisamos — degradar em silêncio foi o que custou caro da última vez.
    """
    match = re.search(r'"url":"(https://[^"]+\.m3u8[^"]*)"', conteudo_html)
    if not match:
        return None
    return match.group(1).replace('\\/', '/')


def extrair_metadados(url_loom):
    """
    Acessa a página do vídeo (embed) e descobre:
    1. O título original
    2. A URL da playlist (m3u8)

    Devolve (None, None) se a página não puder ser acessada.
    """
    try:
        resposta = requests.get(url_loom, headers=HEADERS, timeout=10)
        conteudo_html = resposta.text
    except Exception as erro:
        print(f"⚠️  Não foi possível acessar {url_loom}: {type(erro).__name__}: {erro}")
        return None, None

    dados = _extrair_apollo_state(conteudo_html)

    # --- URL do stream ---
    url_m3u8 = _procurar_url_do_stream(dados) if dados else None

    if url_m3u8 is None:
        url_m3u8 = _url_por_regex(conteudo_html)
        if url_m3u8:
            print("⚠️  Extração estrutural falhou; usando o regex reserva. "
                  "O formato da página do Loom provavelmente mudou.")
        else:
            motivo = ("__APOLLO_STATE__ não encontrado na página"
                      if not dados else
                      f"nenhum nó '{TIPO_URL_ASSINADA}' com .m3u8 no __APOLLO_STATE__")
            print(f"❌ Não foi possível extrair a URL do vídeo: {motivo}")

    if url_m3u8:
        # Desfaz as barras escapadas do JSON (ex: \/ vira /)
        url_m3u8 = url_m3u8.replace('\\/', '/')

    # --- Título ---
    titulo_bruto = (_procurar_titulo(dados) if dados else None) \
        or _titulo_pela_tag_title(conteudo_html)
    titulo_limpo = limpar_nome_arquivo(titulo_bruto) if titulo_bruto else "sem_titulo"

    return titulo_limpo, url_m3u8