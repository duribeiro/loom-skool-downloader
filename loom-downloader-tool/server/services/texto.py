"""Converte o texto das aulas do Skool (rich-text + recursos) para Markdown.

O Skool guarda a descrição da aula num rich-text estruturado, prefixado por
"[v2]" e seguido de um array JSON de nós no estilo ProseMirror/TipTap:

    [v2][{"type":"paragraph","content":[
            {"type":"text","text":"veja ","marks":[]},
            {"type":"text","text":"aqui","marks":[{"type":"link","attrs":{"href":"..."}}]}
    ]}]

E os recursos numa lista simples:  [{"title": "...", "link": "..."}]

O conversor é tolerante: tipos de nó/mark desconhecidos degradam para o texto
puro em vez de quebrar. Assim, um curso que use negrito, listas ou headings
(que o curso medido não usava) ainda sai razoável.
"""
import os
import json

from .utils import limpar_nome_arquivo
from .caminhos import PASTA_OUTPUT

PREFIXO_V2 = "[v2]"


# --- MARKS (formatação inline) -----------------------------------------------

def _aplicar_marks(texto, marks):
    """Embrulha o texto conforme as marcas (link, negrito, itálico...)."""
    if not marks:
        return texto

    for mark in marks:
        tipo = mark.get("type") if isinstance(mark, dict) else mark
        attrs = mark.get("attrs", {}) if isinstance(mark, dict) else {}

        if tipo == "link":
            href = attrs.get("href") or attrs.get("url") or ""
            if href:
                texto = f"[{texto}]({href})"
        elif tipo in ("bold", "strong"):
            texto = f"**{texto}**"
        elif tipo in ("italic", "em"):
            texto = f"*{texto}*"
        elif tipo == "code":
            texto = f"`{texto}`"
        elif tipo in ("strike", "strikethrough"):
            texto = f"~~{texto}~~"
        # marca desconhecida: mantém o texto sem formatar
    return texto


# --- NÓS (blocos) ------------------------------------------------------------

def _renderizar(no):
    """Renderiza um nó (ou lista de nós) do rich-text para Markdown."""
    if isinstance(no, list):
        return "".join(_renderizar(filho) for filho in no)

    if not isinstance(no, dict):
        return ""

    tipo = no.get("type")

    if tipo == "text":
        return _aplicar_marks(no.get("text", ""), no.get("marks"))

    if tipo == "paragraph":
        return _renderizar(no.get("content", [])) + "\n\n"

    if tipo == "heading":
        nivel = (no.get("attrs") or {}).get("level", 2)
        return "#" * int(nivel) + " " + _renderizar(no.get("content", [])) + "\n\n"

    if tipo in ("bulletList", "orderedList"):
        return _renderizar(no.get("content", [])) + "\n"

    if tipo == "listItem":
        # o conteúdo costuma ser um paragraph; tira a quebra dupla do fim
        interno = _renderizar(no.get("content", [])).strip()
        return f"- {interno}\n"

    if tipo in ("hardBreak", "hard_break"):
        return "\n"

    if tipo == "blockquote":
        interno = _renderizar(no.get("content", [])).strip()
        return f"> {interno}\n\n"

    # tipo desconhecido: ainda assim tenta extrair o texto de dentro
    if "content" in no:
        return _renderizar(no["content"])
    return ""


def converter_desc(desc_bruto):
    """Converte o campo `desc` do Skool para Markdown. String vazia se não houver."""
    if not desc_bruto or not isinstance(desc_bruto, str):
        return ""

    corpo = desc_bruto[len(PREFIXO_V2):] if desc_bruto.startswith(PREFIXO_V2) else desc_bruto

    try:
        nos = json.loads(corpo)
    except (ValueError, TypeError):
        # Não é o formato esperado: devolve o texto cru como último recurso.
        return desc_bruto.strip()

    return _renderizar(nos).strip()


def converter_resources(resources_bruto):
    """Converte o campo `resources` numa lista Markdown de links."""
    if not resources_bruto or not isinstance(resources_bruto, str):
        return ""

    try:
        itens = json.loads(resources_bruto)
    except (ValueError, TypeError):
        return ""

    if not isinstance(itens, list):
        return ""

    linhas = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        titulo = (item.get("title") or item.get("link") or "").strip()
        link = (item.get("link") or "").strip()
        if link and titulo:
            linhas.append(f"- [{titulo}]({link})")
        elif titulo:
            linhas.append(f"- {titulo}")
    return "\n".join(linhas)


def montar_markdown(titulo, desc_bruto, resources_bruto):
    """Monta o .md final de uma aula: título + descrição + recursos.

    Devolve None se não houver conteúdo textual nenhum (aula só de vídeo) — o
    chamador não deve gravar arquivo vazio nesse caso.
    """
    corpo_desc = converter_desc(desc_bruto)
    corpo_resources = converter_resources(resources_bruto)

    if not corpo_desc and not corpo_resources:
        return None

    partes = [f"# {titulo}".rstrip()] if titulo else []
    if corpo_desc:
        partes.append(corpo_desc)
    if corpo_resources:
        partes.append("## Recursos\n\n" + corpo_resources)

    return "\n\n".join(partes).strip() + "\n"


def salvar_aula_md(nome, pasta_rel, desc_bruto, resources_bruto):
    """
    Grava o `.md` da aula ao lado de onde o vídeo fica, se houver texto.

    Devolve o caminho gravado, ou None se a aula não tinha texto nenhum (aí
    nada é gravado — não deixamos .md vazio no disco).
    """
    conteudo = montar_markdown(nome, desc_bruto, resources_bruto)
    if conteudo is None:
        return None

    pasta_rel_limpa = pasta_rel[1:] if pasta_rel.startswith(os.sep) else pasta_rel
    pasta_destino = os.path.join(PASTA_OUTPUT, pasta_rel_limpa)
    os.makedirs(pasta_destino, exist_ok=True)

    caminho = os.path.join(pasta_destino, f"{limpar_nome_arquivo(nome)}.md")
    with open(caminho, "w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write(conteudo)
    return caminho
