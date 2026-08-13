"""registrar_erro: o motivo do erro tem que SOBREVIVER ao dashboard.

O painel roda em `Live(screen=True)` e repinta 4x/s, então `print` de thread de
download some em ~250ms. MEDIDO em 12/08/2026: o painel mostrou "1 erro" e o motivo
era irrecuperável. Arquivo não é repintado — por isso estes testes.
"""
import importlib

import pytest

from services import registro


@pytest.fixture
def log_isolado(tmp_path, monkeypatch):
    """Aponta o log para uma pasta temporária, nunca para a do projeto."""
    destino = tmp_path / "logs" / "erros.log"
    monkeypatch.setattr(registro, "PASTA_LOGS", str(destino.parent))
    monkeypatch.setattr(registro, "ARQUIVO_ERROS", str(destino))
    return destino


def test_grava_o_motivo_em_disco(log_isolado):
    registro.registrar_erro("Aula 1", "Com/Curso/Modulo", "FFmpeg não converteu")

    assert log_isolado.exists(), "sem arquivo, o motivo morre com o repaint da tela"
    conteudo = log_isolado.read_text(encoding="utf-8")
    assert "Aula 1" in conteudo
    assert "Com/Curso/Modulo" in conteudo
    assert "FFmpeg não converteu" in conteudo


def test_cria_a_pasta_de_logs_se_nao_existir(log_isolado):
    # Numa instalação nova a pasta não existe; falhar aqui seria perder justamente
    # o primeiro erro, que é o mais informativo.
    assert not log_isolado.parent.exists()
    registro.registrar_erro("Aula", "Pasta", "motivo")
    assert log_isolado.exists()


def test_um_erro_por_linha(log_isolado):
    # Várias threads de download escrevem ao mesmo tempo. Uma linha por erro é o
    # que impede uma mensagem de aparecer no meio da outra.
    for i in range(5):
        registro.registrar_erro(f"Aula {i}", "Pasta", f"motivo {i}")

    linhas = log_isolado.read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) == 5
    assert all("motivo" in linha for linha in linhas)


def test_anexa_em_vez_de_sobrescrever(log_isolado):
    # Erro novo não pode apagar o histórico: numa fila longa, o primeiro erro
    # costuma explicar os seguintes.
    registro.registrar_erro("Primeira", "Pasta", "motivo antigo")
    registro.registrar_erro("Segunda", "Pasta", "motivo novo")

    conteudo = log_isolado.read_text(encoding="utf-8")
    assert "motivo antigo" in conteudo and "motivo novo" in conteudo


def test_nunca_estoura_mesmo_com_caminho_invalido(monkeypatch):
    """Um log que derruba o download que ele documenta é pior que não ter log."""
    monkeypatch.setattr(registro, "PASTA_LOGS", "\x00caminho invalido")
    monkeypatch.setattr(registro, "ARQUIVO_ERROS", "\x00caminho invalido/erros.log")

    registro.registrar_erro("Aula", "Pasta", "motivo")   # não pode levantar
