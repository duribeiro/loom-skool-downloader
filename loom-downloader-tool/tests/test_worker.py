"""worker_download: os três casos de aula (vídeo+texto, só vídeo, só texto).

Sem rede e sem FFmpeg: o download e a extração são monkeypatchados. O foco é a
orquestração — o que é gravado e qual status final.
"""
import json
import os

import pytest

import routes
from services import texto as mod_texto


@pytest.fixture
def output_isolado(tmp_path, monkeypatch):
    """Aponta a gravação do .md para um output temporário."""
    monkeypatch.setattr(mod_texto, "PASTA_OUTPUT", str(tmp_path))
    return tmp_path


def _item(nome="Aula 1", url=None, folder="Com/Curso/Modulo"):
    return {"nome": nome, "status": "fila", "progresso": 0, "total": 1,
            "url": url, "folder": folder}


DESC = "[v2]" + json.dumps([{"type": "paragraph",
                             "content": [{"type": "text", "text": "corpo da aula"}]}])
RESOURCES = json.dumps([{"title": "Prompts", "link": "https://x"}])


def test_aula_so_texto_grava_md_e_da_sucesso(output_isolado):
    item = _item(url="")  # sem vídeo
    routes.worker_download("", item["folder"], item["nome"], item, DESC, RESOURCES)

    md = output_isolado / "Com" / "Curso" / "Modulo" / "Aula 1.md"
    assert md.exists()
    conteudo = md.read_text(encoding="utf-8")
    assert "corpo da aula" in conteudo
    assert "[Prompts](https://x)" in conteudo
    assert item["status"] == "sucesso"


def test_aula_so_texto_sem_conteudo_da_erro(output_isolado):
    """Sem vídeo e sem texto não há o que salvar — status erro."""
    item = _item(url="")
    routes.worker_download("", item["folder"], item["nome"], item, None, None)

    assert item["status"] == "erro"
    assert not any(output_isolado.rglob("*.md"))


def test_aula_video_mais_texto(output_isolado, monkeypatch):
    """Grava o .md e baixa o vídeo."""
    monkeypatch.setattr(routes, "extrair_metadados",
                        lambda url: ("titulo", "https://loom/x.m3u8"))
    monkeypatch.setattr(routes, "processar_download",
                        lambda *a, **k: True)
    monkeypatch.setattr(routes, "converter_final", lambda *a, **k: True)
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)

    item = _item(url="https://www.loom.com/embed/abc")
    routes.worker_download(item["url"], item["folder"], item["nome"], item, DESC, RESOURCES)

    md = output_isolado / "Com" / "Curso" / "Modulo" / "Aula 1.md"
    assert md.exists()
    assert item["status"] == "sucesso"


def test_aula_so_video_nao_grava_md(output_isolado, monkeypatch):
    monkeypatch.setattr(routes, "extrair_metadados",
                        lambda url: ("titulo", "https://loom/x.m3u8"))
    monkeypatch.setattr(routes, "processar_download", lambda *a, **k: True)
    monkeypatch.setattr(routes, "converter_final", lambda *a, **k: True)
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)

    item = _item(url="https://www.loom.com/embed/abc")
    routes.worker_download(item["url"], item["folder"], item["nome"], item, None, None)

    assert not any(output_isolado.rglob("*.md"))
    assert item["status"] == "sucesso"


def test_video_falha_status_erro(output_isolado, monkeypatch):
    """Se o texto grava mas o vídeo falha, o status reflete a falha do vídeo."""
    monkeypatch.setattr(routes, "extrair_metadados", lambda url: ("t", None))
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)

    item = _item(url="https://www.loom.com/embed/abc")
    routes.worker_download(item["url"], item["folder"], item["nome"], item, DESC, RESOURCES)

    # o .md foi gravado mesmo assim (não se perde o texto)
    assert (output_isolado / "Com" / "Curso" / "Modulo" / "Aula 1.md").exists()
    assert item["status"] == "erro"
