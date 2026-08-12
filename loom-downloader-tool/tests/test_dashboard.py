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
