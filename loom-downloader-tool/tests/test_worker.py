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
    # O anexo é adotado — e o prefixo `Aula 1 - ` cai, porque dentro da pasta da
    # aula ele é redundante e mantê-lo faria o anexo ser rebaixado na próxima vez.
    assert (pasta_aula / "anexo.pdf").exists(), \
        "anexo com o prefixo antigo deixou de ser adotado"


# --- TRAVA DA NUMERAÇÃO ---
# A ordem das aulas no Skool sai da POSIÇÃO no array `children` (medido em
# 12/08/2026 no __NEXT_DATA__). Para o disco respeitá-la, as pastas ganham prefixo
# `NN - `. Sem a trava abaixo, esse prefixo faria o servidor não achar nada e
# rebaixar 522 aulas / 62 GB.

def test_acha_pasta_da_aula_com_prefixo_de_ordem(tmp_path):
    (tmp_path / "07 - Aula X").mkdir()
    assert routes._pasta_existente_da_aula(str(tmp_path), "Aula X") == "07 - Aula X"


def test_acha_pasta_sem_prefixo_tambem(tmp_path):
    (tmp_path / "Aula X").mkdir()
    assert routes._pasta_existente_da_aula(str(tmp_path), "Aula X") == "Aula X"


def test_padding_de_qualquer_largura(tmp_path):
    (tmp_path / "007 - Aula X").mkdir()
    assert routes._pasta_existente_da_aula(str(tmp_path), "Aula X") == "007 - Aula X"


def test_prefixo_nao_numerico_nao_casa(tmp_path):
    # "Bônus - Aula X" é OUTRA aula, não a "Aula X" numerada. Casar aqui faria o
    # servidor gravar dentro da pasta errada — pior que rebaixar.
    (tmp_path / "Bonus - Aula X").mkdir()
    assert routes._pasta_existente_da_aula(str(tmp_path), "Aula X") is None


def test_arquivo_com_o_nome_certo_nao_conta_como_pasta(tmp_path):
    (tmp_path / "07 - Aula X").write_text("nao sou pasta")
    assert routes._pasta_existente_da_aula(str(tmp_path), "Aula X") is None


def test_sem_pasta_nenhuma_devolve_none(tmp_path):
    assert routes._pasta_existente_da_aula(str(tmp_path), "Aula X") is None
    assert routes._pasta_existente_da_aula(str(tmp_path / "nao existe"), "Aula X") is None


def test_worker_grava_dentro_da_pasta_numerada(output_isolado, monkeypatch, tmp_path):
    """A prova da Fase 1: aula já baixada em pasta NUMERADA não é rebaixada.

    Sem `_pasta_existente_da_aula`, o worker criaria `Modulo/Aula 1/` ao lado de
    `Modulo/03 - Aula 1/` e baixaria tudo outra vez.
    """
    monkeypatch.setattr(routes, "PASTA_OUTPUT", str(tmp_path))
    monkeypatch.setattr(routes, "extrair_metadados", lambda url: ("t", "m3u8"))
    monkeypatch.setattr(routes, "converter_final", lambda *a, **k: True)
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)

    monkeypatch.setattr(routes, "processar_download", lambda *a, **k: True)

    numerada = tmp_path / "Com" / "Curso" / "Modulo" / "03 - Aula 1"
    numerada.mkdir(parents=True)
    (numerada / "Aula 1.mp4").write_bytes(b"x" * 2_000_000)   # acima de 1 MB

    item = _item(url="https://www.loom.com/embed/abc")
    routes.worker_download(item["url"], item["folder"], item["nome"], item, None, None)

    # O CAMINHO é a asserção que importa: é ele que o "já baixei?" consulta
    # (`downloader.py`, `converter.py`, `ytdlp.py` checam o .mp4 nesse caminho).
    # Apontando para `03 - Aula 1`, o arquivo de 2 MB é encontrado e nada rebaixa.
    #
    # VERIFICADO em 12/08/2026 que este assert FALHA com a trava desligada: sem
    # `_pasta_existente_da_aula`, o folder vira `.../Aula 1`. Um assert sobre a
    # existência da pasta no disco NÃO serviria aqui — com os escritores mockados
    # nenhuma pasta chega a ser criada, e ele passaria dos dois jeitos.
    assert item["folder"].endswith("03 - Aula 1"), \
        f"gravou em {item['folder']} — ignorou a pasta numerada e vai rebaixar"


def test_pasta_sem_numero_e_renumerada_sem_baixar(output_isolado, monkeypatch, tmp_path):
    """Um "baixar tudo" vira RENUMERAÇÃO completa, sem baixar um byte.

    Sem isto a numeração só valeria para download novo, e as 522 pastas já em disco
    (medido em 12/08/2026) ficariam para sempre sem número — a ordem do curso nunca
    chegaria ao disco.
    """
    monkeypatch.setattr(routes, "PASTA_OUTPUT", str(tmp_path))
    monkeypatch.setattr(routes, "extrair_metadados", lambda url: ("t", "m3u8"))
    monkeypatch.setattr(routes, "converter_final", lambda *a, **k: True)
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)
    monkeypatch.setattr(routes, "processar_download", lambda *a, **k: True)

    modulo = tmp_path / "Com" / "Curso" / "Modulo"
    antiga = modulo / "Aula 1"
    antiga.mkdir(parents=True)
    (antiga / "Aula 1.mp4").write_bytes(b"x" * 2_000_000)

    item = _item(url="https://www.loom.com/embed/abc")
    routes.worker_download(item["url"], item["folder"], item["nome"], item,
                           None, None, None, None, 3, 12)

    assert (modulo / "03 - Aula 1").is_dir(), "a pasta não foi renumerada"
    assert not antiga.exists(), "sobrou a pasta antiga ao lado da renumerada"
    assert (modulo / "03 - Aula 1" / "Aula 1.mp4").exists(), "o vídeo veio junto"
    assert item["folder"].endswith("03 - Aula 1")


def test_renumeracao_nunca_sobrescreve_pasta_existente(tmp_path):
    """Duas pastas disputando o mesmo número é estado inconsistente.

    Mesclar aqui, no meio de um download e sem o usuário ver, poderia enterrar
    arquivo. Mantém o nome atual e avisa.
    """
    (tmp_path / "Aula 1").mkdir()
    ocupada = tmp_path / "03 - Aula 1"
    ocupada.mkdir()
    (ocupada / "importante.mp4").write_bytes(b"nao me perca")

    usado = routes._renomear_pasta_da_aula(str(tmp_path), "Aula 1", "03 - Aula 1")

    assert usado == "Aula 1", "renomeou por cima de uma pasta que já existia"
    assert (ocupada / "importante.mp4").exists()


def test_pedido_sem_ordem_nao_renumera(output_isolado, monkeypatch, tmp_path):
    """Link colado e Loom avulso não têm ordem — não podem inventar número."""
    monkeypatch.setattr(routes, "PASTA_OUTPUT", str(tmp_path))
    monkeypatch.setattr(routes, "extrair_metadados", lambda url: ("t", "m3u8"))
    monkeypatch.setattr(routes, "converter_final", lambda *a, **k: True)
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)
    monkeypatch.setattr(routes, "processar_download", lambda *a, **k: True)

    modulo = tmp_path / "Com" / "Curso" / "Modulo"
    (modulo / "Aula 1").mkdir(parents=True)
    (modulo / "Aula 1" / "Aula 1.mp4").write_bytes(b"x" * 2_000_000)

    item = _item(url="https://www.loom.com/embed/abc")
    routes.worker_download(item["url"], item["folder"], item["nome"], item)

    assert (modulo / "Aula 1").is_dir()
    assert item["folder"].endswith("Aula 1") and not item["folder"].endswith(" - Aula 1")


def test_modulo_tambem_e_renumerado_e_nada_rebaixa(output_isolado, monkeypatch, tmp_path):
    """A trava tem que cobrir o MÓDULO, não só a aula.

    PEGO NA REVISÃO (12/08/2026): quem numera o módulo é a extensão, então o pedido
    chega como `Com/Curso/01 - Dia 1`. A primeira versão olhava só a pasta da aula,
    o módulo numerado não existia em disco, e a árvore inteira nascia ao lado da
    antiga — rebaixando 522 aulas / 62 GB. Este teste guarda o nível de cima.
    """
    monkeypatch.setattr(routes, "PASTA_OUTPUT", str(tmp_path))
    monkeypatch.setattr(routes, "extrair_metadados", lambda url: ("t", "m3u8"))
    monkeypatch.setattr(routes, "converter_final", lambda *a, **k: True)
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)
    monkeypatch.setattr(routes, "processar_download", lambda *a, **k: True)

    antiga = tmp_path / "Com" / "Curso" / "Dia 1" / "Aula 1"
    antiga.mkdir(parents=True)
    (antiga / "Aula 1.mp4").write_bytes(b"x" * 2_000_000)

    item = _item(url="https://www.loom.com/embed/abc", folder="Com/Curso/01 - Dia 1")
    routes.worker_download(item["url"], item["folder"], item["nome"], item,
                           None, None, None, None, 1, 4)

    curso = tmp_path / "Com" / "Curso"
    assert [p.name for p in curso.iterdir()] == ["01 - Dia 1"], \
        f"sobrou árvore duplicada: {[p.name for p in curso.iterdir()]}"
    assert (curso / "01 - Dia 1" / "01 - Aula 1" / "Aula 1.mp4").exists(), \
        "o vídeo não acompanhou o rename — vai rebaixar"


def test_caminho_sem_ordem_reaproveita_modulo_numerado(tmp_path, monkeypatch):
    """O inverso: disco já numerado, pedido sem ordem. Não pode duplicar."""
    monkeypatch.setattr(routes, "PASTA_OUTPUT", str(tmp_path))
    (tmp_path / "Com" / "Curso" / "01 - Dia 1").mkdir(parents=True)

    assert routes._resolver_caminho("Com/Curso/Dia 1") == \
        os.path.join("Com", "Curso", "01 - Dia 1")


def test_caminho_novo_e_criado_como_pedido(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "PASTA_OUTPUT", str(tmp_path))
    assert routes._resolver_caminho("Com/Curso/01 - Dia 1") == \
        os.path.join("Com", "Curso", "01 - Dia 1")


def test_conversao_anda_depois_de_contar_segmentos(output_isolado, monkeypatch, tmp_path):
    """A faixa da conversão (85→99) tem que valer TAMBÉM no caminho HLS do Loom.

    PEGO NA REVISÃO (12/08/2026) e medido: ali `progresso` conta SEGMENTOS (0..N com
    `total` = N). Ao entrar na conversão, o `max(progresso, percentual)` comparava
    300 segmentos com 85 por cento e a barra congelava em 100% durante toda a
    conversão — a queixa original ("travada em 100% e não avança"), que estava dada
    como resolvida e nunca tinha valido neste caminho.
    """
    monkeypatch.setattr(routes, "PASTA_OUTPUT", str(tmp_path))
    monkeypatch.setattr(routes, "extrair_metadados", lambda url: ("t", "m3u8"))
    monkeypatch.setattr(routes, "limpar_pasta", lambda *a, **k: None)

    vistos = []

    def falso_download(url, temp, nome, pasta, callback):
        callback(total=300)                      # 300 segmentos
        for _ in range(300):
            callback()
        return True

    def falso_converter(nome, pasta, temp, ao_progresso=None):
        for fracao in (0.0, 0.5, 1.0):
            ao_progresso(fracao)
            vistos.append(item["progresso"])
        return True

    monkeypatch.setattr(routes, "processar_download", falso_download)
    monkeypatch.setattr(routes, "converter_final", falso_converter)

    item = _item(url="https://www.loom.com/embed/abc")
    routes.worker_download(item["url"], item["folder"], item["nome"], item, None, None)

    assert vistos == sorted(vistos), f"a barra andou para trás: {vistos}"
    assert vistos[0] < vistos[-1], \
        f"a conversão não moveu a barra (congelada em {vistos[0]}) — faixa 85→99 morta"
    assert all(0 <= v <= 100 for v in vistos), f"fora de 0..100: {vistos}"


def test_anexo_adotado_perde_o_prefixo_e_nao_duplica(tmp_path):
    """O prefixo `<Aula> - ` cai na adoção, senão o anexo é baixado de novo.

    PEGO NA REVISÃO (12/08/2026): `baixar_anexos` grava o nome NU
    (`template.json`), mas a adoção mantinha `Aula 1 - template.json`. Na execução
    seguinte, o "já existe" não encontrava e o anexo vinha de novo — os dois lado a
    lado dentro da mesma pasta.
    """
    modulo = tmp_path / "Modulo"
    modulo.mkdir()
    (modulo / "Aula 1.mp4").write_bytes(b"video")
    (modulo / "Aula 1 - template.json").write_bytes(b"anexo")

    pasta_aula = modulo / "Aula 1"
    routes._adotar_arquivos_soltos(str(modulo), str(pasta_aula), "Aula 1")

    assert (pasta_aula / "template.json").exists(), "o prefixo não caiu"
    assert not (pasta_aula / "Aula 1 - template.json").exists(), \
        "guardou com o nome antigo — vai duplicar na próxima execução"
    assert (pasta_aula / "Aula 1.mp4").exists(), "o vídeo mantém o nome da aula"
