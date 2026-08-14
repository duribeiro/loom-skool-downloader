"""Loom: detecção de URL e wrappers finos sobre a engine yt-dlp.

POR QUE ISTO EXISTE, tendo o projeto um motor HLS próprio para o Loom
(`downloader.py`): porque o motor próprio não dá conta de uma família inteira de
vídeos, e o yt-dlp dá.

MEDIDO em 14/08/2026, comunidade NoeAI Automator — 53 aulas falhando nas DUAS
tentativas (108 linhas no erros.log). A causa:

  A assinatura do master é escopada ao ARQUIVO, não à pasta. A policy do
  CloudFront que vem na query do master diz, literalmente:

      "Resource": "https://cdn.loom.com/sessions/raw/<id>.m3u8"

  `processar_download` reaproveita essa mesma query para buscar `<id>-video0.m3u8`
  e `<id>-audio0.m3u8`. Resposta medida nos dois: HTTP 403 AccessDenied. Não é
  rede nem bloqueio por volume — é 403 por construção, o que explica as mesmas
  aulas falharem em toda tentativa.

O yt-dlp não tem esse problema porque não adivinha URL: ele pede as URLs
assinadas à GraphQL do Loom (`raw-url`, `transcoded-url`) e recebe uma para cada
arquivo.

COMPARADO no mesmo vídeo em que o motor próprio funciona (Mastermind Call de
21/04): motor próprio 1920x1080 / 1,33 GiB; yt-dlp `hls-raw-3200` 1920x1080 /
~1,43 GiB. Empatam. No vídeo que o motor próprio recusa (`/resume`), o yt-dlp
entrega 1108x720, 95,42s, áudio aac — o vídeo íntegro.

NÃO PRECISA DE SESSÃO DO SKOOL. Verificado rodando o yt-dlp de um terminal limpo,
sem cookie nenhum: vídeo do Loom referenciado por uma aula do Skool é acessível
só pelo ID. Diferente do Vimeo privado (exige `Referer`) e do vídeo próprio do
Skool (exige `playbackToken`, que expira em ~24h).

O motor HLS próprio continua no repositório e continua sendo o caminho de
qualquer embed que não seja Loom — ver o `else` em `worker_download`.
"""
from .ytdlp import baixar_com_ytdlp, titulo_via_ytdlp


def eh_url_loom(url):
    """True se a URL é do Loom (share ou embed).

    As duas formas existem no uso real: a extensão manda `/embed/` quando lê o
    iframe do player, e o `videoLink` da unit do Skool costuma vir como `/share/`.
    O yt-dlp aceita as duas — conferido.
    """
    if not url:
        return False
    return "loom.com" in url.lower()


def baixar_loom(url, pasta_relativa_destino, nome_arquivo, callback=None,
                ao_converter=None, ao_fase=None):
    """Baixa um vídeo do Loom na melhor qualidade em .mp4."""
    return baixar_com_ytdlp(url, pasta_relativa_destino, nome_arquivo,
                            callback=callback, ao_converter=ao_converter,
                            ao_fase=ao_fase)


def titulo_do_loom(url):
    """Título do vídeo do Loom (para quando o pedido vem sem nome)."""
    return titulo_via_ytdlp(url)
