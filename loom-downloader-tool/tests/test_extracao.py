"""extrair_metadados contra a fixture congelada do Loom, sem rede.

Estes testes travam o comportamento ANTES da reescrita da Fase 3. Eles devem
continuar verdes depois dela — é isso que prova que a reescrita não mudou o
contrato, só a implementação.
"""
import pytest

from services import utils
from conftest import RespostaFalsa

URL_QUALQUER = "https://www.loom.com/embed/7a0abb7d8ae14ab480f963cc2f49ec67"
TITULO_ESPERADO = "Introdução ao Programa Gang e Dinâmica de Implementação"


@pytest.fixture
def sem_rede(monkeypatch):
    """Faz requests.get devolver o texto que o teste escolher."""
    def instalar(texto):
        monkeypatch.setattr(utils.requests, "get",
                            lambda *a, **k: RespostaFalsa(texto))
    return instalar


def test_extrai_titulo(sem_rede, html_embed):
    sem_rede(html_embed)
    titulo, _ = utils.extrair_metadados(URL_QUALQUER)
    assert titulo == TITULO_ESPERADO


def test_extrai_url_do_stream(sem_rede, html_embed):
    sem_rede(html_embed)
    _, url = utils.extrair_metadados(URL_QUALQUER)
    assert url is not None, "não achou a URL do .m3u8 na página"
    assert url.startswith("https://")
    assert ".m3u8" in url


def test_url_extraida_nao_tem_escape_de_json(sem_rede, html_embed):
    sem_rede(html_embed)
    _, url = utils.extrair_metadados(URL_QUALQUER)
    assert "\\/" not in url, "as barras escapadas do JSON não foram desfeitas"


# --- O bug que derrubou o projeto -------------------------------------------
# O Loom renomeou "playlist.m3u8" para "playlist-multibitrate.m3u8" e a extração
# parou de funcionar, silenciosamente. Estes dois testes existem para que isso
# não volte a acontecer.

def test_nao_exige_o_nome_literal_playlist_ponto_m3u8(sem_rede, html_embed):
    """A fixture atual usa 'playlist-multibitrate.m3u8'."""
    assert "playlist-multibitrate.m3u8" in html_embed
    assert '"playlist.m3u8"' not in html_embed

    sem_rede(html_embed)
    _, url = utils.extrair_metadados(URL_QUALQUER)
    assert url is not None, "voltou a exigir o nome literal 'playlist.m3u8'"


@pytest.mark.parametrize("nome_novo", [
    "playlist.m3u8",
    "playlist-multibitrate.m3u8",
    "playlist-v2.m3u8",
    "stream-principal.m3u8",
    "qualquer-nome-que-o-loom-inventar.m3u8",
])
def test_sobrevive_a_rename_do_arquivo_pelo_loom(sem_rede, html_embed, nome_novo):
    """Se o Loom renomear de novo, a extração não pode quebrar."""
    html_alterado = html_embed.replace("playlist-multibitrate.m3u8", nome_novo)

    sem_rede(html_alterado)
    _, url = utils.extrair_metadados(URL_QUALQUER)

    assert url is not None, f"quebrou quando o arquivo virou '{nome_novo}'"
    assert nome_novo in url


def test_pagina_sem_stream_devolve_none_sem_explodir(sem_rede):
    sem_rede("<html><title>Nada aqui | Loom</title></html>")
    titulo, url = utils.extrair_metadados(URL_QUALQUER)
    assert url is None
    assert titulo == "Nada aqui"


def test_erro_de_rede_nao_propaga_excecao(monkeypatch):
    def explodir(*a, **k):
        raise ConnectionError("rede caiu")
    monkeypatch.setattr(utils.requests, "get", explodir)

    assert utils.extrair_metadados(URL_QUALQUER) == (None, None)
