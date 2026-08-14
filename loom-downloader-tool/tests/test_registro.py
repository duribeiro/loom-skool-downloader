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


# --- CICLO DE VIDA -----------------------------------------------------------
# O log responde "o que está quebrado AGORA". Sem isso ele vira sedimento: em
# 14/08/2026 tinha 108 linhas com aulas repetidas e duas entradas de token do
# Skool que ninguém sabia se ainda valiam.

def test_a_mesma_aula_nao_duplica(log_isolado):
    """Reenfileirar um curso não pode multiplicar a mesma falha."""
    registro.registrar_erro("Aula 1", "Com/Curso", "primeiro motivo")
    registro.registrar_erro("Aula 1", "Com/Curso", "segundo motivo")

    linhas = log_isolado.read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) == 1, f"a mesma aula virou {len(linhas)} linhas"
    assert "segundo motivo" in linhas[0], "tem que valer o motivo mais recente"


def test_sucesso_tira_a_aula_do_log(log_isolado):
    registro.registrar_erro("Aula 1", "Com/Curso", "master.m3u8 não baixou")
    assert registro.limpar_erro("Aula 1", "Com/Curso") is True

    assert log_isolado.read_text(encoding="utf-8").strip() == "", \
        "a aula deu certo e continuou no log de erros"


def test_sucesso_de_uma_nao_apaga_a_outra(log_isolado):
    registro.registrar_erro("Aula 1", "Com/Curso", "motivo 1")
    registro.registrar_erro("Aula 2", "Com/Curso", "motivo 2")
    registro.limpar_erro("Aula 1", "Com/Curso")

    conteudo = log_isolado.read_text(encoding="utf-8")
    assert "Aula 1" not in conteudo
    assert "motivo 2" in conteudo, "limpar uma aula levou a outra junto"


def test_aulas_homonimas_em_pastas_diferentes_sao_distintas(log_isolado):
    """O mesmo nome se repete entre módulos — a chave é PASTA + NOME."""
    registro.registrar_erro("Introdução", "Com/Curso A", "motivo A")
    registro.registrar_erro("Introdução", "Com/Curso B", "motivo B")
    registro.limpar_erro("Introdução", "Com/Curso A")

    conteudo = log_isolado.read_text(encoding="utf-8")
    assert "motivo A" not in conteudo
    assert "motivo B" in conteudo, "apagou a homônima do outro módulo"


def test_limpar_o_que_nao_esta_la_nao_escreve(log_isolado):
    """Caso comum: 'baixar tudo' numa biblioteca pronta chama isto centenas de
    vezes sem nenhum erro registrado. Não pode custar uma reescrita cada vez."""
    assert registro.limpar_erro("Nunca falhou", "Com/Curso") is False
    assert not log_isolado.exists(), "criou o arquivo à toa"
