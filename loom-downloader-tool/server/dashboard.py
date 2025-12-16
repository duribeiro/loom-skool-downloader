import time
import threading
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich import box

# --- BASE DE DADOS EM MEMÓRIA ---
# Esta lista é partilhada entre o routes.py (que adiciona dados) 
# e este arquivo (que lê dados para desenhar na tela).
DASHBOARD_DATA = []

def _gerar_tabela_ativos():
    """
    Cria a tabela principal com os downloads que estão a acontecer agora.
    Mostra: Nome do Arquivo | Barra de Progresso | Status (Baixando/Convertendo)
    """
    # Separa quem está trabalhando de quem está na fila
    ativos = [d for d in DASHBOARD_DATA if d['status'] in ['baixando', 'convertendo']]
    fila = [d for d in DASHBOARD_DATA if d['status'] == 'fila']
    
    # Configuração da Tabela (Estilo Rich)
    table = Table(box=box.ROUNDED, expand=True, title="[bold green]🚀 LOOM HUB v2.5[/]")
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
        if item['total'] > 0: 
            percentual = int((item['progresso'] / item['total']) * 100)
        
        # Criação da barra visual (Ex: █ █ █ ░ ░)
        largura_barra = 20
        blocos_cheios = int((percentual / 100) * largura_barra)
        barra_visual = "█" * blocos_cheios + "░" * (largura_barra - blocos_cheios)
        
        # Define o ícone de status
        texto_status = "Convertendo ⚙️" if item['status'] == 'convertendo' else "Baixando ⬇"
        
        table.add_row(
            f"[bold]{item['nome']}[/]", 
            f"[green]{barra_visual}[/] {percentual}%", 
            texto_status
        )

    # 2. Renderiza a FILA (se houver alguém esperando)
    if fila:
        table.add_section() # Linha divisória
        for item in fila:
            table.add_row(
                f"[dim]{item['nome']}[/]", 
                "[dim]Aguardando vaga...[/]", 
                "⏳ Na Fila"
            )

    return table

def _gerar_painel_historico():
    """
    Cria o painel inferior com o histórico dos últimos downloads concluídos.
    """
    concluidos = [d for d in DASHBOARD_DATA if d['status'] == 'sucesso']
    
    if not concluidos:
        return Panel(
            "[dim]Nenhum download finalizado nesta sessão.[/]", 
            title="📜 Histórico Recente", 
            border_style="blue"
        )
    
    # Mostra apenas os últimos 3 para não encher a tela
    texto_historico = ""
    for item in concluidos[-3:]:
        texto_historico += f"✅ {item['nome']}\n"
    
    return Panel(
        texto_historico.strip(), 
        title="📜 Histórico Recente", 
        border_style="green"
    )

def _loop_visual():
    """
    Função que roda em loop infinito atualizando a tela 4 vezes por segundo.
    """
    with Live(refresh_per_second=4) as live:
        while True:
            # Layout dividido: Tabela em Cima, Histórico em Baixo
            layout = Layout()
            layout.split(
                Layout(_gerar_tabela_ativos(), name="main"),
                Layout(_gerar_painel_historico(), name="footer", size=5)
            )
            
            live.update(layout)
            time.sleep(0.25)

def iniciar_dashboard():
    """
    Inicia o dashboard numa Thread separada (Daemon).
    Daemon significa que se o programa principal fechar, esta thread morre junto.
    """
    thread = threading.Thread(target=_loop_visual, daemon=True)
    thread.start()