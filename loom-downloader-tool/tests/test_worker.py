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

    # PASTA SEMPRE: a aula ganha pasta com o nome dela mesmo com um arquivo só.
    # O caminho é função da IDENTIDADE da aula, nunca do que o pedido trouxe.
    md = output_isolado / "Com" / "Curso" / "Modulo" / "Aula 1" / "Aula 1.md"
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

    md = output_isolado / "Com" / "Curso" / "Modulo" / "Aula 1" / "Aula 1.md"
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

    # PASTA SEMPRE: o caminho sai da IDENTIDADE da aula, não do que ela gera.
    # Vale igual para a aula de 5 arquivos e para a de 1 só.
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


def test_worker_que_estoura_vira_erro_e_nao_fica_baixando(monkeypatch, capsys):
    """Exceção no worker tem que virar status 'erro', nunca 'baixando' eterno.

    REGRESSÃO VISTA NA TELA: o `ThreadPoolExecutor` guarda a exceção no `Future`
    e ninguém chamava `.result()`. Um worker que estourava deixava o item preso em
    'baixando' com 0% para sempre, enquanto a vaga era liberada — o painel chegou
    a mostrar 6 aulas "baixando" com só 4 vagas. Duas eram cadáveres.
    """
    def explode(*a, **k):
        raise RuntimeError("boom no meio do download")

    monkeypatch.setattr(routes, "worker_download", explode)

    item = _item(url="https://www.loom.com/embed/abc")
    item["status"] = "baixando"

    # Não pode propagar: se propagar, o executor engole de novo e voltamos ao bug.
    routes._worker_blindado(item["url"], item["folder"], item["nome"], item)

    assert item["status"] == "erro", "o item ficaria preso em 'baixando' para sempre"
    saida = capsys.readouterr().out
    assert "boom no meio do download" in saida, \
        "a falha precisa ser VISÍVEL no terminal, não só mudar o status"

    # O terminal não basta: o dashboard roda em Live(screen=True) e repinta 4x/s,
    # então o print some em ~250ms. O motivo tem que ficar GUARDADO no item.
    assert "boom no meio do download" in item.get("motivo", ""), \
        "sem o motivo no item, o painel diz 'erro' e ninguém sabe de quê"


def test_barra_nao_passa_de_100_entre_faixas(output_isolado, monkeypatch):
    """Vídeo e áudio são downloads SEPARADOS: a barra tem que zerar entre eles.

    REGRESSÃO VISTA NA TELA: `atualizar_progresso(total=100)` definia o total mas
    não zerava o progresso, então o contador do áudio seguia de onde o vídeo parou
    e o painel mostrava 200% (barra verde cheia, número impossível).
    """
    vistos = []

    def falso_ytdlp(url, pasta, nome, callback, **k):
        # Faixa 1 (vídeo): reporta o total e enche a barra.
        callback(total=100)
        for _ in range(100):
            callback()
            vistos.append((item["progresso"], item["total"]))
        # Faixa 2 (áudio): novo total — é aqui que o progresso tem que zerar.
        callback(total=100)
        vistos.append((item["progresso"], item["total"]))
        for _ in range(100):
            callback()
            vistos.append((item["progresso"], item["total"]))
        return True

    monkeypatch.setattr(routes, "baixar_youtube", falso_ytdlp)
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)

    item = _item(url="https://www.youtube.com/watch?v=abc")
    routes.worker_download(item["url"], item["folder"], item["nome"], item, None, None)

    assert vistos, "o dublê não chegou a ser chamado"
    piores = [(p, t) for p, t in vistos if p > t]
    assert not piores, f"progresso passou do total: {piores[:3]}"
    # E zerou de verdade na troca de faixa, em vez de continuar de 100.
    assert (0, 100) in vistos, "o progresso não zerou quando a faixa mudou"
    assert item["progresso"] == 100


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


def test_pasta_existente_da_aula_manda_mais_que_a_previsao(output_isolado, monkeypatch, tmp_path):
    """Pedido sem `desc` cai na MESMA pasta de um pedido com `desc`.

    REGRESSÃO RELATADA (12/08/2026): um curso inteiro foi rebaixado só com os
    vídeos, soltos ao lado das pastas antigas. A regra de então previa os artefatos
    do pedido — sem `desc` dava 1, nenhuma pasta era criada, o servidor procurava o
    .mp4 solto no módulo, não achava, e baixava tudo de novo.

    O caminho passou a sair da IDENTIDADE da aula, então o `desc` não influencia
    mais onde nada é gravado. Este teste guarda essa propriedade.
    """
    monkeypatch.setattr(routes, "PASTA_OUTPUT", str(tmp_path))
    monkeypatch.setattr(routes, "extrair_metadados", lambda url: ("t", "m3u8"))
    monkeypatch.setattr(routes, "converter_final", lambda *a, **k: True)
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)

    destinos = []
    monkeypatch.setattr(routes, "processar_download",
                        lambda url, temp, nome, pasta_rel, cb=None: destinos.append(pasta_rel) or True)

    # Execução anterior deixou a pasta da aula pronta.
    (tmp_path / "Com" / "Curso" / "Modulo" / "Aula 1").mkdir(parents=True)

    # Pedido novo SEM desc: a previsão sozinha daria 1 artefato e nenhuma pasta.
    item = _item(url="https://www.loom.com/embed/abc")
    routes.worker_download(item["url"], item["folder"], item["nome"], item, None, None)

    assert destinos, "processar_download não chegou a ser chamado"
    assert destinos[0].replace("\\", "/").endswith("Modulo/Aula 1"), (
        f"gravaria fora da pasta existente: {destinos[0]!r}")


def test_caminho_dos_anexos_e_exercitado(output_isolado, monkeypatch):
    """O bloco de anexos precisa ser EXECUTADO por algum teste.

    BURACO DE COBERTURA MEDIDO em 12/08/2026: ao remover a variável
    `aula_tem_pasta`, ficou para trás um `prefixar=not aula_tem_pasta` — um
    `NameError` puro. A suíte inteira passou (113 verdes), porque o bloco só roda
    `if anexos:` e nenhum teste mandava anexo. Um teste que nunca entra no ramo não
    protege o ramo.
    """
    chamadas = []

    def falso_baixar_anexos(anexos, pasta):
        chamadas.append((anexos, pasta))
        return len(anexos), 0

    monkeypatch.setattr(routes, "baixar_anexos", falso_baixar_anexos)

    item = _item(url="")   # aula só de texto + anexo
    anexos = [{"url": "https://x/f.pdf", "nome": "f.pdf"}]
    routes.worker_download("", item["folder"], item["nome"], item, DESC, None,
                           None, anexos)

    assert chamadas, "o bloco de anexos não foi executado — o ramo segue sem guarda"
    _, pasta_usada = chamadas[0]
    assert pasta_usada.endswith("Aula 1"), \
        "anexo tem que ir para a pasta da aula, não para o módulo"
    assert item["status"] == "sucesso"


def test_nao_adota_video_de_aula_vizinha_com_nome_mais_longo(tmp_path, monkeypatch):
    """'Aula 1' não pode engolir o vídeo de 'Aula 1 - Extra'.

    PEGO NA REVISÃO (12/08/2026): a regra do prefixo valia para qualquer arquivo,
    então 'Aula 1' adotava 'Aula 1 - Extra.mp4'. A vizinha então procurava o vídeo
    na pasta dela, não achava, e REBAIXAVA — perdendo justamente a propriedade que
    `_adotar_arquivos_soltos` existe para proteger.
    """
    modulo = tmp_path / "Modulo"
    modulo.mkdir()
    (modulo / "Aula 1.mp4").write_bytes(b"meu")
    (modulo / "Aula 1 - Extra.mp4").write_bytes(b"da vizinha")
    (modulo / "Aula 1 - anexo.pdf").write_bytes(b"anexo meu")

    pasta_aula = modulo / "Aula 1"
    routes._adotar_arquivos_soltos(str(modulo), str(pasta_aula), "Aula 1")

    assert (pasta_aula / "Aula 1.mp4").exists(), "o próprio vídeo tem que ser adotado"
    assert (modulo / "Aula 1 - Extra.mp4").exists(), \
        "o vídeo da aula vizinha foi roubado — ela vai rebaixar tudo"
    assert (pasta_aula / "Aula 1 - anexo.pdf").exists(), \
        "anexo com o prefixo antigo continua sendo adotado"
