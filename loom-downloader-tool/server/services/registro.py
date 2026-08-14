"""Registro de erros que SOBREVIVE ao dashboard.

Por que existe: o dashboard roda em `Live(..., screen=True)` e repinta a tela 4x/s
(`dashboard.py`). Qualquer `print` vindo de uma thread de download aparece por um
quadro e some no repaint seguinte. O efeito medido em 12/08/2026: o painel mostrava
"1 erro" e o motivo era irrecuperável — nem o dono do projeto nem o agente sabiam
se tinha falhado o vídeo, o texto ou o anexo.

O motivo agora vai para um arquivo. Arquivo não é repintado.

O LOG TEM CICLO DE VIDA: ele responde "o que está quebrado AGORA", não "o que já
quebrou algum dia". Aula que erra entra; a MESMA aula, quando dá certo, sai
(`limpar_erro`). Sem isso o arquivo vira sedimento — em 14/08/2026 ele tinha 108
linhas em que várias aulas apareciam duas vezes pela mesma falha, e duas entradas
de token do Skool que ninguém sabia se ainda valiam. Um log que só cresce obriga a
conferir cada linha à mão para saber o que ainda importa, e aí ninguém confere.

Histórico é descartado de propósito (decisão do dono, 14/08/2026): ele só teria
valor se alguém fosse lê-lo, e as descobertas que importam ficam no git.

A entrada é identificada por PASTA + NOME, que é o que distingue uma aula de outra
— o mesmo nome se repete entre módulos ("Introdução" aparece em vários cursos).
"""
import os
import threading
from datetime import datetime

from .caminhos import ARQUIVO_ERROS, PASTA_LOGS

# Antes bastava o append, que o CPython já faz de forma atômica para linhas curtas.
# Com ciclo de vida virou LER-FILTRAR-ESCREVER, que não é atômico em lugar nenhum:
# dois workers terminando junto liam a mesma lista e um sobrescrevia a remoção do
# outro. Mesma lição do `_TRAVA_CAMINHO` em routes.py.
_TRAVA = threading.Lock()


def _chave(nome, pasta):
    return (pasta or '?', nome or '?')


def _linhas_sem(chave):
    """Lê o log e devolve as linhas que NÃO são da aula indicada."""
    if not os.path.exists(ARQUIVO_ERROS):
        return [], False
    with open(ARQUIVO_ERROS, encoding="utf-8") as arquivo:
        todas = arquivo.readlines()
    mantidas = []
    achou = False
    for linha in todas:
        partes = linha.rstrip("\n").split("\t")
        if len(partes) >= 3 and (partes[1], partes[2]) == chave:
            achou = True
            continue
        mantidas.append(linha)
    return mantidas, achou


def registrar_erro(nome, pasta, motivo):
    """Registra o erro daquela aula, substituindo a entrada anterior dela.

    NUNCA estoura: um log que derruba o download que ele deveria estar
    documentando é pior que não ter log — por isso o `except` largo.
    """
    linha = (f"{datetime.now():%Y-%m-%d %H:%M:%S}\t"
             f"{pasta or '?'}\t{nome or '?'}\t{motivo}\n")
    try:
        with _TRAVA:
            os.makedirs(PASTA_LOGS, exist_ok=True)
            mantidas, _ = _linhas_sem(_chave(nome, pasta))
            with open(ARQUIVO_ERROS, "w", encoding="utf-8") as arquivo:
                arquivo.writelines(mantidas)
                arquivo.write(linha)
    except Exception:
        pass
    return linha


def limpar_erro(nome, pasta):
    """Tira a aula do log — ela deu certo. NUNCA estoura.

    Devolve True se havia uma entrada para remover.

    O caso comum é NÃO haver entrada (aula que nunca falhou), e aí não se escreve
    nada: um "baixar tudo" numa biblioteca pronta chama isto centenas de vezes, e
    reescrever o arquivo a cada acerto seria custo puro.
    """
    try:
        with _TRAVA:
            mantidas, achou = _linhas_sem(_chave(nome, pasta))
            if not achou:
                return False
            with open(ARQUIVO_ERROS, "w", encoding="utf-8") as arquivo:
                arquivo.writelines(mantidas)
            return True
    except Exception:
        return False
