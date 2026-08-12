"""Registro de erros que SOBREVIVE ao dashboard.

Por que existe: o dashboard roda em `Live(..., screen=True)` e repinta a tela 4x/s
(`dashboard.py`). Qualquer `print` vindo de uma thread de download aparece por um
quadro e some no repaint seguinte. O efeito medido em 12/08/2026: o painel mostrava
"1 erro" e o motivo era irrecuperável — nem o dono do projeto nem o agente sabiam
se tinha falhado o vídeo, o texto ou o anexo.

O motivo agora vai para um arquivo. Arquivo não é repintado.

Escrita em modo append e uma linha por erro, de propósito: várias threads de
download escrevem ao mesmo tempo, e append de linha curta é a forma mais simples de
não embaralhar uma dentro da outra.
"""
import os
import threading
from datetime import datetime

from .caminhos import ARQUIVO_ERROS, PASTA_LOGS

# O `open(..., "a")` do CPython já é atômico o bastante para linhas curtas, mas o
# lock torna a garantia explícita em vez de dependida por acidente. Custo: zero,
# porque erro é raro.
_TRAVA = threading.Lock()


def registrar_erro(nome, pasta, motivo):
    """Anexa uma linha ao log de erros. NUNCA estoura.

    Um log que derruba o download que ele deveria estar documentando é pior que
    não ter log — por isso o `except` largo.
    """
    linha = (f"{datetime.now():%Y-%m-%d %H:%M:%S}\t"
             f"{pasta or '?'}\t{nome or '?'}\t{motivo}\n")
    try:
        with _TRAVA:
            os.makedirs(PASTA_LOGS, exist_ok=True)
            with open(ARQUIVO_ERROS, "a", encoding="utf-8") as arquivo:
                arquivo.write(linha)
    except Exception:
        pass
    return linha
