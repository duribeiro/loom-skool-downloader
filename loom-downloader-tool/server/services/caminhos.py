"""Caminhos do projeto, num lugar só.

Antes, o cálculo de PASTA_OUTPUT estava duplicado em downloader.py e
converter.py — "mexeu num, mexa no outro". Agora mora aqui e os dois importam.

Fica num módulo separado (e não no __init__.py) de propósito: o __init__
importa de .downloader e .converter, que por sua vez importam daqui. Se estas
constantes estivessem no __init__, daria import circular.
"""
import os

# .../server/services/caminhos.py -> sobe até .../loom-downloader-tool
_DIR_SERVICES = os.path.dirname(os.path.abspath(__file__))
_DIR_SERVER = os.path.dirname(_DIR_SERVICES)
_DIR_RAIZ = os.path.dirname(_DIR_SERVER)

# Absoluto: onde os .mp4 finais são organizados.
PASTA_OUTPUT = os.path.join(_DIR_RAIZ, "output")

# Relativo ao diretório de trabalho: onde ficam os .ts temporários.
# É relativo de propósito — o servidor deve rodar de loom-downloader-tool/.
PASTA_TEMP_RAIZ = "hls-temp"

# Absoluto, como PASTA_OUTPUT: o log não pode depender de onde o servidor foi
# iniciado, senão some quando mais se precisa dele.
PASTA_LOGS = os.path.join(_DIR_RAIZ, "logs")
ARQUIVO_ERROS = os.path.join(PASTA_LOGS, "erros.log")
