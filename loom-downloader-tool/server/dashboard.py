import time
import threading
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich import box

# Dados Globais
DASHBOARD_DATA = []

def _gerar_tabela_ativos():
    # Filtra downloads ativos e fila
    ativos = [d for d in DASHBOARD_DATA if d['status'] in ['baixando', 'convertendo']]
    fila = [d for d in DASHBOARD_DATA if d['status'] == 'fila']
    
    # Cria tabela principal
    table = Table(box=box.ROUNDED, expand=True, title="[bold green]🚀 LOOM HUB v2.5[/]")
    table.add_column("Arquivo / Aula", style="cyan", ratio=3)
    table.add_column("Progresso", style="magenta", ratio=2)
    table.add_column("Status", style="yellow", justify="right", ratio=1)

    if not ativos and not fila:
        table.add_row("[dim]Aguardando links...[/]", "", "[dim]Ocioso[/]")

    # Linhas de Ativos
    for item in ativos:
        pct = 0
        if item['total'] > 0: pct = int((item['progresso'] / item['total']) * 100)
        
        largura = 20
        cheio = int((pct / 100) * largura)
        barra = "█" * cheio + "░" * (largura - cheio)
        
        sts = "Convertendo ⚙️" if item['status'] == 'convertendo' else "Baixando ⬇"
        table.add_row(f"[bold]{item['nome']}[/]", f"[green]{barra}[/] {pct}%", sts)

    # Seção da Fila
    if fila:
        table.add_section()
        for item in fila:
            table.add_row(f"[dim]{item['nome']}[/]", "[dim]Aguardando vaga...[/]", "⏳ Na Fila")

    return table

def _gerar_painel_historico():
    # Filtra os concluídos
    concluidos = [d for d in DASHBOARD_DATA if d['status'] == 'sucesso']
    
    if not concluidos:
        return Panel("[dim]Nenhum download finalizado nesta sessão.[/]", title="📜 Histórico Recente", border_style="blue")
    
    # Pega os últimos 3 para não lotar a tela
    texto_hist = ""
    for item in concluidos[-3:]:
        texto_hist += f"✅ {item['nome']}\n"
    
    return Panel(texto_hist.strip(), title="📜 Histórico Recente", border_style="green")

def _loop_visual():
    with Live(refresh_per_second=4) as live:
        while True:
            # Cria o layout dividido: Principal em cima, Histórico em baixo
            layout = Layout()
            layout.split(
                Layout(_gerar_tabela_ativos(), name="main"),
                Layout(_gerar_painel_historico(), name="footer", size=5) # Tamanho fixo para o rodapé
            )
            
            live.update(layout)
            time.sleep(0.25)

def iniciar_dashboard():
    t = threading.Thread(target=_loop_visual, daemon=True)
    t.start()