"""YouTube: detecção de URL e wrappers finos sobre a engine yt-dlp.

A lógica de download mora em `ytdlp.py` (compartilhada com o Vimeo). Aqui só fica o
que é específico do YouTube.
"""
from .ytdlp import baixar_com_ytdlp, titulo_via_ytdlp, canal_via_ytdlp


def eh_url_youtube(url):
    """True se a URL é do YouTube (watch, embed, youtu.be, shorts)."""
    if not url:
        return False
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u


def baixar_youtube(url, pasta_relativa_destino, nome_arquivo, callback=None):
    """Baixa um vídeo do YouTube na melhor qualidade em .mp4."""
    return baixar_com_ytdlp(url, pasta_relativa_destino, nome_arquivo, callback=callback)


def titulo_do_youtube(url):
    """Título do vídeo do YouTube (para quando o pedido vem sem nome)."""
    return titulo_via_ytdlp(url)


def canal_do_youtube(url):
    """Nome do canal do YouTube — para organizar em output/YouTube/<Canal>/."""
    return canal_via_ytdlp(url)
