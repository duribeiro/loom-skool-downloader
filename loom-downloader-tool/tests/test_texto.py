"""Conversor de rich-text do Skool para Markdown.

As fixtures seguem o schema real medido no navegador (curso GANG.EXE):
nós paragraph/text/heading/listItem, marks do tipo link, e resources {title,link}.
"""
import json

import pytest

from services.texto import (
    converter_desc,
    converter_resources,
    montar_markdown,
    imagens_do_desc,
)


def desc_v2(nos):
    """Monta uma string `desc` no formato do Skool a partir de nós."""
    return "[v2]" + json.dumps(nos)


# --- converter_desc ----------------------------------------------------------

def test_paragrafo_simples():
    d = desc_v2([{"type": "paragraph", "content": [
        {"type": "text", "text": "Olá mundo"}]}])
    assert converter_desc(d) == "Olá mundo"


def test_link_vira_markdown():
    d = desc_v2([{"type": "paragraph", "content": [
        {"type": "text", "text": "veja "},
        {"type": "text", "text": "aqui",
         "marks": [{"type": "link", "attrs": {"href": "https://x.com"}}]},
    ]}])
    assert converter_desc(d) == "veja [aqui](https://x.com)"


def test_dois_paragrafos_separados_por_linha_em_branco():
    d = desc_v2([
        {"type": "paragraph", "content": [{"type": "text", "text": "um"}]},
        {"type": "paragraph", "content": [{"type": "text", "text": "dois"}]},
    ])
    assert converter_desc(d) == "um\n\ndois"


def test_negrito_e_italico():
    d = desc_v2([{"type": "paragraph", "content": [
        {"type": "text", "text": "a", "marks": [{"type": "bold"}]},
        {"type": "text", "text": "b", "marks": [{"type": "italic"}]},
    ]}])
    assert converter_desc(d) == "**a***b*"


def test_heading():
    d = desc_v2([{"type": "heading", "attrs": {"level": 2},
                  "content": [{"type": "text", "text": "Título"}]}])
    assert converter_desc(d) == "## Título"


def test_lista():
    d = desc_v2([{"type": "bulletList", "content": [
        {"type": "listItem", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "item 1"}]}]},
        {"type": "listItem", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "item 2"}]}]},
    ]}])
    assert converter_desc(d) == "- item 1\n- item 2"


def test_tipo_desconhecido_degrada_para_o_texto():
    d = desc_v2([{"type": "callout", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "dentro"}]}]}])
    assert converter_desc(d) == "dentro"


def test_prefixo_v2_opcional():
    nos = [{"type": "paragraph", "content": [{"type": "text", "text": "x"}]}]
    assert converter_desc(json.dumps(nos)) == "x"  # sem [v2]


@pytest.mark.parametrize("vazio", ["", None, 123])
def test_desc_vazio_ou_invalido(vazio):
    assert converter_desc(vazio) == ""


def test_desc_nao_json_devolve_bruto():
    assert converter_desc("texto solto sem json") == "texto solto sem json"


# --- converter_resources -----------------------------------------------------

def test_resources_vira_lista_de_links():
    r = json.dumps([
        {"title": "BAIXAR PROMPTS", "link": "https://docs.google.com/x"},
        {"title": "Planilha", "link": "https://sheets/y"},
    ])
    assert converter_resources(r) == (
        "- [BAIXAR PROMPTS](https://docs.google.com/x)\n"
        "- [Planilha](https://sheets/y)"
    )


@pytest.mark.parametrize("vazio", ["", None, "[]", "não-json"])
def test_resources_vazio(vazio):
    assert converter_resources(vazio) == ""


# --- montar_markdown ---------------------------------------------------------

def test_markdown_completo():
    d = desc_v2([{"type": "paragraph", "content": [{"type": "text", "text": "corpo"}]}])
    r = json.dumps([{"title": "Link", "link": "https://x"}])
    md = montar_markdown("Aula 1", d, r)
    assert md == (
        "# Aula 1\n\n"
        "corpo\n\n"
        "## Recursos\n\n"
        "- [Link](https://x)\n"
    )


def test_markdown_so_com_video_retorna_none():
    """Aula com vídeo e sem texto não gera .md — não gravar arquivo redundante."""
    assert montar_markdown("Aula", "", "") is None
    assert montar_markdown("Aula", None, None) is None


def test_markdown_vazio_com_permitir_vazio_gera_placeholder():
    """Aula sem vídeo e sem texto: gera placeholder para não sumir do registro."""
    md = montar_markdown("Intro", "", "", permitir_vazio=True)
    assert md is not None
    assert "# Intro" in md
    assert "não tinha vídeo nem texto" in md


def test_markdown_so_texto_sem_recursos():
    d = desc_v2([{"type": "paragraph", "content": [{"type": "text", "text": "só texto"}]}])
    md = montar_markdown("T", d, "")
    assert md == "# T\n\nsó texto\n"
    assert "Recursos" not in md


# --- IMAGEM DENTRO DO TEXTO ---
# RELATADO em 13/08/2026 (BACKROOM.EXE): "os links estão presentes, mas a imagem
# não foi inserida no Markdown". O nó `image` não tinha caso no renderizador,
# caía no ramo genérico, não tinha `content` e voltava string vazia.

def _desc(*nos):
    return "[v2]" + json.dumps(list(nos))


IMG = {"type": "image", "attrs": {
    "alt": "Screenshot 2025-10-03 at 9.16.56 AM.png",
    "title": "Screenshot 2025-10-03 at 9.16.56 AM.png",
    "src": "https://assets.skool.com/f/7ab1081/f6a31ba"}}


def test_imagem_vira_markdown():
    md = converter_desc(_desc(IMG))
    assert "![" in md and "Screenshot 2025-10-03" in md, f"imagem sumiu: {md!r}"


def test_imagem_aponta_para_arquivo_local_nao_para_a_url():
    """A biblioteca existe para funcionar offline; a `src` do Skool pode cair."""
    md = converter_desc(_desc(IMG))
    assert "assets.skool.com" not in md, "o .md ficou dependendo da nuvem"


def test_nome_no_markdown_bate_com_o_que_sera_baixado():
    """Se as duas pontas divergirem, a imagem baixa e o texto aponta para o vazio."""
    md = converter_desc(_desc(IMG))
    baixadas = imagens_do_desc(_desc(IMG))

    assert len(baixadas) == 1
    assert baixadas[0]["nome"] in md, \
        f"o Markdown não referencia {baixadas[0]['nome']!r}"


def test_imagens_do_desc_devolve_a_forma_dos_anexos():
    # Mesma forma {url, nome} — é o que permite reusar `baixar_anexos`.
    img = imagens_do_desc(_desc(IMG))[0]
    assert set(img) == {"url", "nome"}
    assert img["url"].startswith("https://")


def test_imagem_repetida_baixa_uma_vez_so():
    assert len(imagens_do_desc(_desc(IMG, IMG))) == 1


def test_imagem_sem_titulo_ganha_nome_estavel():
    no = {"type": "image", "attrs": {"src": "https://assets.skool.com/f/abc/def"}}
    a = imagens_do_desc(_desc(no))
    b = imagens_do_desc(_desc(no))
    assert a and a == b, "nome instável quebraria o 'já baixei?'"


def test_imagem_sem_url_nenhuma_e_ignorada():
    no = {"type": "image", "attrs": {"alt": "x.png"}}
    assert imagens_do_desc(_desc(no)) == []


def test_desc_sem_imagem_devolve_lista_vazia():
    assert imagens_do_desc(_desc({"type": "paragraph",
                                  "content": [{"type": "text", "text": "oi"}]})) == []


# --- OUTROS TIPOS QUE TAMBÉM SUMIAM ---

def test_linha_horizontal_aparece():
    # 6 ocorrências só no curso medido, todas perdidas.
    assert "---" in converter_desc(_desc({"type": "horizontalRule"}))


def test_unorderedList_e_o_nome_que_o_skool_usa():
    """O código tratava `bulletList`; o Skool manda `unorderedList` (medido)."""
    lista = {"type": "unorderedList", "content": [
        {"type": "listItem", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Abra o agente"}]}]},
        {"type": "listItem", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Cole o prompt"}]}]}]}
    md = converter_desc(_desc(lista))
    assert "- Abra o agente" in md and "- Cole o prompt" in md
