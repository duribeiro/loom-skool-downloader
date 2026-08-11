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


def test_aula_vazia_gera_md_placeholder(output_isolado):
    """Aula sem vídeo e sem texto (placeholder do curso) não some: vira um .md
    com o título e uma nota, e conta como sucesso."""
    item = _item(url="")
    routes.worker_download("", item["folder"], item["nome"], item, None, None)

    md = output_isolado / "Com" / "Curso" / "Modulo" / "Aula 1.md"
    assert md.exists()
    conteudo = md.read_text(encoding="utf-8")
    assert "# Aula 1" in conteudo
    assert "não tinha vídeo nem texto" in conteudo
    assert item["status"] == "sucesso"


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

    # Vídeo + texto = 2 artefatos, então a aula ganha PASTA PRÓPRIA
    # (`_quantos_artefatos >= 2`, routes.py:161). Por isso o .md fica em
    # `Modulo/Aula 1/Aula 1.md`, e não solto no módulo como nas aulas de um
    # arquivo só. A decisão é tomada antes do download, pelo que se espera gerar.
    md = output_isolado / "Com" / "Curso" / "Modulo" / "Aula 1" / "Aula 1.md"
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


def test_aula_youtube_roteia_para_ytdlp(output_isolado, monkeypatch):
    """URL de YouTube vai pro baixar_youtube, NÃO pro caminho HLS do Loom."""
    chamado = {"yt": False, "loom": False}
    monkeypatch.setattr(routes, "baixar_youtube",
                        lambda *a, **k: chamado.__setitem__("yt", True) or True)
    monkeypatch.setattr(routes, "processar_download",
                        lambda *a, **k: chamado.__setitem__("loom", True) or True)
    monkeypatch.setattr(routes, "extrair_metadados", lambda url: ("t", "m3u8"))
    monkeypatch.setattr(routes, "converter_final", lambda *a, **k: True)
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)

    item = _item(url="https://www.youtube.com/watch?v=abc")
    routes.worker_download(item["url"], item["folder"], item["nome"], item, None, None)

    assert chamado["yt"] and not chamado["loom"]
    assert item["status"] == "sucesso"


def test_youtube_sem_nome_usa_titulo_ytdlp_nao_loom(output_isolado, monkeypatch):
    """Link de YouTube sem nome (colado no popup): o título vem do yt-dlp,
    NUNCA do extrator do Loom."""
    chamado = {"titulo": False, "loom": False}
    monkeypatch.setattr(routes, "titulo_do_youtube",
                        lambda url: chamado.__setitem__("titulo", True) or "Meu Video")
    monkeypatch.setattr(routes, "extrair_metadados",
                        lambda url: chamado.__setitem__("loom", True) or ("x", "m3u8"))
    monkeypatch.setattr(routes, "baixar_youtube", lambda *a, **k: True)
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)

    item = _item(url="https://youtu.be/abc")
    routes.worker_download(item["url"], item["folder"], "", item, None, None)

    assert chamado["titulo"] and not chamado["loom"]
    assert item["nome"] == "Meu Video"
    assert item["status"] == "sucesso"


def test_aula_vimeo_roteia_com_referer(output_isolado, monkeypatch):
    """URL de Vimeo vai pro baixar_vimeo, levando o referer do pedido."""
    capturado = {}
    # O dublê aceita **kwargs de propósito. A versão anterior fixava os 5
    # parâmetros de então e quebrou com `TypeError` quando `baixar_vimeo` ganhou
    # `ao_converter` (vimeo.py:31-32) — falha do teste, não do código. Assinatura
    # frouxa aqui porque o que está sob teste é o ROTEAMENTO, não a assinatura.
    monkeypatch.setattr(routes, "baixar_vimeo",
                        lambda url, pasta, nome, referer=None, *a, **k:
                            capturado.update(url=url, referer=referer) or True)
    monkeypatch.setattr(routes, "baixar_youtube",
                        lambda *a, **k: pytest.fail("Vimeo não deve ir pro youtube"))
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)

    item = _item(url="https://player.vimeo.com/video/1212858408")
    routes.worker_download(item["url"], item["folder"], item["nome"], item,
                           None, None, "https://www.skool.com/x/post")

    assert capturado["url"] == "https://player.vimeo.com/video/1212858408"
    assert capturado["referer"] == "https://www.skool.com/x/post"
    assert item["status"] == "sucesso"


def test_aula_loom_nao_vai_para_ytdlp(output_isolado, monkeypatch):
    """URL do Loom NÃO deve cair no yt-dlp."""
    monkeypatch.setattr(routes, "baixar_youtube",
                        lambda *a, **k: pytest.fail("Loom não deve ir pro yt-dlp"))
    monkeypatch.setattr(routes, "extrair_metadados", lambda url: ("t", "m3u8"))
    monkeypatch.setattr(routes, "processar_download", lambda *a, **k: True)
    monkeypatch.setattr(routes, "converter_final", lambda *a, **k: True)
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)

    item = _item(url="https://www.loom.com/embed/abc")
    routes.worker_download(item["url"], item["folder"], item["nome"], item, None, None)

    assert item["status"] == "sucesso"


def test_video_falha_status_erro(output_isolado, monkeypatch):
    """Se o texto grava mas o vídeo falha, o status reflete a falha do vídeo."""
    monkeypatch.setattr(routes, "extrair_metadados", lambda url: ("t", None))
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)

    item = _item(url="https://www.loom.com/embed/abc")
    routes.worker_download(item["url"], item["folder"], item["nome"], item, DESC, RESOURCES)

    # o .md foi gravado mesmo assim (não se perde o texto).
    # Fica na pasta da aula porque a decisão de criar pasta é tomada ANTES do
    # download, pelo que se espera gerar (vídeo + texto = 2). O vídeo falhar
    # depois não desfaz a pasta — e não deve mesmo: o texto já está lá dentro.
    assert (output_isolado / "Com" / "Curso" / "Modulo" / "Aula 1" / "Aula 1.md").exists()
    assert item["status"] == "erro"
