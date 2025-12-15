import logging
import os
import time
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor

# --- BIBLIOTECAS VISUAIS (RICH) ---
from rich.live import Live
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text
from rich.progress import BarColumn, Progress, TextColumn

# Silenciar Flask
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app = Flask(__name__)
CORS(app)

from loom_downloader_full_clean import (
    extrair_metadados, processar_download, converter_final, 
    limpar_pasta_temporaria_especifica, limpar_nome_arquivo, PASTA_TEMP_RAIZ
)

# --- ESTADO GLOBAL ---
DASHBOARD_DATA = []
executor = ThreadPoolExecutor(max_workers=3)

# --- FUNÇÃO QUE GERA O VISUAL ---
def gerar_tabela_downloads():
    # Separa os dados
    baixando = [d for d in DASHBOARD_DATA if d['status'] in ['baixando', 'convertendo']]
    fila = [d for d in DASHBOARD_DATA if d['status'] == 'fila']
    concluidos = [d for d in DASHBOARD_DATA if d['status'] == 'sucesso']

    # 1. Tabela Principal (Downloads Ativos)
    table = Table(box=box.ROUNDED, expand=True, title="[bold green]🚀 LOOM DOWNLOADER HUB[/]")
    table.add_column("Arquivo / Aula", style="cyan", ratio=3)
    table.add_column("Progresso", style="magenta", ratio=2)
    table.add_column("Status", style="yellow", justify="right", ratio=1)

    if not baixando and not fila:
        table.add_row("[dim]Nenhum download ativo...[/]", "", "[dim]Aguardando[/]")

    # Adiciona linhas de quem está baixando
    for item in baixando:
        percent = 0
        if item['total'] > 0:
            percent = int((item['progresso'] / item['total']) * 100)
        
        # Cria uma barra de progresso visual usando caracteres de bloco
        largura = 20
        cheio = int((percent / 100) * largura)
        barra_str = "█" * cheio + "░" * (largura - cheio)
        
        status_txt = "Convertendo ⚙️" if item['status'] == 'convertendo' else "Baixando ⬇"
        
        table.add_row(
            f"[bold]{item['nome']}[/]",
            f"[green]{barra_str}[/] {percent}%",
            status_txt
        )

    # Adiciona separador se tiver fila
    if fila:
        table.add_section()
        for item in fila:
            table.add_row(
                f"[dim]{item['nome']}[/]",
                "[dim]Aguardando vaga...[/]",
                "⏳ Na Fila"
            )

    return table

def gerar_painel_concluidos():
    concluidos = [d for d in DASHBOARD_DATA if d['status'] == 'sucesso']
    if not concluidos:
        return Panel("[dim]Nenhum download finalizado ainda.[/]", title="Histórico Recente", border_style="blue")
    
    texto_hist = ""
    # Pega os últimos 3
    for item in concluidos[-3:]:
        texto_hist += f"✅ {item['nome']}\n"
    
    return Panel(texto_hist.strip(), title="Histórico Recente", border_style="green")

def desenhar_painel_rich():
    # O objeto 'Live' cuida de atualizar a tela sem piscar
    with Live(refresh_per_second=4) as live:
        while True:
            # Cria o layout
            layout = Layout()
            layout.split(
                Layout(gerar_tabela_downloads(), name="main"),
                Layout(gerar_painel_concluidos(), name="footer", size=5)
            )
            
            # Atualiza a tela
            live.update(layout)
            time.sleep(0.25)

# Inicia o visualizador em thread separada
thread_visual = threading.Thread(target=desenhar_painel_rich, daemon=True)
thread_visual.start()

# --- WORKER E ROTAS (Igual ao anterior) ---
def worker(url, pasta, nome_arq, item_data):
    item_data['status'] = 'baixando'
    if not nome_arq:
        t, _ = extrair_metadados(url)
        nome_arq = t
    
    nome_limpo = limpar_nome_arquivo(nome_arq)
    item_data['nome'] = nome_limpo
    pasta_curso = pasta if pasta else "Downloads Loom"
    pasta_temp = os.path.join(PASTA_TEMP_RAIZ, nome_limpo)
    
    def atualizar_progresso(total=None):
        if total: item_data['total'] = total
        else: item_data['progresso'] += 1
    
    _, m3u8 = extrair_metadados(url)
    sucesso = False
    if m3u8:
        if processar_download(m3u8, nome_limpo, pasta_temp, atualizar_progresso):
            item_data['status'] = 'convertendo'
            if converter_final(nome_limpo, pasta_curso, pasta_temp):
                limpar_pasta_temporaria_especifica(pasta_temp)
                sucesso = True
    
    if sucesso:
        item_data['status'] = 'sucesso'
        item_data['progresso'] = item_data['total']
    else:
        item_data['status'] = 'erro'

@app.route('/baixar', methods=['POST'])
def baixar():
    d = request.json
    nome_inicial = d.get('filename', 'Verificando...')
    
    novo_item = {
        'nome': nome_inicial,
        'status': 'fila',
        'progresso': 0,
        'total': 1,
        'url': d.get('url'),
        'folder': d.get('folder')
    }
    DASHBOARD_DATA.append(novo_item)
    executor.submit(worker, novo_item['url'], novo_item['folder'], novo_item['nome'], novo_item)
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(port=5000)