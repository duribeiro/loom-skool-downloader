"""Testes que batem no Loom DE VERDADE.

POR QUE ISTO EXISTE, e por que fixture não substitui:

    Uma fixture está congelada. Se o Loom mudar o formato da página amanhã, os
    testes de fixture continuam verdes para sempre — o projeto quebrado e a
    suíte passando. Foi exatamente o que aconteceu quando eles renomearam
    "playlist.m3u8" para "playlist-multibitrate.m3u8".

    Fixture protege contra NÓS quebrarmos o código.
    Este arquivo protege contra ELES mudarem a página.

Excluídos da execução padrão (ver pytest.ini) porque dependem de internet e de
o Loom estar no ar. Rode de propósito:

    pytest -m rede -v

Vale rodar antes de uma sessão longa de downloads, ou quando algo parar de
funcionar sem motivo aparente.
"""
import pytest

from services import utils

pytestmark = pytest.mark.rede

VIDEO_PUBLICO = "https://www.loom.com/embed/7a0abb7d8ae14ab480f963cc2f49ec67"


def test_a_pagina_do_loom_ainda_responde():
    resposta = utils.requests.get(VIDEO_PUBLICO, headers=utils.HEADERS, timeout=20)
    assert resposta.status_code == 200
    assert len(resposta.text) > 1000


def test_ainda_conseguimos_extrair_a_url_do_stream():
    """SE ESTE TESTE FALHAR: o Loom mudou a página. Não é bug nosso — é
    manutenção. Baixe o HTML novo, veja o que mudou e atualize a extração
    junto com a fixture em tests/fixtures/loom_embed.html."""
    titulo, url = utils.extrair_metadados(VIDEO_PUBLICO)

    assert titulo, "não conseguiu extrair o título"
    assert url is not None, (
        "não conseguiu extrair a URL do .m3u8 da página real do Loom. "
        "Provavelmente eles mudaram o formato da página."
    )
    assert ".m3u8" in url


def test_a_playlist_realmente_baixa():
    """Extrair a URL não basta: ela precisa servir conteúdo HLS de verdade."""
    _, url = utils.extrair_metadados(VIDEO_PUBLICO)
    assert url, "sem URL não dá para testar o download"

    resposta = utils.requests.get(url, headers=utils.HEADERS, timeout=20)
    assert resposta.status_code == 200
    assert resposta.text.startswith("#EXTM3U"), "não veio uma playlist HLS válida"


def test_a_playlist_tem_video_e_audio():
    """Se o áudio sumir da playlist, o .mp4 sai mudo — e hoje isso seria
    silencioso."""
    _, url = utils.extrair_metadados(VIDEO_PUBLICO)
    assert url
    master = utils.requests.get(url, headers=utils.HEADERS, timeout=20).text

    assert "#EXT-X-STREAM-INF" in master, "nenhum stream de vídeo na playlist"
    assert "TYPE=AUDIO" in master, "nenhuma faixa de áudio na playlist"
