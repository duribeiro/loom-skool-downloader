import re
import html
import json
import shutil
import os
import requests

# Cabeçalhos para fingir que somos um navegador real e não ser bloqueado
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.loom.com/",
    "Origin": "https://www.loom.com"
}

# Teto de caracteres para o nome de UM componente do caminho (pasta ou arquivo).
#
# Por que existe: com pasta por aula, o nome da aula entra DUAS vezes no caminho
# (`.../Aula X/Aula X.mp4`), então um título longo custa o dobro. O limite do
# Windows é 260 chars no caminho inteiro.
#
# MEDIDO na output/ em 12/08/2026: 885 arquivos, caminho mais longo 256 chars, e
# só 3 passariam de 260 ao ganhar pasta própria — o pior com 286.
#
# Por que 80 e não outro número: dos 1260 componentes de caminho em uso, o maior
# tem 81 chars — e é um dos 3 que estouram. Ou seja, cortar em 80 encurta esse um
# em uma letra (rebaixa ele uma vez, de propósito, porque o caminho dele é
# inválido) e não encosta em nenhum dos outros 1259. Um limite mais folgado (100)
# não protegeria os 3; um mais apertado renomearia arquivo bom em massa.
LIMITE_NOME = 80

# Maior extensão que ainda parece extensão (".jpeg", ".webm", ".stackdump"). Acima
# disso, o ponto era do NOME, não de uma extensão.
_MAX_EXTENSAO = 12


def limpar_nome_arquivo(nome, limite=None):
    """
    Remove caracteres proibidos em nomes de arquivos do Windows/Linux e corta o
    que passar de `limite` (padrão `LIMITE_NOME`).
    Ex: "Aula: 01?" vira "Aula 01"

    `limite` menor entra quando o CAMINHO inteiro está apertado — ver
    `limite_do_nome`.
    """
    limite = LIMITE_NOME if limite is None else limite
    if not nome: return "sem_titulo"

    # Decodifica entidades HTML (ex: &amp; vira &)
    nome = html.unescape(nome)

    # Remove caracteres proibidos (< > : " / \ | ? *)
    nome = re.sub(r'[<>:"/\\|?*]', '', nome)

    # Remove espaços duplos e espaços nas pontas
    nome = " ".join(nome.split())

    # PONTO OU ESPAÇO NO FIM NÃO EXISTEM NO WINDOWS — e cada camada "conserta" de um
    # jeito diferente, o que parte a pasta em três.
    #
    # MEDIDO em 13/08/2026, com a aula "#12 De 597 a 10 mil reais em 6 meses, por
    # Luis F." (repare no ponto do fim):
    #
    #     nosso nome       -> '... por Luis F.'
    #     Windows cria     -> '... por Luis F'     (corta o ponto, calado)
    #     yt-dlp sanitiza  -> '... por Luis F#'    (troca o ponto por '#')
    #
    # Resultado real: o yt-dlp baixou 161 MB em `...F#/`, nosso código foi procurar o
    # .mp4 em `...F./` (que o Windows resolve como `...F/`, vazia), não achou, e o
    # temporário `._yt_*` ficou órfão. Duas aulas, 349,8 MB parados.
    #
    # Cortar aqui faz o nome ser o mesmo em todas as camadas. Não é cosmético.
    nome = nome.rstrip(". ")

    # Corta no limite, sem deixar espaço solto na ponta. O corte é DETERMINÍSTICO:
    # o mesmo título sempre vira o mesmo nome, então "já baixei?" continua achando
    # o arquivo de uma execução anterior.
    #
    # NÃO tenta preservar extensão aqui de propósito: esta função nomeia PASTAS e
    # bases de arquivo (aula, módulo, comunidade), onde um ponto no meio do título
    # ("Aula 1.5 - Intro") não é extensão. Para nome que TEM extensão de verdade,
    # use `cortar_preservando_extensao`.
    if len(nome) > limite:
        nome = nome[:limite].rstrip()

    return nome or "sem_titulo"


# Teto do CAMINHO INTEIRO. O Windows corta em 260; 255 deixa margem para o
# ".part"/sufixo temporário que alguns downloads criam antes do rename.
MAX_CAMINHO = 255

# Abaixo disto o nome deixa de identificar a aula, e truncar mais só troca um
# problema por outro. Quem chegar aqui recebe um aviso: o caminho de destino é que
# está fundo demais, e isso o usuário resolve escolhendo outra pasta.
PISO_NOME = 25


def limite_do_nome(pasta_pai_abs, extensao=".mp4", prefixo="", aparicoes=2):
    """Quanto pode ter o nome da aula, para o CAMINHO INTEIRO caber em `MAX_CAMINHO`.

    Por que não basta o `LIMITE_NOME` fixo: ele é teto POR COMPONENTE, e o limite do
    Windows é do caminho inteiro. MEDIDO em 13/08/2026 — com a `output/` dentro do
    projeto (82 chars só de prefixo) o pior caso deu 277, mesmo com o nome já em 80.

    O caminho final é:

        <pasta_pai>\\<prefixo><nome>\\<nome><extensão>

    O nome aparece DUAS vezes (pasta da aula e arquivo), por isso o que sobra é
    dividido por `aparicoes`. Devolve no máximo `LIMITE_NOME` (legibilidade) e no
    mínimo `PISO_NOME`.

    O resultado depende da pasta-pai, então mover a biblioteca pode mudar o nome de
    quem foi truncado. Na prática isso atinge pouquíssimos arquivos — com a `output/`
    num lugar normal, nenhum (medido: pior caso 232 de 260).
    """
    fixo = len(pasta_pai_abs) + aparicoes + len(prefixo) + len(extensao)
    disponivel = MAX_CAMINHO - fixo
    if disponivel <= 0:
        return PISO_NOME
    return max(PISO_NOME, min(LIMITE_NOME, disponivel // max(1, aparicoes)))


def prefixo_de_ordem(ordem, total=None):
    """`NN - ` para a pasta refletir a ordem do curso, ou '' quando não se sabe.

    No disco as pastas ordenam alfabeticamente, e aí "Dia 10" vem antes de "Dia 2".
    Pior: MEDIDO no Skool em 12/08/2026, a PRIMEIRA aula do Dia 1 do Bootcamp é
    "Wins do Mês 1", que alfabeticamente cai em último. O curso tem sequência
    pedagógica e o disco a inverte.

    O padding sai do TOTAL do nível, não é fixo: com 2 dígitos num módulo de 100+
    aulas, a 100ª ordenaria antes da 20ª — o mesmo bug, um nível acima.

    Sem ordem (link colado, Loom fora do Skool, curso sem `children` no JSON)
    devolve '' — nunca inventamos posição.

    Espelha `prefixoDeOrdem` em extension/content.js; os dois têm que concordar,
    senão o servidor cria uma pasta que a extensão não reconhece.
    """
    try:
        ordem = int(ordem)
    except (TypeError, ValueError):
        return ""
    if ordem <= 0:
        return ""

    try:
        largura = max(2, len(str(int(total))))
    except (TypeError, ValueError):
        largura = 2
    return f"{ordem:0{largura}d} - "


def cortar_preservando_extensao(nome_arquivo, limite=LIMITE_NOME):
    """Limpa e encurta um nome de arquivo SEM perder a extensão.

    REGRESSÃO MEDIDA em 12/08/2026, pega na revisão: ao remover o antigo
    `_nome_do_anexo` (que usava `splitext`) e, no mesmo patch, pôr um corte cego de
    `LIMITE_NOME` em `limpar_nome_arquivo`, um anexo de 90 chars perdia o `.pdf`:

        'Checklist ... com N8N e Evolution API.pdf'  ->  'Checklist ... e Evoluti'

    Sem extensão o Windows não abre o arquivo e nada a jusante consegue distinguir
    o anexo de lixo. As duas mudanças estavam certas sozinhas; juntas, destruíam
    o produto de cursos como a Biblioteca de Templates.
    """
    bruto = html.unescape(nome_arquivo or "")
    base, ext = os.path.splitext(bruto)
    ext = re.sub(r'[<>:"/\\|?*]', '', ext)

    # `splitext` corta no ÚLTIMO ponto, e ponto no meio do nome é comum:
    # 'Aula 1.5 - Introducao' virava base='Aula 1' + ext='.5 - Introducao', e o
    # corte da "extensão" mutilava o nome. Extensão de verdade é curta e não tem
    # espaço — o que não for assim é parte do nome.
    if len(ext) > _MAX_EXTENSAO or " " in ext:
        base, ext = bruto, ""

    base = limpar_nome_arquivo(base)
    if base == "sem_titulo" and not ext:
        return "anexo"

    disponivel = max(1, limite - len(ext))
    return (base[:disponivel].rstrip() or "anexo") + ext

def limpar_pasta(caminho):
    """
    Tenta remover uma pasta e todo o seu conteúdo recursivamente.
    Útil para limpar os arquivos temporários após o download.
    """
    if os.path.exists(caminho):
        try:
            shutil.rmtree(caminho, ignore_errors=True)
        except Exception as e:
            print(f"⚠️ Aviso: Não foi possível limpar {caminho}: {e}")

# --- EXTRAÇÃO DOS DADOS DA PÁGINA DO LOOM ------------------------------------
#
# A página do Loom carrega um objeto JSON completo em `window.__APOLLO_STATE__`
# com tudo que o player precisa. Lemos DESSE objeto, pela estrutura dele.
#
# Por que não por regex no texto: já quebrou. O Loom renomeou o arquivo da
# playlist de "playlist.m3u8" para "playlist-multibitrate.m3u8" e a extração
# parou de funcionar, sem erro nenhum. Casar texto depende do formato da string;
# ler a estrutura depende só do contrato dos dados, que muda muito menos.

TIPO_URL_ASSINADA = "CloudfrontSignedUrlPayload"
TIPO_VIDEO = "RegularUserVideo"


def _extrair_apollo_state(conteudo_html):
    """
    Recorta o objeto `window.__APOLLO_STATE__` do HTML e devolve como dict.

    O truque está em não tentar achar onde o objeto termina: contar chaves
    dá errado porque existem chaves dentro de strings. Achamos onde ele
    COMEÇA e deixamos o parser de JSON ler até o fim natural do objeto.
    """
    marcador = re.search(r'window\.__APOLLO_STATE__\s*=\s*', conteudo_html)
    if not marcador:
        return None

    try:
        dados, _ = json.JSONDecoder().raw_decode(conteudo_html, marcador.end())
        return dados
    except ValueError:
        return None


def _caminhar(no, aceita):
    """
    Percorre a árvore de dados e devolve o primeiro nó aceito por `aceita`.

    O Apollo guarda os dados numa estrutura aninhada e com chaves geradas
    dinamicamente (ex: 'RegularUserVideo:abc123'), então não dá para navegar
    por um caminho fixo — procuramos pelo formato do nó.
    """
    if isinstance(no, dict):
        resultado = aceita(no)
        if resultado is not None:
            return resultado
        for valor in no.values():
            achado = _caminhar(valor, aceita)
            if achado is not None:
                return achado
    elif isinstance(no, list):
        for item in no:
            achado = _caminhar(item, aceita)
            if achado is not None:
                return achado
    return None


def _procurar_url_do_stream(dados):
    """Acha a URL assinada do .m3u8 pelo __typename do nó."""
    def aceita(no):
        if no.get("__typename") != TIPO_URL_ASSINADA:
            return None
        url = no.get("url")
        if isinstance(url, str) and ".m3u8" in url:
            return url
        return None

    return _caminhar(dados, aceita)


def _procurar_titulo(dados):
    """Acha o nome do vídeo pelo __typename do nó."""
    def aceita(no):
        if no.get("__typename") != TIPO_VIDEO:
            return None
        nome = no.get("name")
        return nome if isinstance(nome, str) and nome.strip() else None

    return _caminhar(dados, aceita)


def _titulo_pela_tag_title(conteudo_html):
    """Reserva: pega o título da tag <title> quando o Apollo não tem o nome."""
    match = re.search(r'<title>(.*?)</title>', conteudo_html, re.S)
    if not match:
        return None
    return match.group(1).replace(" | Loom", "")


def _url_por_regex(conteudo_html):
    """
    ÚLTIMO RECURSO. Mantido de propósito: se o Loom mudar o formato do
    __APOLLO_STATE__, isto ainda pode salvar o download. Quando cair aqui,
    avisamos — degradar em silêncio foi o que custou caro da última vez.
    """
    match = re.search(r'"url":"(https://[^"]+\.m3u8[^"]*)"', conteudo_html)
    if not match:
        return None
    return match.group(1).replace('\\/', '/')


def extrair_metadados(url_loom):
    """
    Acessa a página do vídeo (embed) e descobre:
    1. O título original
    2. A URL da playlist (m3u8)

    Devolve (None, None) se a página não puder ser acessada.
    """
    try:
        resposta = requests.get(url_loom, headers=HEADERS, timeout=10)
        conteudo_html = resposta.text
    except Exception as erro:
        print(f"⚠️  Não foi possível acessar {url_loom}: {type(erro).__name__}: {erro}")
        return None, None

    dados = _extrair_apollo_state(conteudo_html)

    # --- URL do stream ---
    url_m3u8 = _procurar_url_do_stream(dados) if dados else None

    if url_m3u8 is None:
        url_m3u8 = _url_por_regex(conteudo_html)
        if url_m3u8:
            print("⚠️  Extração estrutural falhou; usando o regex reserva. "
                  "O formato da página do Loom provavelmente mudou.")
        else:
            motivo = ("__APOLLO_STATE__ não encontrado na página"
                      if not dados else
                      f"nenhum nó '{TIPO_URL_ASSINADA}' com .m3u8 no __APOLLO_STATE__")
            print(f"❌ Não foi possível extrair a URL do vídeo: {motivo}")

    if url_m3u8:
        # Desfaz as barras escapadas do JSON (ex: \/ vira /)
        url_m3u8 = url_m3u8.replace('\\/', '/')

    # --- Título ---
    titulo_bruto = (_procurar_titulo(dados) if dados else None) \
        or _titulo_pela_tag_title(conteudo_html)
    titulo_limpo = limpar_nome_arquivo(titulo_bruto) if titulo_bruto else "sem_titulo"

    return titulo_limpo, url_m3u8