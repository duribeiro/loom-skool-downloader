"""Baixa vídeos do YouTube via yt-dlp, na melhor qualidade em .mp4.

Caminho paralelo ao do Loom: enquanto downloader.py + converter.py resolvem o HLS
do Loom, aqui o yt-dlp cuida do YouTube — formatos adaptativos, cifragem de
assinatura e throttling que mudam toda semana e são o motivo de o yt-dlp existir.
O yt-dlp usa o próprio ffmpeg para fundir vídeo + áudio.

Decisão (plano A1.3): **melhor qualidade EM .mp4**. O seletor pega o melhor vídeo
(av1/vp9/h264) + o melhor áudio **aac** (`m4a`) e funde num `.mp4`. Áudio aac garante
que o arquivo toque em qualquer player — opus dentro de mp4 é aceito pelo container
mas emudece em vários players (QuickTime, TVs). Vídeo av1/vp9 em mp4 é remuxado sem
recodificar, então não há perda nem lentidão.
"""
import os
import uuid

import yt_dlp

from .utils import limpar_nome_arquivo
from .caminhos import PASTA_OUTPUT

# Melhor vídeo + melhor áudio AAC, fundidos em mp4. Fallback: melhor combinação
# disponível (raro no YouTube, que quase sempre entrega streams separados).
FORMATO_MELHOR_MP4 = "bv*+ba[ext=m4a]/bv*+ba/b"

# Abaixo disto, consideramos que o arquivo não é um vídeo de verdade (erro/HTML).
_TAMANHO_MINIMO = 100_000


def eh_url_youtube(url):
    """True se a URL é do YouTube (watch, embed, youtu.be, shorts)."""
    if not url:
        return False
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u


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


def baixar_youtube(url, pasta_relativa_destino, nome_arquivo, callback=None):
    """Baixa um vídeo do YouTube na melhor qualidade em .mp4.

    Grava direto no destino final (o yt-dlp já funde com ffmpeg). Devolve True se o
    .mp4 final existir ao fim; False em qualquer falha — e a falha é **visível** no
    terminal, nunca engolida em silêncio.
    """
    pasta_relativa = _normalizar_pasta_relativa(pasta_relativa_destino)
    pasta_destino_abs = os.path.join(PASTA_OUTPUT, pasta_relativa)
    os.makedirs(pasta_destino_abs, exist_ok=True)

    nome_limpo = limpar_nome_arquivo(nome_arquivo)
    caminho_final = os.path.join(pasta_destino_abs, f"{nome_limpo}.mp4")

    # Pular se já existe (mesma política do caminho do Loom): não rebaixa o que já
    # está no destino acima de 1 MB.
    if os.path.exists(caminho_final) and os.path.getsize(caminho_final) > 1_000_000:
        print(f"⚠️  Já existe, download do YouTube pulado: {nome_limpo}.mp4")
        return True

    # Progresso: mapeia o percentual do yt-dlp para o mesmo callback de barra do
    # dashboard (total=100, incrementa até o percentual atual). Não é exato durante
    # a fusão de dois streams, mas dá movimento visível sem quebrar nada.
    estado = {"reportou_total": False, "ultimo_pct": 0}

    def _hook(d):
        if not callback:
            return
        if d.get("status") != "downloading":
            return
        if not estado["reportou_total"]:
            callback(total=100)
            estado["reportou_total"] = True
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        baixado = d.get("downloaded_bytes") or 0
        if not total:
            return
        pct = int(baixado * 100 / total)
        while estado["ultimo_pct"] < pct <= 100:
            estado["ultimo_pct"] += 1
            callback()

    # Baixa para um nome TEMPORÁRIO fixo (sem o título do usuário) e só depois
    # renomeia para o destino. Isso blinda contra dois problemas: (a) o título
    # tem caracteres que o outtmpl do yt-dlp interpreta como template (ex.: '%'),
    # e (b) colisão entre downloads simultâneos na mesma pasta (uuid único).
    base_temp = f"._yt_{uuid.uuid4().hex}"
    opcoes = {
        "format": FORMATO_MELHOR_MP4,
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(pasta_destino_abs, base_temp + ".%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_hook],
    }

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
        print(f"✅ SUCESSO (YouTube): {nome_limpo}.mp4")
        return True

    _limpar_temporarios(pasta_destino_abs, base_temp)
    print(f"❌ yt-dlp terminou mas o .mp4 esperado não apareceu: {nome_limpo}.mp4")
    return False
