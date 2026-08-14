"""processar_download contra as fixtures, sem rede.

Cobre a seleção de qualidade e a montagem da fila de segmentos — a parte que
hoje é feita com regex em downloader.py e que a Fase 3 vai reescrever.
"""
import os

import pytest

from services import downloader
from conftest import RespostaFalsa

URL_MASTER = "https://luna.loom.com/id/VIDEO/rev/REV/resource/hls/playlist-multibitrate.m3u8?Policy=X"


@pytest.fixture
def rede_falsa(monkeypatch, master_m3u8, playlist_video, playlist_audio):
    """Serve as fixtures conforme a URL pedida e registra o que foi requisitado."""
    pedidos = []

    def get_falso(url, *args, **kwargs):
        pedidos.append(url)
        if "playlist-multibitrate" in url:
            return RespostaFalsa(master_m3u8)
        if "mediaplaylist-audio" in url:
            return RespostaFalsa(playlist_audio)
        if "mediaplaylist-video" in url:
            return RespostaFalsa(playlist_video)
        # qualquer .ts: devolve bytes de mentira
        return RespostaFalsa(conteudo=b"\x00" * 128)

    monkeypatch.setattr(downloader.requests, "get", get_falso)
    return pedidos


@pytest.fixture
def temp(tmp_path, monkeypatch):
    """Isola output e pasta temporária dentro do tmp do pytest."""
    monkeypatch.setattr(downloader, "PASTA_OUTPUT", str(tmp_path / "output"))
    return str(tmp_path / "trabalho")


def test_download_completa(rede_falsa, temp):
    assert downloader.processar_download(URL_MASTER, temp, "Aula", "Curso") == (True, None)


def test_escolhe_a_maior_qualidade(rede_falsa, temp):
    """O master tem BANDWIDTH 1500000 e 3200000 — tem que pegar o de 3200."""
    downloader.processar_download(URL_MASTER, temp, "Aula", "Curso")

    pedidos_video = [u for u in rede_falsa if "mediaplaylist-video" in u]
    assert len(pedidos_video) == 1
    assert "bitrate3200" in pedidos_video[0]
    assert "bitrate1500" not in pedidos_video[0]


def test_baixa_video_e_audio(rede_falsa, temp):
    """Sem esta parte o vídeo final sai mudo."""
    downloader.processar_download(URL_MASTER, temp, "Aula", "Curso")

    assert any("mediaplaylist-video" in u for u in rede_falsa)
    assert any("mediaplaylist-audio" in u for u in rede_falsa)


def test_enfileira_todos_os_segmentos(rede_falsa, temp):
    """33 de vídeo + 42 de áudio = 75."""
    contagem = {"total": 0}

    def progresso(total=None):
        if total is not None:
            contagem["total"] = total

    downloader.processar_download(URL_MASTER, temp, "Aula", "Curso", progresso)
    assert contagem["total"] == 75


def test_grava_as_playlists_para_o_ffmpeg(rede_falsa, temp):
    """O FFmpeg lê estes arquivos locais na hora de juntar tudo."""
    downloader.processar_download(URL_MASTER, temp, "Aula", "Curso")

    gravados = os.listdir(temp)
    assert "master.m3u8" in gravados
    assert any(n.startswith("mediaplaylist-video") for n in gravados)
    assert any(n.startswith("mediaplaylist-audio") for n in gravados)


def test_pula_quando_o_mp4_ja_existe(rede_falsa, temp, tmp_path):
    """Proteção contra rebaixar o mesmo vídeo (downloader.py:63)."""
    destino = tmp_path / "output" / "Curso"
    destino.mkdir(parents=True)
    (destino / "Aula.mp4").write_bytes(b"\x00" * 2_000_000)  # > 1 MB

    assert downloader.processar_download(URL_MASTER, temp, "Aula", "Curso") == (True, None)
    assert rede_falsa == [], "não deveria ter feito nenhuma requisição"


def test_arquivo_pequeno_nao_conta_como_pronto(rede_falsa, temp, tmp_path):
    """Abaixo de 1 MB é tratado como truncado e baixado de novo."""
    destino = tmp_path / "output" / "Curso"
    destino.mkdir(parents=True)
    (destino / "Aula.mp4").write_bytes(b"\x00" * 500_000)  # < 1 MB

    downloader.processar_download(URL_MASTER, temp, "Aula", "Curso")
    assert rede_falsa != [], "deveria ter baixado de novo"


def test_master_sem_audio_falha(monkeypatch, temp):
    """Sem faixa de áudio o projeto não sabe montar o vídeo — tem que recusar."""
    master_mudo = (
        "#EXTM3U\n"
        "#EXT-X-STREAM-INF:BANDWIDTH=1500000,RESOLUTION=1272x720\n"
        "mediaplaylist-video-bitrate1500.m3u8\n"
    )
    monkeypatch.setattr(downloader.requests, "get",
                        lambda *a, **k: RespostaFalsa(master_mudo))

    ok, motivo = downloader.processar_download(URL_MASTER, temp, "Aula", "Curso")
    assert ok is False
    assert "áudio" in motivo, f"o motivo tem que nomear a causa, veio: {motivo!r}"
