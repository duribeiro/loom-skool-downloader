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
    """Aula sem texto nem recursos não gera .md — não gravar arquivo vazio."""
    assert montar_markdown("Aula", "", "") is None
    assert montar_markdown("Aula", None, None) is None


def test_markdown_so_texto_sem_recursos():
    d = desc_v2([{"type": "paragraph", "content": [{"type": "text", "text": "só texto"}]}])
    md = montar_markdown("T", d, "")
    assert md == "# T\n\nsó texto\n"
    assert "Recursos" not in md
