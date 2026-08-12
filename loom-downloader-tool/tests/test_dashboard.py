"""Painel: rótulo de fase, tempo restante e a trava do percentual.

Todos os casos aqui nasceram de defeito VISTO NA TELA, não de imaginação:
barra passando de 100%, barra congelada sem dizer o que estava acontecendo, e
rótulo comprido demais para a coluna.
"""
import dashboard as db


# --- ROTULO DE FASE ----------------------------------------------------------
# O yt-dlp baixa vídeo e áudio como downloads SEPARADOS. Dizer só "Baixando"
# fazia a barra parecer congelada em 100% durante todo o áudio.

def test_cada_fase_tem_rotulo_proprio():
    assert db._ROTULO_STATUS['baixando video'] != db._ROTULO_STATUS['baixando audio']
    assert 'vídeo' in db._ROTULO_STATUS['baixando video']
    assert 'áudio' in db._ROTULO_STATUS['baixando audio']
    assert 'Convertendo' in db._ROTULO_STATUS['convertendo']


def test_status_desconhecido_nao_quebra_o_painel():
    """Fase nova no yt-dlp não pode derrubar a tela — cai no rótulo genérico."""
    assert db._ROTULO_STATUS.get('fase que ainda nao existe', 'Baixando ⬇') == 'Baixando ⬇'


def test_fases_de_download_contam_como_ativas():
    """Fora de _STATUS_ATIVO, o resumo zeraria os 'ativos' durante o download."""
    for fase in ('baixando', 'baixando video', 'baixando audio', 'convertendo'):
        assert fase in db._STATUS_ATIVO, f"'{fase}' ficaria fora da contagem de ativos"
    for final in ('fila', 'sucesso', 'erro'):
        assert final not in db._STATUS_ATIVO


# --- TEMPO RESTANTE ----------------------------------------------------------

def test_eta_sem_valor_nao_inventa_numero():
    """Sem estimativa (ex.: conversão) o campo some. Melhor calar que chutar."""
    for vazio in (None, '', 'lixo', -1, [], {}):
        assert db._formatar_eta(vazio) == ''


def test_eta_formata_por_ordem_de_grandeza():
    assert '45s' in db._formatar_eta(45)
    assert '3m20s' in db._formatar_eta(200)
    assert '1h04m' in db._formatar_eta(3860)


# --- TRAVA DO PERCENTUAL -----------------------------------------------------
# REGRESSÃO VISTA NA TELA: o painel chegou a mostrar 140% e 200%, com a barra
# verde cheia. Nasceu de progresso não zerado entre faixas — já corrigido na
# origem, mas número impossível no painel corrói a confiança em tudo que ele
# mostra, então a trava fica como segunda camada.

def _percentual(progresso, total):
    """Réplica do cálculo do painel, incluindo a trava."""
    pct = int((progresso / total) * 100) if total > 0 else 0
    return max(0, min(100, pct))


def test_percentual_nunca_passa_de_100_nem_fica_negativo():
    assert _percentual(200, 100) == 100, "o 200% que apareceu na tela"
    assert _percentual(140, 100) == 100
    assert _percentual(-5, 100) == 0
    assert _percentual(50, 100) == 50
    assert _percentual(0, 0) == 0, "total zero não pode dividir por zero"


def test_barra_desenha_dentro_do_limite():
    """A barra é texto de largura fixa: percentual acima de 100 estouraria a coluna."""
    largura = len(db._barra(0))
    for pct in (0, 1, 50, 99, 100):
        assert len(db._barra(pct)) == largura, f"largura mudou em {pct}%"
    assert db._barra(0) != db._barra(100)


# --- FAIXAS DA BARRA ---------------------------------------------------------
# Cada etapa ocupa um trecho da barra, em vez dos 100% inteiros. Assim 100% passa
# a significar PRONTO — antes a barra enchia no fim do vídeo e ficava parada
# durante áudio e conversão, dando impressão de travamento.

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
from services.ytdlp import FAIXA_DA_FASE
from routes import FAIXA_CONVERSAO


def _pct(fase, fracao):
    ini, fim = FAIXA_DA_FASE[fase]
    return ini + fracao * (fim - ini)


def test_faixas_cobrem_a_barra_em_ordem_e_sem_buraco():
    assert FAIXA_DA_FASE['baixando video'][1] == FAIXA_DA_FASE['baixando audio'][0]
    assert FAIXA_DA_FASE['baixando audio'][1] == FAIXA_CONVERSAO[0]
    for ini, fim in list(FAIXA_DA_FASE.values()) + [FAIXA_CONVERSAO]:
        assert 0 <= ini < fim <= 100


def test_download_nunca_chega_a_100():
    """100% tem que significar PRONTO. Download cheio ainda tem conversão pela frente."""
    for fase in FAIXA_DA_FASE:
        assert _pct(fase, 1.0) < 100, f"'{fase}' cheia marcaria 100% antes da hora"
    assert FAIXA_CONVERSAO[1] < 100, "nem a conversão fecha em 100 sozinha"


def test_barra_so_anda_para_frente_ao_trocar_de_etapa():
    """Vídeo cheio nunca pode marcar mais que áudio começando."""
    assert _pct('baixando video', 1.0) <= _pct('baixando audio', 0.0)
    assert _pct('baixando audio', 1.0) <= FAIXA_CONVERSAO[0]


# --- HISTÓRICO: erro na frente, e com motivo ---

def _render(painel, largura):
    from rich.console import Console
    console = Console(width=largura, record=True)
    console.print(painel)
    return console.export_text()


def test_historico_mostra_o_motivo_do_erro():
    """RELATADO: 'deu um erro e eu nem sei o que foi'.

    O motivo ia só para `logs/erros.log`, e quem olha o painel não abre arquivo.
    """
    itens = [{'nome': 'Aula X', 'status': 'erro',
              'motivo': 'nao achei o .m3u8', 'folder': 'C/M'}]
    saida = _render(db._gerar_painel_historico(itens), 100)
    assert 'Aula X' in saida
    assert 'nao achei o .m3u8' in saida, "o painel diz 'erro' e não diz de quê"


def test_erro_tem_prioridade_sobre_sucesso_no_historico():
    # Sucesso o resumo já conta; o motivo do erro não aparece em nenhum outro lugar.
    itens = ([{'nome': f'ok {i}', 'status': 'sucesso', 'folder': 'C/M'} for i in range(5)]
             + [{'nome': 'quebrada', 'status': 'erro', 'motivo': 'FFmpeg falhou',
                 'folder': 'C/M'}])
    saida = _render(db._gerar_painel_historico(itens), 100)
    assert 'quebrada' in saida and 'FFmpeg falhou' in saida


def test_historico_nunca_estoura_a_altura_orcada():
    """A linha não pode quebrar em duas, em NENHUMA largura de terminal.

    MEDIDO: com corte de largura fixa, num terminal de 80 colunas o painel rendeu
    8 linhas contra o orçamento de 5 — e o `Live` então empilha quadros, virando a
    cascata de bordas que já apareceu na tela. Quem decide onde cortar tem que ser
    o Rich no render (`no_wrap` + `overflow`), não uma constante nossa.
    """
    itens = [{'nome': 'N' * 80, 'status': 'erro', 'motivo': 'M' * 200, 'folder': 'C/M'}
             for _ in range(3)]
    painel = db._gerar_painel_historico(itens)
    for largura in (40, 60, 80, 100, 200):
        linhas = _render(painel, largura).strip().splitlines()
        assert len(linhas) <= db.ALTURA_HISTORICO, \
            f"estourou em {largura} colunas: {len(linhas)} linhas"


def test_historico_vazio_nao_quebra():
    saida = _render(db._gerar_painel_historico([]), 100)
    assert 'Nenhum download finalizado' in saida
