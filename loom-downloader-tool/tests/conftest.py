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
def _output_isolado_sempre(tmp_path, monkeypatch):
    """NENHUM teste escreve na `output/` de verdade.

    MEDIDO em 13/08/2026: a biblioteca real ficou com `Com/Curso/Modulo/Aula 1` e
    `Com/Curso/Modulo/Meu Video` — nomes de FIXTURE. A causa foi minha: ao mover a
    criação da pasta para dentro da trava de caminho, `worker_download` passou a
    chamar `os.makedirs` com `routes.PASTA_OUTPUT`, e a fixture `output_isolado` só
    trocava o `PASTA_OUTPUT` de `services.texto`.

    `autouse` porque a poluição vem de testes que nem falam de pasta. Testes que
    precisam do caminho real dentro do tmp continuam podendo sobrescrever depois —
    monkeypatch aplicado por último vence.
    """
    import routes
    from services import caminhos, converter, downloader, skool, texto, ytdlp

    for modulo in (routes, caminhos, converter, downloader, skool, texto, ytdlp):
        if hasattr(modulo, "PASTA_OUTPUT"):
            monkeypatch.setattr(modulo, "PASTA_OUTPUT", str(tmp_path / "output"))


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


@pytest.fixture(autouse=True)
def _sem_rede_na_suite_rapida(request, monkeypatch):
    """A suíte rápida não fala com a internet. Quem tentar, quebra AQUI.

    MEDIDO em 14/08/2026: quando o Loom passou a ir por `baixar_loom`, três testes
    continuaram dublando `processar_download` — que aquele caminho não usa mais.
    Eles chamaram o yt-dlp DE VERDADE, tomaram 404 do host de fixture ("abc") e um
    deles PASSOU por causa disso: esperava status 'erro' e o erro veio da rede, não
    do que estava sob teste. Teste que acerta por acidente é pior que teste
    faltando, porque ninguém vai olhar de novo.

    Bloqueio no socket, e não em `requests`, para pegar também o yt-dlp, que tem
    pilha de rede própria. Os testes marcados `rede` são liberados por desenho.
    """
    if request.node.get_closest_marker("rede"):
        return

    import socket

    def recusar(*_a, **_k):
        raise RuntimeError(
            "teste da suíte rápida tentou usar a rede. Provavelmente um dublê está "
            "no lugar errado — confira qual motor a URL do teste realmente aciona."
        )

    monkeypatch.setattr(socket.socket, "connect", recusar)
    monkeypatch.setattr(socket.socket, "connect_ex", recusar)
    monkeypatch.setattr(socket, "create_connection", recusar)


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
