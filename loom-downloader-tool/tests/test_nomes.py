"""limpar_nome_arquivo: função pura, testável direto."""
import pytest

from services.utils import limpar_nome_arquivo


@pytest.mark.parametrize("entrada, esperado", [
    ("Aula 01", "Aula 01"),
    ("Aula: 01?", "Aula 01"),
    ('a<b>c:d"e/f\\g|h?i*j', "abcdefghij"),
    ("Introdução à Programação", "Introdução à Programação"),
    ("Aula &amp; Prática", "Aula & Prática"),
    ("&lt;tag&gt;", "tag"),
    ("  espaços    demais  ", "espaços demais"),
    ("Módulo 1 - Início 🚀", "Módulo 1 - Início 🚀"),
])
def test_limpa_conforme_esperado(entrada, esperado):
    assert limpar_nome_arquivo(entrada) == esperado


@pytest.mark.parametrize("vazio", ["", None])
def test_valor_vazio_vira_sem_titulo(vazio):
    assert limpar_nome_arquivo(vazio) == "sem_titulo"


@pytest.mark.parametrize("proibido", list('<>:"/\\|?*'))
def test_nenhum_caractere_proibido_no_windows_sobrevive(proibido):
    resultado = limpar_nome_arquivo(f"nome{proibido}qualquer")
    assert proibido not in resultado


def test_nao_produz_nome_com_barra_que_criaria_subpasta():
    # Um "/" que escapasse viraria diretório em vez de nome de arquivo.
    assert "/" not in limpar_nome_arquivo("Parte 1/2")
    assert "\\" not in limpar_nome_arquivo("Parte 1\\2")
