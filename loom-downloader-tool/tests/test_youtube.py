"""baixar_youtube e eh_url_youtube, sem rede: o yt-dlp é mockado.

Foco: reconhecimento da URL, sucesso grava o .mp4, pular se já existe, e falha
VISÍVEL (retorna False sem estourar) quando o yt-dlp quebra ou não gera arquivo.
"""
import os

import pytest

from services import youtube as mod_yt


@pytest.fixture
def output_isolado(tmp_path, monkeypatch):
    """Aponta PASTA_OUTPUT do módulo youtube para um destino temporário."""
    monkeypatch.setattr(mod_yt, "PASTA_OUTPUT", str(tmp_path))
    return tmp_path


def _instalar_ydl(monkeypatch, *, cria=True, erro=None):
    """Substitui yt_dlp.YoutubeDL por um fake que, ao 'baixar', cria o .mp4
    esperado a partir do outtmpl (ou levanta `erro`, ou não cria nada)."""
    class FakeYDL:
        def __init__(self, opcoes):
            self.opcoes = opcoes

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def download(self, urls):
            if erro:
                raise erro
            if cria:
                caminho = self.opcoes["outtmpl"].replace("%(ext)s", "mp4")
                with open(caminho, "wb") as f:
                    f.write(b"0" * 200_000)  # acima do tamanho mínimo

    monkeypatch.setattr(mod_yt.yt_dlp, "YoutubeDL", FakeYDL)


# --- reconhecimento de URL -----------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=abc123",
    "https://youtu.be/abc123",
    "https://www.youtube.com/embed/abc123",
    "https://www.youtube.com/shorts/abc123",
])
def test_reconhece_youtube(url):
    assert mod_yt.eh_url_youtube(url) is True


@pytest.mark.parametrize("url", [
    "https://www.loom.com/embed/abc",
    "https://www.loom.com/share/abc",
    "",
    None,
])
def test_nao_confunde_com_outros(url):
    assert mod_yt.eh_url_youtube(url) is False


# --- download ------------------------------------------------------------------

def test_sucesso_grava_mp4(output_isolado, monkeypatch):
    _instalar_ydl(monkeypatch, cria=True)
    ok = mod_yt.baixar_youtube("https://youtu.be/abc", "Com/Curso", "Aula 1")
    assert ok is True
    assert (output_isolado / "Com" / "Curso" / "Aula 1.mp4").exists()


def test_pula_se_ja_existe(output_isolado, monkeypatch):
    # Pré-cria um .mp4 grande no destino; o yt-dlp NÃO deve nem ser chamado.
    destino = output_isolado / "Com" / "Curso"
    destino.mkdir(parents=True)
    (destino / "Aula 1.mp4").write_bytes(b"0" * 2_000_000)
    _instalar_ydl(monkeypatch, erro=AssertionError("não deveria baixar de novo"))

    ok = mod_yt.baixar_youtube("https://youtu.be/abc", "Com/Curso", "Aula 1")
    assert ok is True


def test_falha_do_ytdlp_retorna_false(output_isolado, monkeypatch):
    _instalar_ydl(monkeypatch, erro=RuntimeError("bloqueado"))
    ok = mod_yt.baixar_youtube("https://youtu.be/abc", "Com/Curso", "Aula 1")
    assert ok is False


def test_sem_arquivo_final_retorna_false(output_isolado, monkeypatch):
    # yt-dlp "termina" mas não gera o arquivo -> não é sucesso silencioso.
    _instalar_ydl(monkeypatch, cria=False)
    ok = mod_yt.baixar_youtube("https://youtu.be/abc", "Com/Curso", "Aula 1")
    assert ok is False


def test_nome_com_caracteres_proibidos_e_limpo(output_isolado, monkeypatch):
    _instalar_ydl(monkeypatch, cria=True)
    ok = mod_yt.baixar_youtube("https://youtu.be/abc", "Com/Curso", 'Aula: 1? "x"')
    assert ok is True
    # ':', '?' e '"' removidos por limpar_nome_arquivo
    assert (output_isolado / "Com" / "Curso" / "Aula 1 x.mp4").exists()


def test_titulo_com_porcento_nao_quebra(output_isolado, monkeypatch):
    """'%' é válido em nome de arquivo mas é template no outtmpl do yt-dlp.
    Como baixamos num nome temporário e renomeamos, o título passa intacto."""
    _instalar_ydl(monkeypatch, cria=True)
    ok = mod_yt.baixar_youtube("https://youtu.be/abc", "Com/Curso", "50% de desconto")
    assert ok is True
    assert (output_isolado / "Com" / "Curso" / "50% de desconto.mp4").exists()
