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
import hashlib

from .utils import limpar_nome_arquivo, cortar_preservando_extensao
from .caminhos import PASTA_OUTPUT

PREFIXO_V2 = "[v2]"


def _carregar_desc(desc_bruto):
    """Tira o prefixo `[v2]` e devolve os nós já em objeto Python, ou None.

    Um lugar só para o parse: `converter_desc` (que renderiza) e `imagens_do_desc`
    (que coleta os arquivos) TÊM que enxergar exatamente a mesma árvore, senão o
    Markdown referencia uma imagem que ninguém baixou.
    """
    if not desc_bruto or not isinstance(desc_bruto, str):
        return None

    corpo = desc_bruto[len(PREFIXO_V2):] if desc_bruto.startswith(PREFIXO_V2) else desc_bruto
    try:
        return json.loads(corpo)
    except (ValueError, TypeError):
        return None


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


# --- IMAGENS -----------------------------------------------------------------

def nome_local_da_imagem(attrs):
    """Nome do arquivo da imagem em disco. DETERMINÍSTICO.

    O Markdown aponta para este nome e o worker grava com este nome — se as duas
    pontas divergirem, a imagem baixa mas o `.md` referencia um arquivo que não
    existe, e o defeito só aparece quando alguém abre o texto.

    O Skool guarda o nome original em `title`/`alt` ("Screenshot ....png"). Sem
    nome utilizável, deriva da URL: continua estável entre execuções, então o
    "já baixei?" segue funcionando.
    """
    attrs = attrs or {}
    bruto = attrs.get("title") or attrs.get("alt") or ""
    if bruto and os.path.splitext(bruto)[1]:
        return cortar_preservando_extensao(bruto)

    src = attrs.get("src") or attrs.get("originalSrc") or ""
    if not src:
        return ""
    marca = hashlib.sha1(src.encode("utf-8")).hexdigest()[:10]
    ext = os.path.splitext(src.split("?")[0])[1]
    if len(ext) > 5 or " " in ext:
        ext = ".png"
    return f"imagem-{marca}{ext or '.png'}"


def imagens_do_desc(desc_bruto):
    """Lista `[{url, nome}]` das imagens do texto — a mesma forma dos anexos.

    De propósito: assim o worker reaproveita `baixar_anexos` em vez de ganhar um
    baixador novo (política de "reutilizar antes de criar").
    """
    nos = _carregar_desc(desc_bruto)
    if not nos:
        return []

    achadas, vistas = [], set()

    def andar(no):
        if isinstance(no, list):
            for filho in no:
                andar(filho)
            return
        if not isinstance(no, dict):
            return
        if no.get("type") == "image":
            attrs = no.get("attrs") or {}
            url = attrs.get("src") or attrs.get("originalSrc")
            nome = nome_local_da_imagem(attrs)
            if url and nome and url not in vistas:
                vistas.add(url)
                achadas.append({"url": url, "nome": nome})
        for valor in no.values():
            andar(valor)

    andar(nos)
    return achadas


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

    if tipo == "image":
        # IMAGEM NO TEXTO DA AULA.
        #
        # RELATADO em 13/08/2026, na BACKROOM.EXE: "os links estão presentes, mas a
        # imagem não foi inserida no Markdown". Sem este caso, o nó caía no ramo
        # "tipo desconhecido", não tinha `content`, e voltava string vazia — a aula
        # perdia a imagem SEM AVISO.
        #
        # MEDIDO, a forma do nó:
        #   {"type":"image","attrs":{"alt":"Screenshot ....png","fileID":"...",
        #                            "src":"https://assets.skool.com/f/...","title":"..."}}
        #
        # Aponta para o arquivo LOCAL, não para a URL: a `src` do Skool pode sair do
        # ar e a biblioteca existe para funcionar offline. Quem baixa é o worker,
        # usando `imagens_do_desc` — e os dois nomes têm que bater, por isso ambos
        # passam por `nome_local_da_imagem`.
        attrs = no.get("attrs") or {}
        nome = nome_local_da_imagem(attrs)
        if not nome:
            return ""
        alt = (attrs.get("alt") or attrs.get("title") or "imagem").replace("]", ")")
        # `<...>` porque nome de imagem do Skool costuma ter espaço.
        return f"![{alt}](<{nome}>)\n\n"

    if tipo in ("horizontalRule", "horizontal_rule", "hr"):
        # Também sumia em silêncio (6 ocorrências só no curso medido).
        return "---\n\n"

    if tipo in ("bulletList", "orderedList", "unorderedList", "bullet_list", "ordered_list"):
        # `unorderedList` é o nome que o Skool usa DE VERDADE (medido). Antes ele
        # caía no ramo genérico: o conteúdo sobrevivia por acidente, mas sem a
        # quebra de linha que separa a lista do parágrafo seguinte.
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

    nos = _carregar_desc(desc_bruto)
    if nos is None:
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


NOTA_VAZIA = "_(Esta aula não tinha vídeo nem texto no Skool.)_"


def montar_markdown(titulo, desc_bruto, resources_bruto, permitir_vazio=False):
    """Monta o .md final de uma aula: título + descrição + recursos.

    - `permitir_vazio=False` (padrão, para aula com vídeo): devolve None quando
      não há texto, para não gravar um .md redundante ao lado do .mp4.
    - `permitir_vazio=True` (aula sem vídeo): sempre devolve um .md. Se não há
      conteúdo, gera um placeholder com o título e uma nota — assim uma aula
      vazia do curso fica registrada em vez de sumir sem aviso.
    """
    corpo_desc = converter_desc(desc_bruto)
    corpo_resources = converter_resources(resources_bruto)

    if not corpo_desc and not corpo_resources:
        if not permitir_vazio:
            return None
        cabecalho = f"# {titulo}".rstrip() if titulo else "# (aula sem título)"
        return f"{cabecalho}\n\n{NOTA_VAZIA}\n"

    partes = [f"# {titulo}".rstrip()] if titulo else []
    if corpo_desc:
        partes.append(corpo_desc)
    if corpo_resources:
        partes.append("## Recursos\n\n" + corpo_resources)

    return "\n\n".join(partes).strip() + "\n"


def salvar_aula_md(nome, pasta_rel, desc_bruto, resources_bruto, permitir_vazio=False):
    """
    Grava o `.md` da aula ao lado de onde o vídeo fica.

    Com `permitir_vazio=False` (aula com vídeo), só grava se houver texto — não
    deixa .md redundante ao lado do .mp4. Com `permitir_vazio=True` (aula sem
    vídeo), sempre grava, usando um placeholder quando a aula está vazia.

    Devolve o caminho gravado, ou None se nada foi gravado.
    """
    conteudo = montar_markdown(nome, desc_bruto, resources_bruto, permitir_vazio)
    if conteudo is None:
        return None

    pasta_rel_limpa = pasta_rel[1:] if pasta_rel.startswith(os.sep) else pasta_rel
    pasta_destino = os.path.join(PASTA_OUTPUT, pasta_rel_limpa)
    os.makedirs(pasta_destino, exist_ok=True)

    caminho = os.path.join(pasta_destino, f"{limpar_nome_arquivo(nome)}.md")
    with open(caminho, "w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write(conteudo)
    return caminho
