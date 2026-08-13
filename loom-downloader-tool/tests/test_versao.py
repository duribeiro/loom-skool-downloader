"""A versão tem que ser a MESMA no servidor e na extensão.

PEGO NA AUDITORIA em 13/08/2026: o `dashboard.py` dizia 4.2 e o
`extension/manifest.json` dizia 4.1. Não é detalhe: a versão MAIOR deste projeto
sobe quando o LAYOUT DA SAÍDA muda, e quem tem biblioteca precisa saber que a
estrutura mudou. Duas versões diferentes é a quebra de contrato ficando invisível
justamente do lado que o usuário instala.

A doc afirmava "a extensão carrega a mesma versão" — afirmação que ninguém
verificava. Agora verifica.
"""
import json
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _versao_do_servidor():
    caminho = os.path.join(RAIZ, "server", "dashboard.py")
    with open(caminho, encoding="utf-8") as arquivo:
        achado = re.search(r'^VERSAO\s*=\s*["\']([^"\']+)', arquivo.read(), re.M)
    assert achado, "não achei VERSAO em server/dashboard.py"
    return achado.group(1)


def _versao_da_extensao():
    caminho = os.path.join(RAIZ, "extension", "manifest.json")
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)["version"]


def test_servidor_e_extensao_na_mesma_versao():
    servidor, extensao = _versao_do_servidor(), _versao_da_extensao()
    assert servidor == extensao, (
        f"servidor={servidor} e extensão={extensao} — a versão maior sobe quando o "
        f"layout da saída muda; divergir esconde a quebra de contrato do usuário")


def test_versao_tem_formato_de_versao():
    assert re.fullmatch(r"\d+\.\d+(\.\d+)?", _versao_do_servidor())
