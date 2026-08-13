import os
import time
import threading
from rich.console import Group
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.padding import Padding
from rich import box

# --- BASE DE DADOS EM MEMÓRIA ---
# Esta lista é partilhada entre o routes.py (que adiciona dados)
# e este arquivo (que lê dados para desenhar na tela).
DASHBOARD_DATA = []

# Momento em que cada aula foi observada concluída. Preenchido AQUI, pela thread de
# desenho, e não pelo worker: assim o routes.py/worker não precisa mudar de formato.
# Chave = id() do dict do item (estável enquanto o item viver na lista).
_CONCLUIDAS_EM = {}

_STATUS_FINAL = ('sucesso', 'erro')
_STATUS_ATIVO = ('baixando', 'baixando video', 'baixando audio', 'convertendo')

# Rótulo de cada fase. Sem distinguir vídeo de áudio, o painel dizia só "Baixando"
# e a barra parecia congelada em 100% durante todo o download do áudio — o yt-dlp
# baixa as duas faixas SEPARADAS. Aconteceu de verdade e quase custou um servidor
# derrubado no meio de 400 MB já baixados.
_ROTULO_STATUS = {
    'baixando video': 'Baixando vídeo ⬇',
    'baixando audio': 'Baixando áudio 🔊',
    'convertendo': 'Convertendo ⚙️',
}


def _formatar_eta(segundos):
    """'faltam 3m20s'. Devolve '' quando não há estimativa — melhor calar que chutar."""
    if not isinstance(segundos, (int, float)) or segundos < 0:
        return ''
    s = int(segundos)
    if s >= 3600:
        return f" · faltam {s // 3600}h{(s % 3600) // 60:02d}m"
    if s >= 60:
        return f" · faltam {s // 60}m{s % 60:02d}s"
    return f" · faltam {s}s"


def _instantaneo():
    """
    Cópia rasa da lista global.

    O DASHBOARD_DATA é mutado pelas threads de download SEM lock (ver CLAUDE.md).
    Iterar direto sobre ele arrisca "list changed size during iteration" bem no meio
    de um download. Copiar a referência de cada item é barato e resolve: os dicts em
    si continuam sendo os mesmos objetos, então os campos seguem ao vivo.
    """
    return list(DASHBOARD_DATA)


def _barra(percentual, largura=20, cheio="█", vazio="░"):
    blocos = int((max(0, min(100, percentual)) / 100) * largura)
    return cheio * blocos + vazio * (largura - blocos)


def _partes_do_caminho(item):
    """
    Quebra o 'folder' em (curso, módulo).

    O folder chega como 'Comunidade/Curso/Módulo' (o módulo é opcional) — é o mesmo
    caminho que a extensão monta. Usamos 'Comunidade/Curso' como identidade do curso
    para não fundir dois cursos homônimos de comunidades diferentes.
    """
    pasta = item.get('folder') or ''
    partes = [p for p in pasta.replace('\\', '/').split('/') if p]
    if not partes:
        return ('(sem curso)', None)
    curso = '/'.join(partes[:2])
    modulo = partes[2] if len(partes) > 2 else None
    return (curso, modulo)


def _registrar_conclusoes(itens):
    """Anota o instante em que cada aula terminou — base para o ritmo e o ETA."""
    agora = time.time()
    for item in itens:
        if item.get('status') in _STATUS_FINAL:
            _CONCLUIDAS_EM.setdefault(id(item), agora)


def _estimativa(concluidas, restantes):
    """
    Tempo restante estimado, a partir do ritmo REAL observado.

    Deliberadamente conservador: usa o tempo decorrido entre a primeira e a última
    conclusão observadas, não o tempo desde que o servidor subiu — senão a espera
    ociosa antes do primeiro pedido envenenaria a média para sempre.

    Devolve None enquanto não houver base para estimar; melhor não mostrar nada do
    que mostrar um número inventado.
    """
    if restantes <= 0:
        return None
    if len(concluidas) < 3:          # amostra pequena demais para valer alguma coisa
        return None

    marcos = sorted(concluidas)
    janela = marcos[-1] - marcos[0]
    if janela <= 0:
        return None

    # (n-1) intervalos entre n conclusões
    segundos_por_aula = janela / max(1, len(marcos) - 1)
    return segundos_por_aula * restantes


def _humanizar(segundos):
    if segundos is None:
        return "—"
    segundos = int(segundos)
    if segundos < 60:
        return f"{segundos}s"
    minutos, seg = divmod(segundos, 60)
    if minutos < 60:
        return f"{minutos}min {seg:02d}s"
    horas, minutos = divmod(minutos, 60)
    return f"{horas}h {minutos:02d}min"


def _painel_resumo(itens):
    """Panorama de tudo que já foi pedido nesta sessão: quanto andou e quanto falta."""
    total = len(itens)
    if not total:
        return Panel("[dim]Aguardando pedidos da extensão...[/]",
                     title="📊 Progresso Geral", border_style="blue")

    sucesso = sum(1 for i in itens if i.get('status') == 'sucesso')
    erro = sum(1 for i in itens if i.get('status') == 'erro')
    ativos = sum(1 for i in itens if i.get('status') in _STATUS_ATIVO)
    fila = sum(1 for i in itens if i.get('status') == 'fila')

    concluidas = sucesso + erro
    restantes = total - concluidas
    percentual = int((concluidas / total) * 100) if total else 0

    eta = _estimativa(list(_CONCLUIDAS_EM.values()), restantes)

    cursos = {_partes_do_caminho(i)[0] for i in itens}
    modulos = {(_partes_do_caminho(i)) for i in itens if _partes_do_caminho(i)[1]}

    linha1 = (f"[bold green]{sucesso}[/] concluídas"
              f" · [bold red]{erro}[/] com erro"
              f" · [yellow]{ativos}[/] baixando"
              f" · [dim]{fila}[/] na fila"
              f"  →  [bold]faltam {restantes}[/] de {total}")

    linha2 = (f"[green]{_barra(percentual, 32)}[/] {percentual}%"
              f"   ⏱  restante ~[bold]{_humanizar(eta)}[/]")

    linha3 = (f"[dim]{len(cursos)} curso(s) · {len(modulos)} módulo(s)[/]")

    return Panel(f"{linha1}\n{linha2}\n{linha3}",
                 title="📊 Progresso Geral", border_style="blue")


def _tabela_cursos(itens, max_linhas=8):
    """
    Quanto já saiu de cada curso — a pergunta "em que módulo está e quanto falta".

    Só mostra cursos com trabalho pendente, mais os que acabaram de fechar, para a
    lista não virar um paredão de 22 linhas quando a comunidade inteira é enfileirada.

    `max_linhas` vem do orçamento de altura do terminal (ver _loop_visual): estourar
    a tela faz o Live duplicar o quadro em vez de sobrescrever.
    """
    if not itens or max_linhas <= 0:
        return None

    cursos = {}
    for item in itens:
        curso, modulo = _partes_do_caminho(item)
        c = cursos.setdefault(curso, {'total': 0, 'feitas': 0, 'erros': 0,
                                      'modulos': set(), 'agora': None})
        c['total'] += 1
        status = item.get('status')
        if status == 'sucesso':
            c['feitas'] += 1
        elif status == 'erro':
            c['erros'] += 1
        elif status in _STATUS_ATIVO:
            c['agora'] = modulo or '—'
        if modulo:
            c['modulos'].add(modulo)

    # Pendentes primeiro; entre eles, o que está mais perto de fechar.
    def ordem(par):
        nome, c = par
        pendente = (c['feitas'] + c['erros']) < c['total']
        return (not pendente, -(c['feitas'] / c['total'] if c['total'] else 0))

    ordenados = sorted(cursos.items(), key=ordem)
    pendentes = [p for p in ordenados if (p[1]['feitas'] + p[1]['erros']) < p[1]['total']]
    visiveis = (pendentes or ordenados)[:max_linhas]

    # Centralizado como todos os outros títulos de seção (marca, Progresso Geral,
    # Baixando agora, Histórico). Estava à esquerda por descuido e destoava.
    tabela = Table(box=box.SIMPLE, expand=True, title="[bold]📚 Cursos[/]")
    tabela.add_column("Curso", style="cyan", ratio=3, no_wrap=True)
    tabela.add_column("Módulo atual", style="dim", ratio=2, no_wrap=True)
    tabela.add_column("Progresso", style="magenta", ratio=2)
    # Largura fixa: com ratio, "23/69 +3✗" era truncado para "23/69 (3 e…".
    tabela.add_column("Aulas", justify="right", width=12, no_wrap=True)

    for nome, c in visiveis:
        feitas = c['feitas'] + c['erros']
        pct = int((feitas / c['total']) * 100) if c['total'] else 0
        # Mostra só o nome do curso (a comunidade é a mesma o tempo todo).
        rotulo = nome.split('/')[-1]
        erros = f" [red]+{c['erros']}✗[/]" if c['erros'] else ""
        tabela.add_row(
            f"[bold]{rotulo}[/]",
            c['agora'] or ("[green]✓ completo[/]" if feitas >= c['total'] else "—"),
            f"[green]{_barra(pct, 14)}[/] {pct}%",
            f"{feitas}/{c['total']}{erros}",
        )

    ocultos = len(pendentes or ordenados) - len(visiveis)
    if ocultos > 0:
        tabela.add_row(f"[dim]+ {ocultos} outro(s) curso(s)[/]", "", "", "")

    return tabela


def _gerar_tabela_ativos(itens, max_fila=5):
    """
    Cria a tabela principal com os downloads que estão a acontecer agora.
    Mostra: Nome do Arquivo | Barra de Progresso | Status (Baixando/Convertendo)

    `max_fila` limita quantas aulas em espera aparecem — com 200+ na fila, listar
    todas empurra o painel para fora da tela e o Live passa a duplicar o quadro.
    """
    # Separa quem está trabalhando de quem está na fila
    ativos = [d for d in itens if d.get('status') in _STATUS_ATIVO]
    fila = [d for d in itens if d.get('status') == 'fila']

    # Configuração da Tabela (Estilo Rich)
    # A marca saiu daqui: ela é o nome do PROGRAMA e agora encabeça a tela inteira
    # (ver _barra_marca). Aqui fica só o rótulo da seção.
    table = Table(box=box.ROUNDED, expand=True, title="[bold]⬇ Baixando agora[/]")
    table.add_column("Arquivo / Aula", style="cyan", ratio=3)
    table.add_column("Progresso", style="magenta", ratio=2)
    table.add_column("Status", style="yellow", justify="right", ratio=1)

    # Mensagem se não houver nada a acontecer
    if not ativos and not fila:
        table.add_row("[dim]Aguardando links...[/]", "", "[dim]Ocioso[/]")

    # 1. Renderiza os Downloads ATIVOS
    for item in ativos:
        # Cálculo da percentagem (proteção contra divisão por zero)
        percentual = 0
        if item.get('total', 0) > 0:
            percentual = int((item.get('progresso', 0) / item['total']) * 100)
        # Trava de segurança. O 200% que apareceu na tela nasceu de progresso não
        # zerado entre faixas — já corrigido na origem (`routes.atualizar_progresso`),
        # mas número impossível no painel corrói a confiança em tudo que ele mostra.
        percentual = max(0, min(100, percentual))

        # Só a fase. O tempo restante junto ("Baixando vídeo ⬇ · faltam 3m20s")
        # estourava a largura da coluna e virava ruído. O `eta` continua no item
        # para quem quiser uma coluna própria depois — aqui ele não entra.
        texto_status = _ROTULO_STATUS.get(item.get('status'), "Baixando ⬇")

        table.add_row(
            f"[bold]{item.get('nome', '?')}[/]",
            f"[green]{_barra(percentual)}[/] {percentual}%",
            texto_status
        )

    # 2. Renderiza a FILA — só as primeiras, senão 200+ aulas enfileiradas empurram
    # todo o resto do painel para fora da tela.
    if fila and max_fila > 0:
        table.add_section()  # Linha divisória
        for item in fila[:max_fila]:
            table.add_row(
                f"[dim]{item.get('nome', '?')}[/]",
                "[dim]Aguardando vaga...[/]",
                "⏳ Na Fila"
            )
        if len(fila) > max_fila:
            table.add_row(f"[dim]+ {len(fila) - max_fila} aula(s) na fila[/]", "", "")
    elif fila:
        table.add_section()
        table.add_row(f"[dim]{len(fila)} aula(s) na fila[/]", "", "")

    return table


# Corte do NOME no histórico, para o motivo ainda aparecer numa linha curta.
_MAX_NOME_HISTORICO = 28


def _cortar(texto, limite):
    texto = str(texto or '?')
    return texto if len(texto) <= limite else texto[:limite - 1] + '…'


def _linha_de_uma_linha_so(markup):
    """Texto que NUNCA quebra em duas linhas, seja qual for a largura do terminal.

    MEDIDO: com corte de largura fixa (nome 28 + motivo 44), num terminal de 80
    colunas o painel rendeu 8 linhas contra um orçamento de 5 — o Live então empilha
    quadros e a tela vira cascata de bordas. Corte fixo não resolve porque a largura
    é do terminal, não do texto: quem tem que decidir onde cortar é o Rich, no
    momento do render. `no_wrap` + `overflow='ellipsis'` faz exatamente isso.
    """
    # `no_wrap`/`overflow` como atributos e não como kwargs de `from_markup`: a
    # versão do Rich aqui não aceita esses kwargs no construtor da fábrica.
    texto = Text.from_markup(markup)
    texto.no_wrap = True
    texto.overflow = "ellipsis"
    return texto


def _gerar_painel_historico(itens):
    """Histórico recente, com ERRO NA FRENTE — e dizendo de quê.

    Antes mostrava só os últimos sucessos. Mas sucesso o resumo já conta (é o próprio
    comentário de `_montar_layout`: "o histórico só repete o que o resumo já diz"),
    enquanto o MOTIVO do erro não aparecia em lugar nenhum da tela.

    RELATADO no uso real (12/08/2026): "deu um erro e eu nem sei o que foi que deu
    erro, se foi um vídeo, se foi o markdown". O motivo existia — em `logs/erros.log`
    — mas quem está olhando o painel não vai abrir arquivo.

    O número de linhas é o mesmo de antes (3), então o orçamento de altura não muda.
    """
    erros = [d for d in itens if d.get('status') == 'erro']
    sucessos = [d for d in itens if d.get('status') == 'sucesso']

    if not erros and not sucessos:
        return Panel(
            "[dim]Nenhum download finalizado nesta sessão.[/]",
            title="📜 Histórico Recente",
            border_style="blue"
        )

    linhas = []
    # Erro primeiro: é a informação que some se não couber.
    for item in erros[-3:]:
        nome = _cortar(item.get('nome'), _MAX_NOME_HISTORICO)
        motivo = item.get('motivo') or 'motivo não registrado'

        # ONDE a aula fica, não só o nome dela. RELATADO em 13/08/2026: "só aparece
        # o nome da aula, e eu não saberia onde ela fica". Com 22 cursos e centenas
        # de aulas — várias homônimas entre módulos ("Enviar 20 mensagens de
        # prospecção" aparece em 6 dias diferentes) — o nome sozinho não localiza.
        curso, modulo = _partes_do_caminho(item)
        onde = f"{curso}/{modulo}" if modulo else curso
        linhas.append(f"[red]❌ {nome}[/] [dim]· {onde} — {motivo}[/]")

    for item in sucessos[-(3 - len(linhas)):] if len(linhas) < 3 else []:
        linhas.append(f"✅ {_cortar(item.get('nome'), _MAX_NOME_HISTORICO)}")

    return Panel(
        Group(*[_linha_de_uma_linha_so(l) for l in linhas[:3]]),
        title="📜 Histórico Recente",
        border_style="red" if erros else "green"
    )

NOME_PROGRAMA = "Sifão"
# A versão MAIOR sobe quando o LAYOUT DA SAÍDA muda, não quando entram features:
# quem já tem biblioteca vê a estrutura mudar, e isso é quebra de contrato.
#
# 4.2: toda aula ganha pasta própria (antes só a partir de 2 arquivos) e as pastas
# saem NUMERADAS na ordem do curso. Renumerar não custa download — o servidor acha
# a pasta com ou sem prefixo (`_pasta_existente_da_aula`).
VERSAO = "4.2"

# Cada bloco carrega UMA linha de respiro embaixo (ver _com_respiro). As alturas
# abaixo já incluem essa linha — o orçamento da tela precisa contá-la, senão o
# conteúdo volta a estourar e o Live empilha quadros.
ALTURA_MARCA = 2          # título + respiro
ALTURA_RESUMO = 6         # painel (5) + respiro
ALTURA_HISTORICO = 5
# Moldura da tabela de ativos, contada linha a linha no render real:
# título, borda de cima, cabeçalho, régua, divisória da fila, linha "+N na fila",
# borda de baixo e o respiro. Subestimar isto cortava a BORDA INFERIOR da tabela.
_MOLDURA_ATIVOS = 8
# Moldura da tabela de cursos: título + cabeçalho + régua + respiro.
_MOLDURA_CURSOS = 5


def _barra_marca(itens):
    """Faixa de identidade no topo — o nome do programa encabeça a tela.

    Antes a marca era o título da tabela de ativos, o que a jogava no MEIO do painel,
    depois do resumo e dos cursos. Nome de programa é cabeçalho, não rótulo de seção.
    """
    ativos = sum(1 for i in itens if i.get('status') in _STATUS_ATIVO)
    estado = f"[green]{ativos} baixando[/]" if ativos else "[dim]ocioso[/]"
    return Text.from_markup(
        f"[bold green]🚀 {NOME_PROGRAMA} v{VERSAO}[/]"
        f"   [dim]·[/]   [dim]baixador de aulas[/]   [dim]·[/]   {estado}",
        justify="center",
    )


def _com_respiro(renderavel):
    """Uma linha em branco embaixo do bloco.

    Sem isso os blocos ficam colados (a borda do resumo encostando no título de
    Cursos, e a tabela de Cursos encostando em 'Baixando agora') e a tela vira um
    paredão. Quem chama precisa somar essa linha na altura reservada.
    """
    return Padding(renderavel, (0, 0, 1, 0))


def _montar_layout(itens, altura_terminal):
    """
    Monta o quadro CABENDO na altura informada.

    Isto não é estética: se o conteúdo passar da altura do terminal, o `Live` do Rich
    não consegue apagar o que já rolou para fora e passa a EMPILHAR quadros — a tela
    vira uma cascata de bordas repetidas. Por isso as seções variáveis (cursos e fila)
    recebem um orçamento de linhas em vez de crescerem à vontade.
    """
    # Piso defensivo: terminal minúsculo (ou altura não detectada) não pode gerar
    # orçamento negativo e quebrar o split.
    altura = max(altura_terminal or 0, 12)

    ativos = sum(1 for i in itens if i.get('status') in _STATUS_ATIVO)

    # PRIORIDADE, do mais para o menos importante:
    #   marca > resumo > cursos > ativos > histórico
    # O histórico é o único descartável: ele só repete, em outro formato, o que o
    # resumo já diz. Antes ele era fixo e quem caía era a tabela de CURSOS — que é
    # justamente a resposta para "em que módulo estou e quanto falta". Com 4
    # downloads simultâneos num terminal de 30 linhas, tudo somado dava 31: o
    # Cursos sumia sem aviso e o painel parecia ter perdido uma seção.
    disponivel = altura - ALTURA_MARCA - ALTURA_RESUMO

    partes = [
        Layout(_com_respiro(_barra_marca(itens)), name="marca", size=ALTURA_MARCA),
        Layout(_com_respiro(_painel_resumo(itens)), name="resumo", size=ALTURA_RESUMO),
    ]

    # Ativos precisam no mínimo da moldura + as linhas em download (a fila pode ir
    # a zero sem perder informação: o resumo já diz quantas estão esperando).
    minimo_ativos = _MOLDURA_ATIVOS + max(ativos, 1)

    # Cursos: só existe com pelo menos 1 linha útil; teto de 8.
    espaco_cursos = max(0, disponivel - minimo_ativos)
    linhas_cursos = min(8, max(0, espaco_cursos - _MOLDURA_CURSOS))
    tabela_cursos = _tabela_cursos(itens, linhas_cursos)
    if tabela_cursos is not None:
        alto_cursos = len(tabela_cursos.rows) + _MOLDURA_CURSOS
        partes.append(Layout(_com_respiro(tabela_cursos), name="cursos", size=alto_cursos))
        disponivel -= alto_cursos

    # O histórico entra só se ainda sobrar espaço depois do mínimo dos ativos.
    mostrar_historico = (disponivel - minimo_ativos) >= ALTURA_HISTORICO
    if mostrar_historico:
        disponivel -= ALTURA_HISTORICO

    max_fila = max(0, disponivel - _MOLDURA_ATIVOS - ativos)
    partes.append(Layout(_com_respiro(_gerar_tabela_ativos(itens, max_fila)), name="main"))
    if mostrar_historico:
        partes.append(Layout(_gerar_painel_historico(itens), name="footer",
                             size=ALTURA_HISTORICO))

    layout = Layout()
    layout.split(*partes)
    return layout


def _loop_visual():
    """
    Função que roda em loop infinito atualizando a tela 4 vezes por segundo.

    `screen=True` usa o buffer alternativo do terminal (como o htop): o painel ocupa
    a tela inteira e é repintado no lugar, sem sujar o scrollback. `vertical_overflow`
    em 'crop' é a segunda trava — se ainda assim algo passar da altura, o Rich corta
    em vez de empilhar.
    """
    with Live(refresh_per_second=4, screen=True, vertical_overflow="crop") as live:
        while True:
            # Um único snapshot por quadro: todos os painéis enxergam o MESMO estado,
            # senão o resumo e a tabela poderiam discordar entre si.
            itens = _instantaneo()
            _registrar_conclusoes(itens)

            live.update(_montar_layout(itens, live.console.size.height))
            time.sleep(0.25)

def iniciar_dashboard():
    """
    Inicia o dashboard numa Thread separada (Daemon).
    Daemon significa que se o programa principal fechar, esta thread morre junto.
    """
    thread = threading.Thread(target=_loop_visual, daemon=True)
    thread.start()
