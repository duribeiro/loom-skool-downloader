import os
import threading
import traceback
import uuid
from flask import Blueprint, request, jsonify
from concurrent.futures import ThreadPoolExecutor

# Importa a "Base de Dados" visual (lista global) do dashboard
from dashboard import DASHBOARD_DATA

# Importa nossos serviços via __init__.py
from services import (
    extrair_metadados,
    limpar_nome_arquivo,
    prefixo_de_ordem,
    limite_do_nome,
    PISO_NOME,
    limpar_pasta,
    processar_download,
    converter_final,
    salvar_aula_md,
    imagens_do_desc,
    PASTA_OUTPUT,
    baixar_youtube,
    eh_url_youtube,
    titulo_do_youtube,
    canal_do_youtube,
    baixar_vimeo,
    eh_url_vimeo,
    titulo_do_vimeo,
    baixar_skool,
    eh_url_skool_video,
    baixar_loom,
    eh_url_loom,
    titulo_do_loom,
    baixar_anexos,
    registrar_erro,
    limpar_erro,
    PASTA_TEMP_RAIZ
)

# Cria o Blueprint (um módulo da aplicação Flask)
download_bp = Blueprint('download', __name__)

# Pasta que a extensão manda quando o vídeo vem de um LINK COLADO (popup ou botão
# na página do YouTube). Só nesse caso faz sentido subdividir por canal.
PASTA_LINK_YOUTUBE = 'YouTube'

# Quantas aulas baixam ao mesmo tempo. O gargalo real é local (ffmpeg fundindo
# vídeo+áudio e disco), não o servidor remoto: os downloads usam URLs assinadas de
# CDN, que são feitas para entrega paralela. Ajustável sem editar código:
#   SIFAO_DOWNLOADS_SIMULTANEOS=6 python server/app.py
try:
    _SIMULTANEOS = max(1, int(os.environ.get('SIFAO_DOWNLOADS_SIMULTANEOS', '4')))
except ValueError:
    _SIMULTANEOS = 4

executor = ThreadPoolExecutor(max_workers=_SIMULTANEOS)

# Faixa da barra reservada para a CONVERSÃO. O download nunca chega a 100%: assim
# a barra cheia significa "pronto", e não "esperando o ffmpeg". As faixas do
# download (vídeo/áudio) estão em `services/ytdlp.py`.
FAIXA_CONVERSAO = (85, 99)

# --- 0. ORGANIZAÇÃO EM PASTA POR AULA ---
# Uma aula pode render vários arquivos (mp4 + md + anexos). Soltos no módulo, eles
# se misturam com os das aulas vizinhas. Por isso TODA aula ganha pasta própria —
# ver o bloco longo em `worker_download`, que explica por que a regra antiga
# ("só a partir de 2 arquivos") rebaixava curso inteiro.

def _adotar_arquivos_soltos(pasta_pai_abs, pasta_aula_abs, nome_limpo):
    """Move para a pasta da aula o que já havia sido baixado solto.

    Sem isto, mudar o layout faria o servidor NÃO encontrar o .mp4 antigo (ele
    procura no caminho novo) e rebaixar tudo do zero — 277 vídeos já em disco.
    Mover é instantâneo e preserva o trabalho já feito.
    """
    if not os.path.isdir(pasta_pai_abs):
        return 0

    movidos = 0
    for nome_arquivo in os.listdir(pasta_pai_abs):
        origem = os.path.join(pasta_pai_abs, nome_arquivo)
        if not os.path.isfile(origem):
            continue

        base, ext = os.path.splitext(nome_arquivo)

        # O .mp4/.md da aula, e os anexos que foram gravados com o prefixo dela.
        #
        # O PREFIXO SÓ VALE PARA ANEXO. Antes a regra do prefixo valia para qualquer
        # arquivo, e aí a aula "Aula 1" adotava o `Aula 1 - Extra.mp4` da aula VIZINHA
        # chamada "Aula 1 - Extra": a vizinha então procurava o vídeo na pasta dela,
        # não achava, e rebaixava — perdendo exatamente a propriedade que esta função
        # existe para proteger. `migrar_layout.py:22-23` já conhece essa ambiguidade e
        # a resolve com "prefixo mais longo vence"; aqui o worker não enxerga as aulas
        # irmãs, então o corte é por tipo: vídeo e texto exigem nome EXATO.
        #
        # Isso é seguro porque o layout antigo nomeava vídeo/texto sempre como
        # `<Aula>.mp4` / `<Aula>.md`; só o anexo levava o prefixo `<Aula> - `.
        if ext.lower() in ('.mp4', '.md'):
            pertence = base == nome_limpo
        else:
            pertence = base == nome_limpo or nome_arquivo.startswith(f"{nome_limpo} - ")
        if not pertence:
            continue

        # O PREFIXO `<Aula> - ` CAI NA ADOÇÃO.
        #
        # Dentro da pasta da aula ele é redundante, e mantê-lo criava duplicata: o
        # `baixar_anexos` grava o nome NU (`template.json`), então na execução
        # seguinte a checagem de "já existe" não encontrava `Aula X - template.json`
        # e baixava o arquivo de novo, deixando os dois lado a lado.
        # `migrar_layout._destino_do_arquivo` já tira o prefixo; aqui não tirava.
        nome_destino = nome_arquivo
        if ext.lower() not in ('.mp4', '.md'):
            prefixo = f"{nome_limpo} - "
            if nome_arquivo.startswith(prefixo):
                nome_destino = nome_arquivo[len(prefixo):]

        os.makedirs(pasta_aula_abs, exist_ok=True)
        destino = os.path.join(pasta_aula_abs, nome_destino)
        if os.path.exists(destino):
            continue          # já existe no lugar novo: não sobrescreve nada
        try:
            os.replace(origem, destino)
            movidos += 1
        except OSError as erro:
            print(f"⚠️  Não consegui mover '{nome_arquivo}' para a pasta da aula: {erro}")

    if movidos:
        print(f"📁 {movidos} arquivo(s) já baixado(s) movido(s) para a pasta de '{nome_limpo}'")
    return movidos


def _pasta_existente_da_aula(pasta_pai_abs, nome_limpo):
    """Acha a pasta desta aula mesmo que ela tenha PREFIXO DE ORDEM.

    `Modulo/07 - Aula X/` é a pasta de "Aula X". Sem isto, numerar as pastas para
    respeitar a ordem do curso faria o servidor não achar nada e REBAIXAR a
    biblioteca inteira — 522 aulas, 62 GB medidos em 12/08/2026.

    É esta função que torna a numeração barata: se o curso for reordenado no Skool,
    renumerar vira um rename local, sem custo de download.

    O prefixo aceito é ESTRITO — só dígitos seguidos de " - ". Uma aula de verdade
    chamada "Bônus - Aula X" não pode ser confundida com a numeração.

    Devolve o nome real da pasta, ou None.
    """
    if not os.path.isdir(pasta_pai_abs):
        return None

    try:
        nomes = os.listdir(pasta_pai_abs)
    except OSError:
        return None

    return (_equivalentes(pasta_pai_abs, nome_limpo, nomes) or [None])[0]


def _equivalentes(pasta_pai_abs, nome_limpo, nomes=None):
    """Todas as pastas que representam esta aula, NUMERADAS PRIMEIRO.

    A ordem importa e já causou estrago. A versão anterior devolvia de imediato a
    pasta SEM número quando ela existia (`if nome == nome_limpo: return nome`), e aí,
    num diretório com `Dia 3` E `03 - Dia 3`, ela escolhia a antiga, tentava renomear
    para a nova, levava "já existe" e gravava na antiga — **para sempre**. O estado
    partido nunca se curava, nem repetindo o download.

    RELATADO e reproduzido em 13/08/2026: `Bootcamp Mês 1` ficou com as duas pastas,
    e um vídeo de 89,84 MB foi rebaixado à toa (hash idêntico ao que já existia).

    Preferir a numerada faz o servidor convergir para o estado desejado em vez de
    ficar preso no antigo.
    """
    if nomes is None:
        try:
            nomes = os.listdir(pasta_pai_abs)
        except OSError:
            return []

    exatos, numerados = [], []
    sufixo = f" - {nome_limpo}"
    for nome in nomes:
        if not os.path.isdir(os.path.join(pasta_pai_abs, nome)):
            continue
        if nome == nome_limpo:
            exatos.append(nome)
        elif nome.endswith(sufixo) and nome[:-len(sufixo)].isdigit():
            numerados.append(nome)

    if len(numerados) + len(exatos) > 1:
        print(f"⚠️  '{nome_limpo}' existe em {len(numerados) + len(exatos)} pastas: "
              f"{sorted(numerados + exatos)} — usando a numerada.")
    return sorted(numerados) + exatos


def _sem_prefixo_de_ordem(nome):
    """'03 - Aula X' -> 'Aula X'. Só corta prefixo de DÍGITOS."""
    prefixo, sep, resto = nome.partition(" - ")
    return resto if sep and prefixo.isdigit() else nome


def _resolver_componente(pasta_pai_abs, nome_desejado):
    """Resolve UM componente do caminho, reaproveitando a pasta que já existe.

    Devolve o nome a usar. Se existir uma pasta equivalente (mesmo nome, com ou sem
    prefixo de ordem) e o número mudou, RENOMEIA em vez de criar outra.
    """
    nome_base = _sem_prefixo_de_ordem(nome_desejado)
    candidatas = _equivalentes(pasta_pai_abs, nome_base)

    if not candidatas:
        return nome_desejado

    if nome_desejado == nome_base:
        # PEDIDO SEM ORDEM (link colado, curso sem `children`). Não sabemos a
        # posição, então não renomeamos nada — mas usamos a pasta NUMERADA se ela
        # existir. `candidatas` já vem com as numeradas na frente.
        #
        # Devolver a sem número aqui foi o que manteve o `Dia 3` partido: o pill
        # ressuscitava a pasta antiga a cada tentativa.
        return candidatas[0]

    # PEDIDO COM ORDEM. A pasta que já tem o nome certo vence qualquer rename —
    # sem isto, um diretório com `Dia 3` E `03 - Dia 3` tentava renomear a antiga
    # por cima da nova, levava "já existe" e ficava preso na antiga para sempre.
    if nome_desejado in candidatas:
        return nome_desejado
    return _renomear_pasta_da_aula(pasta_pai_abs, candidatas[0], nome_desejado)


# Resolver o caminho é LER-DECIDIR-RENOMEAR, e isso não é atômico.
#
# CAUSA MEDIDA em 13/08/2026: os 4 workers baixam em paralelo e duas aulas do MESMO
# módulo caíram juntas. O worker A leu `Dia 3`, renomeou para `03 - Dia 3` e gravou
# ali; o worker B, que já tinha lido `Dia 3` antes do rename, recriou a pasta antiga
# com `os.makedirs` e baixou 89,84 MB que já existiam (hash idêntico, conferido).
# Sobraram as duas pastas, e o servidor passou a gravar sempre na errada.
#
# O trecho protegido é curto (um `listdir` e talvez um `rename`), então serializar
# não custa vazão perceptível — o download em si segue paralelo.
_TRAVA_CAMINHO = threading.Lock()


def _resolver_caminho(pasta_relativa):
    """Aplica `_resolver_componente` a CADA nível do caminho, de cima para baixo.

    ISTO É O QUE IMPEDE O REBAIXE DE 62 GB. Quem numera o módulo é a EXTENSÃO
    (`caminhoDaAula`), então o pedido chega com `Comunidade/Curso/01 - Dia 1`. Se
    olhássemos só a pasta da AULA — como fazia a primeira versão desta mudança —,
    o módulo `01 - Dia 1` não existiria em disco, uma árvore numerada inteira
    nasceria ao lado da antiga e TODAS as aulas seriam rebaixadas.

    PEGO NA REVISÃO em 12/08/2026, e medido: com `Com/Curso/Dia 1/Aula 1/` em disco,
    um pedido para `Com/Curso/01 - Dia 1` resolvia para `01 - Dia 1/01 - Aula 1` —
    caminho inexistente. Exatamente a falha que a trava existia para evitar, um
    nível acima de onde ela olhava.
    """
    partes = [p for p in pasta_relativa.replace('\\', '/').split('/') if p]
    resolvido = []
    for parte in partes:
        pai_abs = os.path.join(PASTA_OUTPUT, *resolvido) if resolvido else PASTA_OUTPUT
        resolvido.append(_resolver_componente(pai_abs, parte))
    return os.path.join(*resolvido) if resolvido else pasta_relativa


def _renomear_pasta_da_aula(pasta_pai_abs, nome_atual, nome_desejado):
    """Renomeia a pasta da aula para a numeração nova. Devolve o nome em uso.

    NUNCA sobrescreve: se o destino já existe, mantém o nome atual. Duas pastas
    disputando o mesmo número é estado inconsistente, e mesclá-las aqui — no meio de
    um download, sem o usuário ver — poderia enterrar arquivo.

    Falha de rename não é fatal: a pasta antiga continua servindo (a aula é
    encontrada por `_pasta_existente_da_aula` de qualquer jeito). Perder a
    numeração é chato; perder o download seria pior.
    """
    destino = os.path.join(pasta_pai_abs, nome_desejado)
    if os.path.exists(destino):
        print(f"⚠️  Não renomeei '{nome_atual}': '{nome_desejado}' já existe.")
        return nome_atual

    try:
        os.rename(os.path.join(pasta_pai_abs, nome_atual), destino)
        print(f"🔢 '{nome_atual}' → '{nome_desejado}'")
        return nome_desejado
    except OSError as erro:
        print(f"⚠️  Não consegui renomear '{nome_atual}': {erro}")
        return nome_atual


def _marcar_erro(item_dashboard, nome, pasta, motivo):
    """Marca o item como erro guardando O MOTIVO — no item e em disco.

    Antes só o status virava 'erro'; o motivo saía por `print` e o dashboard
    (`Live(screen=True)`) repintava por cima em ~250ms. MEDIDO em 12/08/2026: o
    painel dizia "1 erro" e não havia como saber se falhou o vídeo, o texto ou o
    anexo — a informação existia e era destruída no mesmo segundo.
    """
    item_dashboard['status'] = 'erro'
    item_dashboard['motivo'] = motivo
    registrar_erro(nome, pasta, motivo)
    print(f"\n❌ ERRO em '{nome}': {motivo}")


def _worker_blindado(url, pasta_destino, nome_arquivo_sugerido, item_dashboard,
                     desc=None, resources=None, referer=None, anexos=None,
                     ordem=None, ordem_total=None):
    """Roda `worker_download` sem deixar exceção nenhuma sumir.

    O `ThreadPoolExecutor` guarda a exceção no `Future` e só a mostra quando
    alguém chama `.result()` — e ninguém chamava. Efeito medido no uso real: um
    worker que estourava deixava o item preso em `status='baixando'` com 0% para
    SEMPRE, enquanto a vaga era liberada e a fila seguia. O painel chegou a
    mostrar 6 aulas "baixando" com só 4 vagas — duas eram cadáveres.

    Isso é pior que uma falha barulhenta: a aula não baixa, não acusa erro, e o
    número de ativos mente. Aqui a exceção vira status 'erro' e traceback no
    terminal, que é o mínimo para alguém poder investigar.
    """
    try:
        worker_download(url, pasta_destino, nome_arquivo_sugerido, item_dashboard,
                        desc, resources, referer, anexos, ordem, ordem_total)
    except BaseException as erro:
        nome = item_dashboard.get('nome') or nome_arquivo_sugerido or '?'
        # A pasta sai do ITEM, não do parâmetro: `worker_download` rebinda
        # `pasta_destino` no meio do caminho (subpasta de canal do YouTube, pasta da
        # aula) e mantém o item em dia. Usar o parâmetro registraria o MÓDULO num log
        # cuja única função é dizer onde a falha aconteceu.
        pasta = item_dashboard.get('folder') or pasta_destino
        _marcar_erro(item_dashboard, nome, pasta,
                     f"worker morreu: {type(erro).__name__}: {erro}")
        traceback.print_exc()


# --- 1. A LÓGICA DO TRABALHADOR (WORKER) ---
# Esta função roda em "segundo plano" (background) para não travar o servidor.
def worker_download(url, pasta_destino, nome_arquivo_sugerido, item_dashboard,
                    desc=None, resources=None, referer=None, anexos=None,
                    ordem=None, ordem_total=None):
    """
    Executa o ciclo completo de vida de uma aula:
    Preparar -> (baixar vídeo) -> (converter) -> (gravar texto) -> Limpar

    Três casos, todos suportados:
    - vídeo + texto: baixa o .mp4 e grava o .md
    - só vídeo: baixa o .mp4
    - só texto (url vazia): grava apenas o .md
    """

    # Atualiza o status visual para "Baixando"
    item_dashboard['status'] = 'baixando'

    # A. Resolver o Nome do Arquivo
    # Se o pedido não trouxe nome (ex.: link colado no popup), descobrimos o título.
    # YouTube -> yt-dlp; Loom/embed -> extrator do Loom. Rotear aqui evita que uma
    # URL de YouTube caia no extrator do Loom e volte lixo.
    if not nome_arquivo_sugerido and url:
        if eh_url_youtube(url):
            nome_arquivo_sugerido = titulo_do_youtube(url)
        elif eh_url_vimeo(url):
            nome_arquivo_sugerido = titulo_do_vimeo(url, referer)
        elif eh_url_skool_video(url):
            # A URL do Skool é um .m3u8 puro: não tem título embutido para extrair.
            # Na prática a extensão sempre manda o nome da aula, então isto é só
            # uma rede de segurança para não cair no extrator do Loom e voltar lixo.
            nome_arquivo_sugerido = "Aula do Skool"
        elif eh_url_loom(url):
            # Mesma fonte que baixa o vídeo. Antes o título saía de
            # `extrair_metadados` (scraping do __APOLLO_STATE__) enquanto o download
            # ia por outro caminho — duas mecânicas para o mesmo vídeo divergem por
            # construção, e é o scraping que já quebrou uma vez, quando o Loom
            # renomeou `playlist.m3u8`.
            nome_arquivo_sugerido = titulo_do_loom(url)
        else:
            titulo_extraido, _ = extrair_metadados(url)
            nome_arquivo_sugerido = titulo_extraido

    # Limpa caracteres proibidos (ex: remove "?", "/", ":")
    nome_limpo = limpar_nome_arquivo(nome_arquivo_sugerido)
    item_dashboard['nome'] = nome_limpo  # Atualiza o nome bonitinho no painel

    # YouTube: organiza por canal — output/YouTube/<Canal>/<Titulo>.mp4, a mesma
    # logica de pastas do Skool. O canal vem do proprio yt-dlp, entao vale para
    # qualquer entrada (botao na pagina, popup ou link colado). Se o canal nao
    # resolver, grava direto na pasta raiz (sem subpasta), sem quebrar nada.
    # SÓ para link colado. Antes isto valia para QUALQUER URL de YouTube, e uma aula
    # do Skool cujo vídeo mora no YouTube ganhava uma pasta com o nome do CANAL no
    # meio do caminho — nível que não existe no Skool. O efeito: a aula saía da
    # sequência do módulo (ex.: as aulas 1,2,4,6 de Chatwoot soltas e a 5 enterrada
    # em 'Gabriel Morais/'), e 47 vídeos de Office Hours foram parar em 'Maven AI/'
    # e 'Well Pires/'. Quando o pedido vem de um curso, a pasta já é
    # Comunidade/Curso/Módulo e não deve ganhar mais um nível.
    if url and eh_url_youtube(url) and pasta_destino.strip(os.sep + '/') == PASTA_LINK_YOUTUBE:
        canal = canal_do_youtube(url)
        if canal:
            pasta_destino = os.path.join(pasta_destino, limpar_nome_arquivo(canal))
            item_dashboard['folder'] = pasta_destino

    # TODA aula ganha pasta própria — com 1 arquivo ou com 5.
    #
    # O LUGAR É FUNÇÃO DA IDENTIDADE DA AULA. O conteúdo só decide QUAIS arquivos
    # existem, nunca ONDE eles ficam.
    #
    # Antes, a pasta nascia só a partir de 2 artefatos (`_quantos_artefatos >= 2`),
    # e isso amarrava o CAMINHO ao CONTEÚDO do pedido: com `desc` vinham 2 artefatos
    # e a aula ganhava pasta; sem `desc` vinha 1 e o arquivo ficava solto. Mesma aula,
    # dois caminhos, decididos por um fetch HTTP ter dado certo ou não.
    #
    # MEDIDO no uso real (12/08/2026): o "pular o que já baixou" procurava o .mp4 num
    # caminho que a própria regra tinha mudado — não achava, REBAIXAVA o curso inteiro
    # e largava o vídeo solto AO LADO da pasta antiga, sem .md. Não foi descuido: era
    # a regra funcionando como estava escrita.
    #
    # Com pasta sempre, o caminho é idempotente e a pergunta "já baixei?" tem um lugar
    # só. Custo aceito: um clique a mais para chegar num vídeo de aula que só tem vídeo.
    # O CAMINHO INTEIRO é resolvido contra o que já existe — MÓDULO INCLUSIVE, não
    # só a aula. Quem numera o módulo é a EXTENSÃO (`caminhoDaAula`), então o pedido
    # chega como `Comunidade/Curso/01 - Dia 1`.
    #
    # PEGO NA REVISÃO em 12/08/2026: a primeira versão desta mudança olhava só a
    # pasta da AULA. Medido — com `Com/Curso/Dia 1/Aula 1/` em disco, um pedido para
    # `Com/Curso/01 - Dia 1` resolvia para `01 - Dia 1/01 - Aula 1`, caminho que não
    # existe: a árvore numerada inteira nasceria ao lado da antiga e TODAS as aulas
    # seriam rebaixadas. Exatamente a falha que a trava existia para evitar, um nível
    # acima de onde ela olhava.
    #
    # TUDO ISTO SOB UMA TRAVA, e a criação da pasta junto: sem ela, dois workers do
    # mesmo módulo se atropelam (ver `_TRAVA_CAMINHO`). O `makedirs` entra dentro da
    # trava de propósito — se ficasse fora, o segundo worker leria o diretório antes
    # de o primeiro tê-lo criado e recriaria a pasta antiga.
    with _TRAVA_CAMINHO:
        pasta_pai = _resolver_caminho(
            pasta_destino[1:] if pasta_destino.startswith(os.sep) else pasta_destino)
        pasta_pai_limpa = pasta_pai

        # Onde o número muda, a pasta é RENOMEADA em vez de duplicada. Assim um
        # "baixar tudo" — que pula tudo o que já existe — vira uma RENUMERAÇÃO
        # COMPLETA sem baixar um byte, e uma reordenação no Skool sai de graça.
        pasta_pai_abs = os.path.join(PASTA_OUTPUT, pasta_pai_limpa)
        prefixo = prefixo_de_ordem(ordem, ordem_total)

        # ORÇAMENTO DO CAMINHO INTEIRO, agora que a pasta-pai é conhecida.
        #
        # `LIMITE_NOME` é teto por COMPONENTE; o limite do Windows é do caminho
        # inteiro. MEDIDO em 13/08/2026: com a `output/` dentro do projeto (82 chars
        # só de prefixo), o pior caso deu 277 mesmo com o nome já em 80 — e aí o
        # `Get-ChildItem` do PowerShell reporta a pasta como VAZIA, escondendo 1,1 GB.
        #
        # Aqui o nome encolhe só o quanto for preciso. Com a `output/` num lugar
        # normal (Vídeos, Downloads) isto não age em nenhum arquivo do acervo atual.
        limite = limite_do_nome(pasta_pai_abs, extensao=".mp4", prefixo=prefixo)
        if len(nome_limpo) > limite:
            print(f"✂️  Nome encurtado para caber no caminho ({limite} chars): {nome_limpo}")
            nome_limpo = limpar_nome_arquivo(nome_limpo, limite=limite)
            item_dashboard['nome'] = nome_limpo
            if limite <= PISO_NOME:
                print(f"⚠️  A pasta de destino é funda demais; escolha um caminho "
                      f"mais curto para a biblioteca.")

        nome_desejado = prefixo + nome_limpo
        nome_da_pasta = _resolver_componente(pasta_pai_abs, nome_desejado)

        try:
            os.makedirs(os.path.join(pasta_pai_abs, nome_da_pasta), exist_ok=True)
        except OSError as erro:
            print(f"⚠️  Não consegui criar a pasta da aula '{nome_da_pasta}': {erro}")

    pasta_destino = os.path.join(pasta_pai, nome_da_pasta)
    item_dashboard['folder'] = pasta_destino

    # Recolhe o que já estava solto de execuções anteriores, para não rebaixar.
    pasta_aula_limpa = pasta_destino[1:] if pasta_destino.startswith(os.sep) else pasta_destino
    _adotar_arquivos_soltos(os.path.join(PASTA_OUTPUT, pasta_pai_limpa),
                            os.path.join(PASTA_OUTPUT, pasta_aula_limpa),
                            nome_limpo)

    # Define onde ficarão os arquivos temporários (.ts).
    #
    # O SUFIXO ÚNICO NÃO É ENFEITE. Antes a temp era só `hls-temp/<nome da aula>`, e
    # nome de aula se repete: duas "Introdução" em módulos diferentes dividiam a MESMA
    # pasta de trabalho. Com 4 workers simultâneos, a que terminasse primeiro chamava
    # `limpar_pasta` e apagava os segmentos da outra no meio da conversão — perda de
    # dado silenciosa, que o painel reportaria como erro genérico.
    #
    # O risco é anterior a esta mudança (a linha era idêntica em dc68c70), mas o teto
    # de 80 chars aumenta a chance: dois títulos longos podem colapsar no mesmo nome.
    # O uuid custa nada e fecha o caso todo.
    caminho_pasta_temp = os.path.join(PASTA_TEMP_RAIZ, f"{nome_limpo}_{uuid.uuid4().hex[:8]}")

    # B. Função de Callback
    # O downloader chama isso a cada pedacinho baixado para atualizar a barra
    def atualizar_progresso(total=None, percentual=None):
        # PERCENTUAL ABSOLUTO (0..100 da AULA inteira, não da faixa atual).
        # Cada etapa ocupa uma faixa da barra — ver FAIXA_DA_FASE em ytdlp.py.
        # Assim 100% passa a significar PRONTO, e só isso: antes a barra enchia no
        # fim do vídeo e ficava parada em 100% durante áudio e conversão, dando a
        # impressão de travamento. `max` porque barra que anda para trás parece
        # trabalho perdido.
        if percentual is not None:
            novo = max(0, min(100, int(percentual)))
            if item_dashboard.get('total') != 100:
                # TROCA DE UNIDADE: até aqui `progresso` contava SEGMENTOS (o caminho
                # HLS do Loom conta de 0 a N, com `total` = N). Comparar isso com um
                # percentual é somar laranja com maçã.
                #
                # MEDIDO em 12/08/2026: num vídeo de 300 segmentos, `progresso`
                # chegava a 300 e o `max(300, 85)` congelava a barra em 100% durante
                # TODA a conversão — que é a queixa original ("fica travada em 100% e
                # não avança"). A faixa 85→99 do ffmpeg nunca chegou a valer no
                # caminho do Loom, mesmo depois de ela ter sido dada como pronta.
                item_dashboard['total'] = 100
                item_dashboard['progresso'] = novo
            else:
                item_dashboard['progresso'] = max(item_dashboard.get('progresso', 0),
                                                  novo)
        elif total:
            # Total novo = FAIXA nova. O yt-dlp baixa vídeo e áudio como downloads
            # separados e reporta o total uma vez por faixa; sem zerar o progresso
            # junto, o contador do áudio seguia de onde o vídeo parou e a barra
            # marcava 200% — verde cheio com número absurdo. RELATADO no uso real.
            item_dashboard['total'] = total
            item_dashboard['progresso'] = 0
        else:
            item_dashboard['progresso'] += 1

    # O yt-dlp avisa quando entra na fusão vídeo+áudio. Sem isto o painel ficava com
    # a barra em 100% e o rótulo "Baixando" durante todo o merge do ffmpeg, parecendo
    # travado. O caminho do Loom já sinalizava isso na mão (item E, mais abaixo).
    def marcar_convertendo():
        item_dashboard['status'] = 'convertendo'
        item_dashboard['eta'] = None      # o ffmpeg não estima; melhor nada que mentira
        # Entra na faixa da conversão em vez de ficar nos 100% do download.
        item_dashboard['total'] = 100
        item_dashboard['progresso'] = max(item_dashboard.get('progresso', 0), FAIXA_CONVERSAO[0])

    def marcar_progresso_conversao(fracao):
        """0..1 dentro da faixa da conversão. Vem do `-progress` do ffmpeg."""
        ini, fim = FAIXA_CONVERSAO
        atualizar_progresso(percentual=ini + max(0.0, min(1.0, fracao)) * (fim - ini))

    # A FASE do yt-dlp (vídeo / áudio) e o tempo restante da faixa atual. Vídeo e
    # áudio são downloads separados: sem isto o painel dizia só "Baixando" e a barra
    # parecia congelada em 100% durante todo o áudio. RELATADO no uso real.
    def marcar_fase(fase, eta):
        item_dashboard['status'] = fase
        item_dashboard['eta'] = eta

    # C. Gravar o texto da aula (independe do vídeo; aula só-texto também tem).
    # Sem vídeo, gravamos o .md mesmo vazio (placeholder) — assim uma aula do
    # curso nunca é omitida em silêncio.
    try:
        caminho_md = salvar_aula_md(nome_limpo, pasta_destino, desc, resources,
                                    permitir_vazio=not url)
        if caminho_md:
            item_dashboard['tem_texto'] = True
    except Exception as erro:
        print(f"⚠️  Não foi possível gravar o texto de '{nome_limpo}': "
              f"{type(erro).__name__}: {erro}")

    # C.2. Arquivos anexos da aula. Vem ANTES do vídeo de propósito: em cursos como a
    # Biblioteca de Templates o anexo é o produto e o vídeo só o explica — se o vídeo
    # falhar, o material principal já está salvo.
    try:
        if anexos:
            baixados, falhas_anexo = baixar_anexos(anexos, pasta_destino)
            if baixados:
                item_dashboard['anexos'] = baixados
            if falhas_anexo:
                print(f"⚠️  {falhas_anexo} anexo(s) falharam em '{nome_limpo}'.")
    except Exception as erro:
        print(f"⚠️  Não foi possível baixar anexos de '{nome_limpo}': "
              f"{type(erro).__name__}: {erro}")

    # C.3. IMAGENS DE DENTRO DO TEXTO.
    #
    # RELATADO em 13/08/2026 (BACKROOM.EXE): "os links estão presentes, mas a imagem
    # não foi inserida no Markdown". O nó `image` não tinha caso no renderizador e
    # sumia em silêncio.
    #
    # Baixamos em vez de só linkar: a `src` do Skool pode sair do ar, e a biblioteca
    # existe para funcionar offline. `imagens_do_desc` devolve a MESMA forma dos
    # anexos ({url, nome}), então reaproveita `baixar_anexos` — e o nome de arquivo
    # sai da mesma função que o Markdown usa na referência, senão o texto apontaria
    # para um arquivo inexistente.
    try:
        imagens = imagens_do_desc(desc)
        if imagens:
            baixadas, falhas_img = baixar_anexos(imagens, pasta_destino)
            if falhas_img:
                print(f"⚠️  {falhas_img} imagem(ns) do texto falharam em '{nome_limpo}'.")
    except Exception as erro:
        print(f"⚠️  Não foi possível baixar imagens do texto de '{nome_limpo}': "
              f"{type(erro).__name__}: {erro}")

    # D. Baixar o vídeo, se houver
    video_ok = False
    # Motivo padrão: cada ramo que sabe MAIS que isto sobrescreve. Nascer preenchido
    # evita que um caminho novo caia no relatório final sem motivo nenhum — que é
    # exatamente o buraco que este bloco veio fechar.
    motivo_falha = "o download do vídeo não terminou (motivo não identificado)"
    if not url:
        # Aula só de texto: sucesso se o .md foi gravado.
        item_dashboard['total'] = 1
        item_dashboard['progresso'] = 1
        # Anexo conta como entrega: uma aula que só carrega um arquivo (comum na
        # Biblioteca de Templates) não é erro se o arquivo veio.
        sucesso_operacao = bool(item_dashboard.get('tem_texto')
                                or item_dashboard.get('anexos'))
        if sucesso_operacao:
            item_dashboard['status'] = 'sucesso'
            limpar_erro(nome_limpo, pasta_destino)
        else:
            _marcar_erro(item_dashboard, nome_limpo, pasta_destino,
                         "aula sem vídeo não gerou nem .md nem anexo")
        return

    if eh_url_youtube(url):
        # YouTube: o yt-dlp resolve formato + fusão vídeo/áudio com ffmpeg.
        # Não passa pelo HLS nem pelo converter — grava direto o .mp4 final.
        video_ok = baixar_youtube(url, pasta_destino, nome_limpo, atualizar_progresso,
                                  ao_converter=marcar_convertendo, ao_fase=marcar_fase)
        if not video_ok:
            motivo_falha = "yt-dlp não baixou o vídeo do YouTube (ver stderr do yt-dlp)"
    elif eh_url_vimeo(url):
        # Vimeo (privado no Skool): mesmo motor do YouTube, mas com o Referer da
        # página — é o que libera o vídeo restrito por domínio.
        video_ok = baixar_vimeo(url, pasta_destino, nome_limpo, referer, atualizar_progresso,
                                ao_converter=marcar_convertendo, ao_fase=marcar_fase)
        if not video_ok:
            motivo_falha = "yt-dlp não baixou o Vimeo (Referer recusado? vídeo privado?)"
    elif eh_url_skool_video(url):
        # Vídeo hospedado no próprio Skool (Mux). A extensão já resolveu o token e
        # mandou o .m3u8 pronto — aqui é só baixar. Não passa pelo motor HLS do Loom:
        # o master do Mux tem URIs absolutas e nomes de segmento que colidem entre
        # vídeo e áudio (ver services/skool.py).
        video_ok = baixar_skool(url, pasta_destino, nome_limpo, atualizar_progresso,
                                ao_converter=marcar_convertendo, ao_fase=marcar_fase)
        if not video_ok:
            # O token do Skool dura ~24h e uma fila longa alcança a expiração;
            # `_diagnosticar` (skool.py) já separa isso de erro genérico.
            motivo_falha = "vídeo do Skool não baixou (token expirado? reenfileire o curso)"
    elif eh_url_loom(url):
        # Loom pelo yt-dlp, e não pelo motor HLS próprio (`processar_download`).
        #
        # MEDIDO em 14/08/2026 (NoeAI Automator): a assinatura do master do Loom é
        # escopada ao ARQUIVO — a policy diz `"Resource": ".../<id>.m3u8"` —, e o
        # motor próprio reaproveita essa query para buscar `-video0.m3u8` e
        # `-audio0.m3u8`. Os dois respondem 403 AccessDenied. 53 aulas falharam
        # assim, nas duas tentativas, sempre as mesmas. O yt-dlp pede as URLs
        # assinadas à GraphQL do Loom em vez de adivinhá-las.
        #
        # No vídeo em que os dois funcionam, empatam em 1920x1080. Ver services/loom.py.
        video_ok = baixar_loom(url, pasta_destino, nome_limpo, atualizar_progresso,
                               ao_converter=marcar_convertendo, ao_fase=marcar_fase)
        if not video_ok:
            motivo_falha = "yt-dlp não baixou o Loom (vídeo removido ou sem acesso?)"
    else:
        # Loom (e afins via embed): extrai o .m3u8 e baixa o HLS.
        _, url_m3u8 = extrair_metadados(url)

        if not url_m3u8:
            # Distinguir as três falhas do caminho HLS importa: "não achei o .m3u8"
            # é problema de extração (a página do Loom mudou), "download falhou" é
            # rede, e "conversão falhou" é FFmpeg. Um "erro" genérico não separava.
            motivo_falha = "não achei o .m3u8 na página do embed"
        else:
            download_ok, motivo_hls = processar_download(
                url_m3u8,
                caminho_pasta_temp,
                nome_limpo,
                pasta_destino,
                atualizar_progresso
            )

            if not download_ok:
                # O motivo vem de dentro do motor. O rótulo fixo que existia aqui
                # ("download dos segmentos HLS falhou") era SEMPRE falso: falha de
                # segmento nem chega a este ramo. Ele escondeu 108 falhas da NoeAI
                # Automator em 14/08/2026 atrás de uma causa que não existia.
                motivo_falha = motivo_hls or "o motor HLS desistiu sem dizer o motivo"
            else:
                item_dashboard['status'] = 'convertendo'
                if converter_final(nome_limpo, pasta_destino, caminho_pasta_temp,
                           ao_progresso=marcar_progresso_conversao):
                    limpar_pasta(caminho_pasta_temp)
                    video_ok = True
                else:
                    motivo_falha = "FFmpeg não converteu os segmentos em .mp4"

    # E. Finalização e Relatório
    if video_ok:
        item_dashboard['status'] = 'sucesso'
        item_dashboard['progresso'] = item_dashboard['total']  # Garante barra 100%
        # A aula deu certo: se ela estava no log de uma execução anterior, sai de lá.
        # O log responde "o que está quebrado AGORA" — ver services/registro.py.
        limpar_erro(nome_limpo, pasta_destino)
    else:
        _marcar_erro(item_dashboard, nome_limpo, pasta_destino, motivo_falha)
        # Em caso de erro, limpamos a temp para não deixar lixo corrompido ocupando espaço
        limpar_pasta(caminho_pasta_temp)

# --- 2. DEFINIÇÃO DA ROTA (O RECEPCIONISTA) ---
@download_bp.route('/baixar', methods=['POST'])
def rota_receber_pedido():
    """
    Recebe o JSON vindo da extensão do Chrome.
    Exemplo de JSON: { "url": "...", "folder": "Curso/Modulo1", "filename": "Aula 1" }
    """
    dados_request = request.json

    # Cria o objeto de dados que vai aparecer no Dashboard (Terminal)
    novo_item_dashboard = {
        'nome': dados_request.get('filename', 'Verificando...'),
        'status': 'fila',       # Começa na fila
        'progresso': 0,
        'total': 1,             # Valor provisório até começar
        'url': dados_request.get('url'),
        'folder': dados_request.get('folder')
    }

    # Adiciona na lista global (para o dashboard.py ler)
    DASHBOARD_DATA.append(novo_item_dashboard)

    # Envia para a fila de execução (Thread)
    # O servidor responde "OK" imediatamente, sem esperar o download acabar.
    # desc/resources são opcionais: quando presentes, geram o .md da aula.
    executor.submit(
        _worker_blindado,
        novo_item_dashboard['url'],
        novo_item_dashboard['folder'],
        novo_item_dashboard['nome'],
        novo_item_dashboard,
        dados_request.get('desc'),
        dados_request.get('resources'),
        dados_request.get('referer'),
        dados_request.get('anexos'),
        # Posição da aula no módulo, para a pasta refletir a ordem do curso em vez
        # da alfabética. Ausente = pedido sem ordem conhecida (link colado, Loom
        # avulso): grava sem número, nunca inventa posição.
        dados_request.get('ordem'),
        dados_request.get('ordemTotal')
    )

    return jsonify({"status": "ok", "mensagem": "Adicionado à fila"})