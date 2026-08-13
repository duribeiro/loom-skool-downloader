"""Engine de download via yt-dlp, compartilhada por YouTube e Vimeo.

O yt-dlp resolve formatos adaptativos, cifragem e fusão (com ffmpeg) de dezenas de
sites. YouTube e Vimeo usam a MESMA lógica aqui; a única diferença é o `referer`:
o Vimeo privado embutido no Skool só libera o vídeo se a requisição vier com o
`Referer` do domínio autorizado (a página do Skool).

Decisão (plano A1.3): **melhor qualidade EM .mp4**. O seletor pega o melhor vídeo
(av1/vp9/h264) + o melhor áudio **aac** (`m4a`) e funde num `.mp4`. Áudio aac garante
que o arquivo toque em qualquer player — opus dentro de mp4 é aceito pelo container
mas emudece em vários players. Vídeo av1/vp9 em mp4 é remuxado sem recodificar.
"""
import os
import uuid

import yt_dlp

from .utils import limpar_nome_arquivo
from .caminhos import PASTA_OUTPUT

# Melhor vídeo + melhor áudio AAC, fundidos em mp4. Fallback: melhor combinação.
FORMATO_MELHOR_MP4 = "bv*+ba[ext=m4a]/bv*+ba/b"

# Abaixo disto, consideramos que o arquivo não é um vídeo de verdade (erro/HTML).
_TAMANHO_MINIMO = 100_000

# Cada etapa ocupa uma FAIXA da barra, em vez de os 100% inteiros.
#
# Antes, cada faixa do yt-dlp enchia a barra até 100%: no fim do vídeo ela ficava
# cheia e PARADA durante todo o áudio e a conversão, o que parece travamento. Já
# levou o dono do projeto a quase matar o servidor no meio de 400 MB baixados.
#
# Com faixas, 100% passa a significar PRONTO e nada mais. Etapa que não existir
# (vídeo com faixa única) faz a barra saltar para frente — salto é movimento, e
# movimento não engana. A conversão fica com 85..99 (`FAIXA_CONVERSAO` em routes).
FAIXA_DA_FASE = {
    "baixando video": (0, 45),
    "baixando audio": (45, 85),
    "baixando": (0, 85),        # faixa única, já com áudio e vídeo juntos
}


class _LogadorSilencioso:
    """Engole a saída do yt-dlp.

    O dashboard (Rich Live) pinta a tela inteira; qualquer escrita direta no stdout
    vinda das threads de download aparece por um quadro e some no repaint seguinte,
    fazendo a tela tremer. Erros que importam já são impressos pelo chamador, com
    contexto de qual aula falhou — que a mensagem crua do yt-dlp não traz.
    """

    def debug(self, msg): pass

    def info(self, msg): pass

    def warning(self, msg): pass

    def error(self, msg): pass


def _normalizar_pasta_relativa(pasta_relativa):
    return pasta_relativa[1:] if pasta_relativa.startswith(os.sep) else pasta_relativa


def _limpar_temporarios(pasta, base):
    """Remove qualquer sobra do download temporário (.part, .webm, .mp4...)."""
    try:
        for nome in os.listdir(pasta):
            if nome.startswith(base):
                try:
                    os.remove(os.path.join(pasta, nome))
                except OSError:
                    pass
    except OSError:
        pass


def _headers(referer):
    return {"Referer": referer} if referer else None


def titulo_via_ytdlp(url, referer=None):
    """Descobre o título do vídeo sem baixá-lo (metadados via yt-dlp).

    Usado quando o pedido vem sem nome. Em caso de falha devolve um nome
    genérico — nunca estoura, para não derrubar o worker.
    """
    opcoes = {"quiet": True, "no_warnings": True, "skip_download": True,
              "noprogress": True, "logger": _LogadorSilencioso()}
    cabecalhos = _headers(referer)
    if cabecalhos:
        opcoes["http_headers"] = cabecalhos
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(url, download=False)
        return (info or {}).get("title") or "video"
    except Exception as erro:
        print(f"⚠️  Não consegui o título ({type(erro).__name__}); usando genérico.")
        return "video"


def canal_via_ytdlp(url, referer=None):
    """Nome do canal/uploader do vídeo, para organizar em pastas (YouTube/<Canal>/).

    Metadados apenas (sem baixar). Devolve '' se falhar — o chamador então grava
    direto na pasta raiz, sem subpasta de canal. Nunca estoura.
    """
    opcoes = {"quiet": True, "no_warnings": True, "skip_download": True,
              "noprogress": True, "logger": _LogadorSilencioso()}
    cabecalhos = _headers(referer)
    if cabecalhos:
        opcoes["http_headers"] = cabecalhos
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(url, download=False)
        info = info or {}
        return info.get("channel") or info.get("uploader") or ""
    except Exception as erro:
        print(f"⚠️  Não consegui o canal ({type(erro).__name__}); sem subpasta de canal.")
        return ""


def baixar_com_ytdlp(url, pasta_relativa_destino, nome_arquivo, callback=None,
                     referer=None, ao_converter=None, ao_fase=None):
    """Baixa um vídeo na melhor qualidade em .mp4 via yt-dlp.

    `referer`, quando dado, vai no header — é o que libera Vimeo privado do Skool.
    Grava direto no destino final. Devolve True se o .mp4 final existir; False em
    qualquer falha — e a falha é **visível** no terminal, nunca engolida.

    `ao_converter` é chamado quando o yt-dlp entra no pós-processamento (a fusão
    vídeo+áudio pelo ffmpeg). Sem isso o painel mostrava a barra em 100% ainda
    rotulada "Baixando" durante todo o merge — que em vídeo longo demora, e passava
    a impressão de travamento. Só o caminho do Loom sinalizava "convertendo".
    """
    pasta_relativa = _normalizar_pasta_relativa(pasta_relativa_destino)
    pasta_destino_abs = os.path.join(PASTA_OUTPUT, pasta_relativa)
    os.makedirs(pasta_destino_abs, exist_ok=True)

    nome_limpo = limpar_nome_arquivo(nome_arquivo)
    caminho_final = os.path.join(pasta_destino_abs, f"{nome_limpo}.mp4")

    # Pular se já existe (mesma política do caminho do Loom).
    if os.path.exists(caminho_final) and os.path.getsize(caminho_final) > 1_000_000:
        print(f"⚠️  Já existe, download pulado: {nome_limpo}.mp4")
        return True

    # Progresso: mapeia o percentual do yt-dlp para a faixa da barra no dashboard.
    def _hook(d):
        if d.get("status") != "downloading":
            return

        # QUAL FAIXA ESTÁ BAIXANDO. O yt-dlp trata vídeo e áudio como downloads
        # SEPARADOS, um depois do outro, e o `info_dict` diz qual é qual: faixa
        # sem vídeo tem `vcodec == "none"`, faixa sem áudio tem `acodec == "none"`.
        #
        # Isso alimenta duas coisas: o RÓTULO da fase no painel e a FAIXA da barra
        # (ver FAIXA_DA_FASE). Sem essa distinção o painel dizia só "Baixando" e a
        # barra enchia no fim do vídeo, ficando parada durante todo o áudio.
        info = d.get("info_dict") or {}
        if info.get("vcodec") == "none":
            fase = "baixando audio"
        elif info.get("acodec") == "none":
            fase = "baixando video"
        else:
            fase = "baixando"       # faixa única, já com áudio e vídeo

        # ETA vem pronto do yt-dlp, em segundos, e é por FAIXA — não é o tempo
        # total até o .mp4 final. Melhor um número honesto de escopo limitado do
        # que uma estimativa global inventada.
        if ao_fase:
            ao_fase(fase, d.get("eta"))

        if not callback:
            return

        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        baixado = d.get("downloaded_bytes") or 0
        if not total:
            return

        # Percentual da AULA inteira, não da faixa: a fração desta faixa mapeada
        # dentro do trecho da barra que pertence a ela.
        inicio, fim = FAIXA_DA_FASE.get(fase, FAIXA_DA_FASE["baixando"])
        fracao = max(0.0, min(1.0, baixado / total))
        callback(percentual=inicio + fracao * (fim - inicio))

    # Nome TEMPORÁRIO fixo (sem o título do usuário) + rename: blinda contra título
    # com '%' (template do outtmpl) e contra colisão entre downloads simultâneos.
    base_temp = f"._yt_{uuid.uuid4().hex}"
    opcoes = {
        "format": FORMATO_MELHOR_MP4,
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(pasta_destino_abs, base_temp + ".%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # `quiet` NÃO desliga a barra de progresso — ela continua sendo reescrita no
        # stdout e briga com o dashboard pelo controle da tela (a linha "[download]
        # 42% at 1.2MiB/s" piscando, e o painel inteiro repintando junto).
        # `noprogress` é quem cala a barra; o progresso real chega pelo progress_hook.
        "noprogress": True,
        # Rede de segurança: qualquer outra mensagem do yt-dlp também sai do stdout.
        "logger": _LogadorSilencioso(),
        "progress_hooks": [_hook],
    }

    if ao_converter:
        # 'started' dispara ao entrar em cada pós-processador (o Merger é um deles).
        # Guardamos para avisar UMA vez: são vários PPs por download.
        avisado = {"sim": False}

        def _pp_hook(d):
            if d.get("status") == "started" and not avisado["sim"]:
                avisado["sim"] = True
                try:
                    ao_converter()
                except Exception:
                    pass   # o painel nunca pode derrubar o download

        opcoes["postprocessor_hooks"] = [_pp_hook]

    cabecalhos = _headers(referer)
    if cabecalhos:
        opcoes["http_headers"] = cabecalhos

    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            ydl.download([url])
    except Exception as erro:
        print(f"❌ yt-dlp falhou em '{nome_limpo}': {type(erro).__name__}: {erro}")
        _limpar_temporarios(pasta_destino_abs, base_temp)
        return False

    caminho_temp_mp4 = os.path.join(pasta_destino_abs, base_temp + ".mp4")
    if os.path.exists(caminho_temp_mp4) and os.path.getsize(caminho_temp_mp4) > _TAMANHO_MINIMO:
        os.replace(caminho_temp_mp4, caminho_final)  # sobrescreve um parcial anterior
        print(f"✅ SUCESSO: {nome_limpo}.mp4")
        return True

    _limpar_temporarios(pasta_destino_abs, base_temp)
    print(f"❌ yt-dlp terminou mas o .mp4 esperado não apareceu: {nome_limpo}.mp4")
    return False
