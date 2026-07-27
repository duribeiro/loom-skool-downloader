"""Vimeo: detecção de URL e wrappers sobre a engine yt-dlp.

O caso que importa é o Vimeo **privado embutido no Skool** (restrito por domínio).
Medido: `vimeo.com/{id}` dá 401, mas `player.vimeo.com/video/{id}` + `Referer` da
página do Skool libera o vídeo (h264 + aac). Por isso normalizamos sempre para a URL
do player e exigimos o `referer` (a URL da página onde a extensão detectou o vídeo).
"""
import re

from .ytdlp import baixar_com_ytdlp, titulo_via_ytdlp


def eh_url_vimeo(url):
    """True se a URL é do Vimeo (vimeo.com ou player.vimeo.com)."""
    return bool(url) and "vimeo.com" in url.lower()


def url_player_vimeo(url):
    """Normaliza para a URL do player (a que o yt-dlp baixa com referer).

    Aceita `vimeo.com/123`, `vimeo.com/video/123`, `player.vimeo.com/video/123?...`
    e devolve `https://player.vimeo.com/video/123`. Se não achar um id, devolve a
    URL como veio (deixa o yt-dlp tentar).
    """
    m = re.search(r"vimeo\.com/(?:video/)?(\d+)", url or "")
    if m:
        return f"https://player.vimeo.com/video/{m.group(1)}"
    return url


def baixar_vimeo(url, pasta_relativa_destino, nome_arquivo, referer=None, callback=None):
    """Baixa um vídeo do Vimeo na melhor qualidade em .mp4 (com referer do Skool)."""
    return baixar_com_ytdlp(url_player_vimeo(url), pasta_relativa_destino,
                            nome_arquivo, callback=callback, referer=referer)


def titulo_do_vimeo(url, referer=None):
    """Título do vídeo do Vimeo (para quando o pedido vem sem nome)."""
    return titulo_via_ytdlp(url_player_vimeo(url), referer=referer)
