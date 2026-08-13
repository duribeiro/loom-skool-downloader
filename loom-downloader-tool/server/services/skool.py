"""Vídeo hospedado pelo próprio Skool (Mux white-label).

Nem toda aula do Skool aponta para Loom/YouTube. Muitas têm só `metadata.videoId`
e o vídeo mora na infra do Skool — que é **Mux** por baixo. Medido em `ai-makers`:
32 das 280 aulas são assim, e o curso "Supabase" é 100% desse tipo (7 de 7). Antes
disto, essas aulas eram tratadas como "sem vídeo" e só geravam o `.md` — em silêncio.

A extensão resolve `videoId` -> `playbackId` + `playbackToken` (só ela tem a sessão
do Skool) e manda a URL pronta do `.m3u8`. Aqui só baixamos.

Por que yt-dlp e não o `processar_download` (o motor HLS do Loom): o master do Mux
é incompatível com ele em dois pontos MEDIDOS —

1. as URIs são **absolutas e em outro host** (`manifest-*.fastly.video.skool.com`),
   enquanto o downloader monta `base_url + uri` assumindo caminho relativo;
2. os segmentos de vídeo e de áudio têm **nomes idênticos** (`0.m4s`, `1.m4s`, ...).
   Como o downloader grava tudo por `basename` numa pasta só, o áudio sobrescreveria
   o vídeo — e o check de retomada ("já existe e tem bytes") faria os 147 segmentos
   de áudio passarem na hora, gerando um mp4 corrompido sem nenhum erro na tela.

O yt-dlp já trata absoluto, áudio separado e fMP4, e é o mesmo motor que YouTube e
Vimeo usam aqui. Reaproveitar custou menos e arrisca menos que reescrever o HLS.
"""
import os

import requests

from .ytdlp import baixar_com_ytdlp
from .utils import cortar_preservando_extensao
from .caminhos import PASTA_OUTPUT

# O player do Skool serve o HLS por este host (Mux white-label).
HOST_STREAM = "stream.video.skool.com"

# O CDN não exige cookie (a URL é assinada), mas mandar o Referer da origem real
# é o mesmo cuidado que já tomamos com Loom e Vimeo.
REFERER_SKOOL = "https://www.skool.com/"


def eh_url_skool_video(url):
    """True se a URL é o stream HLS de um vídeo hospedado no Skool."""
    return bool(url) and HOST_STREAM in url.lower()


def url_stream_skool(playback_id, token):
    """Monta a URL do master.m3u8 a partir do par que a extensão resolveu.

    Sem o token o CDN responde 403 (medido) — ele não é opcional.
    """
    if not playback_id or not token:
        return None
    return f"https://{HOST_STREAM}/{playback_id}.m3u8?token={token}"


def _diagnosticar(url):
    """Checa o master antes de gastar o yt-dlp, para poder falhar com MOTIVO.

    O token do Skool vale ~24h (medido: `exp` do JWT). Uma fila muito longa pode
    alcançar a expiração, e um 403 engolido viraria mais um buraco silencioso — o
    problema que este projeto documenta como o pior de todos. Então distinguimos
    'token expirado' de 'deu ruim genérico' e dizemos exatamente o que fazer.

    Devolve (pode_seguir, motivo). Erro de rede NÃO bloqueia: deixamos o yt-dlp
    tentar, já que ele tem retry próprio.
    """
    try:
        resposta = requests.get(url, headers={"Referer": REFERER_SKOOL}, timeout=15)
    except Exception as erro:
        print(f"⚠️  Não consegui checar o stream do Skool ({type(erro).__name__}); "
              f"deixando o yt-dlp tentar mesmo assim.")
        return True, None

    # MEDIDO: sem token o CDN devolve 403; com token malformado, 400. Os dois são o
    # mesmo problema para quem está olhando o terminal, então damos a mesma saída
    # acionável em vez de um número de status cru.
    if resposta.status_code in (400, 403):
        return False, (f"token do Skool expirado ou inválido (HTTP {resposta.status_code}). "
                       "Reenfileire o curso pela extensão — as aulas já baixadas "
                       "são puladas automaticamente.")
    if resposta.status_code != 200:
        return False, f"o stream respondeu HTTP {resposta.status_code}"
    if not resposta.text.lstrip().startswith("#EXTM3U"):
        return False, "a resposta não é uma playlist HLS válida"

    return True, None


# Abaixo disto o "arquivo" quase certamente é uma página de erro, não o anexo.
_ANEXO_MINIMO = 64

# NOTA (12/08/2026): havia aqui um `_MAX_NOME_ANEXO = 90`, teto próprio do nome do
# anexo. Ele virou letra morta quando `limpar_nome_arquivo` ganhou `LIMITE_NOME = 80`:
# o corte de 80 acontecia ANTES e o 90 nunca chegava a valer. Dois tetos para a mesma
# coisa só ficam de acordo até um dos dois mudar — o teto agora é só o de utils.py.


# NOTA (12/08/2026): havia aqui um `_nome_do_anexo` que prefixava o anexo com o nome
# da aula (`<Aula> - <arquivo.ext>`). Ele existia para um risco real: anexos SOLTOS no
# módulo podiam colidir entre aulas vizinhas e um sobrescrevia o outro em silêncio.
# Desde que toda aula ganhou pasta própria, dois anexos de aulas diferentes nunca
# dividem o mesmo diretório, e o prefixo virou ramo morto — removido junto com o
# parâmetro `prefixar`, que só tinha um chamador e sempre passava False.


def baixar_anexos(anexos, pasta_relativa_destino):
    """Baixa os arquivos anexos de uma aula. Devolve (baixados, falhas).

    As URLs já vêm assinadas pela extensão (só ela tem a sessão do Skool) e NÃO
    precisam de cookie — medido. Aqui é download puro.
    """
    if not anexos:
        return 0, 0

    pasta_rel = pasta_relativa_destino[1:] \
        if pasta_relativa_destino.startswith(os.sep) else pasta_relativa_destino
    pasta_abs = os.path.join(PASTA_OUTPUT, pasta_rel)
    os.makedirs(pasta_abs, exist_ok=True)

    baixados = falhas = 0
    for anexo in anexos:
        url = (anexo or {}).get("url")
        nome = (anexo or {}).get("nome") or "anexo"
        if not url:
            falhas += 1
            continue

        # O anexo mora na pasta da aula, então guarda o nome original. O teto ainda
        # vale: o caminho já carrega Comunidade/Curso/Módulo/Aula e o Windows corta
        # em 260 — um nome longo estouraria o limite DEPOIS de baixar os bytes.
        #
        # `cortar_preservando_extensao` e NÃO `limpar_nome_arquivo`: sem a extensão o
        # Windows não abre o arquivo. Ver a regressão registrada em utils.py.
        nome_final = cortar_preservando_extensao(nome)
        destino = os.path.join(pasta_abs, nome_final)

        # Retomada: anexo já baixado não é rebaixado (mesma política do .mp4).
        if os.path.exists(destino) and os.path.getsize(destino) > _ANEXO_MINIMO:
            baixados += 1
            continue

        try:
            with requests.get(url, headers={"Referer": REFERER_SKOOL},
                              stream=True, timeout=60) as r:
                if r.status_code != 200:
                    motivo = ("URL do anexo expirada (HTTP 403) — reenfileire o curso"
                              if r.status_code == 403 else f"HTTP {r.status_code}")
                    print(f"❌ Anexo não baixou ({motivo}): {nome}")
                    falhas += 1
                    continue
                with open(destino, "wb") as arq:
                    for pedaco in r.iter_content(chunk_size=8192):
                        arq.write(pedaco)
        except Exception as erro:
            print(f"❌ Anexo falhou ({type(erro).__name__}): {nome}")
            falhas += 1
            continue

        # Um arquivo minúsculo aqui é quase sempre página de erro salva como anexo.
        if os.path.getsize(destino) <= _ANEXO_MINIMO:
            os.remove(destino)
            print(f"❌ Anexo veio vazio/inválido e foi descartado: {nome}")
            falhas += 1
            continue

        baixados += 1
        print(f"📎 Anexo salvo: {os.path.basename(destino)}")

    return baixados, falhas


def baixar_skool(url, pasta_relativa_destino, nome_arquivo, callback=None,
                 ao_converter=None, ao_fase=None):
    """Baixa um vídeo hospedado no Skool a partir da URL do `.m3u8`.

    Devolve True/False. Toda falha é impressa com motivo — nunca engolida.
    """
    pode, motivo = _diagnosticar(url)
    if not pode:
        print(f"❌ Vídeo do Skool não baixou — {motivo} | aula: '{nome_arquivo}'")
        return False

    return baixar_com_ytdlp(url, pasta_relativa_destino, nome_arquivo,
                            callback=callback, referer=REFERER_SKOOL,
                            ao_converter=ao_converter, ao_fase=ao_fase)
