"""Vimeo: detecção de URL, normalização para a URL do player, e propagação do
Referer (que é o que libera o Vimeo privado do Skool). yt-dlp mockado, sem rede.
"""
import pytest

from services import vimeo as mod_vimeo
from services import ytdlp as mod_engine


@pytest.fixture
def output_isolado(tmp_path, monkeypatch):
    monkeypatch.setattr(mod_engine, "PASTA_OUTPUT", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize("url", [
    "https://vimeo.com/1212858408",
    "https://player.vimeo.com/video/1212858408?app_id=122963",
    "https://vimeo.com/video/1212858408",
])
def test_reconhece_vimeo(url):
    assert mod_vimeo.eh_url_vimeo(url) is True


@pytest.mark.parametrize("url", ["https://www.youtube.com/watch?v=x", "", None])
def test_nao_confunde(url):
    assert mod_vimeo.eh_url_vimeo(url) is False


@pytest.mark.parametrize("entrada", [
    "https://vimeo.com/1212858408",
    "https://player.vimeo.com/video/1212858408?app_id=122963",
    "https://vimeo.com/video/1212858408",
])
def test_normaliza_para_url_do_player(entrada):
    assert mod_vimeo.url_player_vimeo(entrada) == "https://player.vimeo.com/video/1212858408"


def test_baixar_vimeo_passa_referer_e_url_do_player(output_isolado, monkeypatch):
    """O referer tem de chegar no http_headers do yt-dlp, e a URL vira a do player."""
    capturado = {}

    class FakeYDL:
        def __init__(self, opcoes):
            capturado["opcoes"] = opcoes

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def download(self, urls):
            capturado["urls"] = urls
            caminho = capturado["opcoes"]["outtmpl"].replace("%(ext)s", "mp4")
            with open(caminho, "wb") as f:
                f.write(b"0" * 200_000)

    monkeypatch.setattr(mod_engine.yt_dlp, "YoutubeDL", FakeYDL)

    ok = mod_vimeo.baixar_vimeo("https://vimeo.com/1212858408", "Com/Post",
                                "Mini Workshop", referer="https://www.skool.com/x/post")
    assert ok is True
    assert (output_isolado / "Com" / "Post" / "Mini Workshop.mp4").exists()
    assert capturado["urls"] == ["https://player.vimeo.com/video/1212858408"]
    assert capturado["opcoes"]["http_headers"] == {"Referer": "https://www.skool.com/x/post"}


def test_titulo_do_vimeo_usa_referer(monkeypatch):
    capturado = {}

    class FakeYDL:
        def __init__(self, opcoes):
            capturado["opcoes"] = opcoes

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            capturado["url"] = url
            return {"title": "Tesouro Escondido"}

    monkeypatch.setattr(mod_engine.yt_dlp, "YoutubeDL", FakeYDL)

    titulo = mod_vimeo.titulo_do_vimeo("https://vimeo.com/1212858408",
                                       referer="https://www.skool.com/x/post")
    assert titulo == "Tesouro Escondido"
    assert capturado["url"] == "https://player.vimeo.com/video/1212858408"
    assert capturado["opcoes"]["http_headers"] == {"Referer": "https://www.skool.com/x/post"}
