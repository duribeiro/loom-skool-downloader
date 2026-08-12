"""Configuração compartilhada dos testes.

Coloca `server/` no sys.path (mesma coisa que `python server/app.py` faz
automaticamente) e expõe as fixtures congeladas do Loom.
"""
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# `services` e `routes` são importados como módulos top-level pelo projeto
sys.path.insert(0, os.path.join(RAIZ, "server"))


@pytest.fixture(autouse=True)
def _log_de_erros_isolado(tmp_path, monkeypatch):
    """Nenhum teste escreve no `logs/erros.log` do projeto.

    MEDIDO: sem isto, os testes do worker chamavam `_marcar_erro` de verdade e
    deixavam 4 linhas de fixture ("Aula 1", "boom no meio do download") no log real
    — que é justamente onde alguém vai procurar um erro DE VERDADE depois.
    `autouse` porque a poluição vem de testes que nem falam de log.
    """
    from services import registro
    monkeypatch.setattr(registro, "PASTA_LOGS", str(tmp_path / "logs"))
    monkeypatch.setattr(registro, "ARQUIVO_ERROS", str(tmp_path / "logs" / "erros.log"))


def ler_fixture(nome):
    """Lê uma fixture congelada como texto."""
    with open(os.path.join(PASTA_FIXTURES, nome), encoding="utf-8") as arquivo:
        return arquivo.read()


@pytest.fixture
def html_embed():
    """HTML real da página de embed do Loom (credenciais sanitizadas)."""
    return ler_fixture("loom_embed.html")


@pytest.fixture
def master_m3u8():
    """Playlist master real: 2 qualidades de vídeo + 1 faixa de áudio."""
    return ler_fixture("master.m3u8")


@pytest.fixture
def playlist_video():
    """Mediaplaylist de vídeo real: 33 segmentos."""
    return ler_fixture("mediaplaylist-video.m3u8")


@pytest.fixture
def playlist_audio():
    """Mediaplaylist de áudio real: 42 segmentos."""
    return ler_fixture("mediaplaylist-audio.m3u8")


class RespostaFalsa:
    """Imita o mínimo de `requests.Response` que o projeto usa."""

    def __init__(self, texto="", status=200, conteudo=b""):
        self.text = texto
        self.status_code = status
        self._conteudo = conteudo

    def iter_content(self, chunk_size=8192):
        yield self._conteudo

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False
