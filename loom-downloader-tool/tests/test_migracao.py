"""migrar_layout.py: script que MOVE ARQUIVO. Cada regra aqui nasceu de medição.

Os testes trabalham sempre em `tmp_path` e nunca tocam a `output/` real.
"""
import importlib
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import migrar_layout as mig


@pytest.fixture
def output_falso(tmp_path, monkeypatch):
    monkeypatch.setattr(mig, "PASTA_OUTPUT", str(tmp_path))
    return tmp_path


# --- IDEMPOTÊNCIA: PONTO FINAL NO TÍTULO ---
# O Windows remove ponto do fim de nome de PASTA mas mantém no de ARQUIVO. Uma aula
# "por Luis F." vira a pasta `por Luis F` com `por Luis F..mp4` dentro.

def test_pasta_com_ponto_final_ja_e_pasta_de_aula(tmp_path):
    """MEDIDO em 12/08/2026: sem tolerar o ponto, o script propunha criar
    `Bem-vindo/Bem-vindo./` — que o Windows normaliza para `Bem-vindo/Bem-vindo/`.
    É o aninhamento que a guarda existe para impedir."""
    aula = tmp_path / "Bem-vindo"
    aula.mkdir()
    (aula / "Bem-vindo..md").write_text("x", encoding="utf-8")

    assert mig._eh_pasta_de_aula(str(aula)) is True


def test_pasta_de_aula_normal_continua_reconhecida(tmp_path):
    aula = tmp_path / "Aula 1"
    aula.mkdir()
    (aula / "Aula 1.mp4").write_bytes(b"x")

    assert mig._eh_pasta_de_aula(str(aula)) is True


def test_modulo_com_arquivos_soltos_nao_e_pasta_de_aula(tmp_path):
    modulo = tmp_path / "Modulo"
    modulo.mkdir()
    (modulo / "Aula 1.mp4").write_bytes(b"x")
    (modulo / "Aula 2.mp4").write_bytes(b"x")

    assert mig._eh_pasta_de_aula(str(modulo)) is False


def test_nao_aninha_pasta_de_aula_com_ponto_final(output_falso, capsys):
    """A prova de ponta a ponta do bug acima: simular não pode propor nada."""
    aula = output_falso / "Modulo" / "Bem-vindo"
    aula.mkdir(parents=True)
    (aula / "Bem-vindo..md").write_text("x", encoding="utf-8")

    mig.migrar(executar=False)

    assert "Aulas que ganham pasta : 0" in capsys.readouterr().out


# --- PASTA SEMPRE: aula de UM arquivo também ganha pasta ---

def test_aula_de_um_arquivo_so_ganha_pasta(output_falso, capsys):
    """Havia aqui um `len(fs) >= 2`, cópia da regra antiga do servidor. Quando o
    servidor mudou, a simulação passou a reportar ZERO com 277 soltos em disco."""
    modulo = output_falso / "Modulo"
    modulo.mkdir()
    (modulo / "Aula sozinha.mp4").write_bytes(b"x")

    mig.migrar(executar=False)

    assert "Aulas que ganham pasta : 1" in capsys.readouterr().out


# --- RELIGAMENTO DE ANEXO ÓRFÃO ---
# O antigo `_nome_do_anexo` gravava o nome da aula TRUNCADO no prefixo, então o
# anexo não casava com nenhuma aula inteira.

def test_religa_anexo_com_prefixo_truncado(tmp_path):
    modulo = tmp_path / "Modulo"
    aula = modulo / "Skill para atualizar CRM com anotações de chamadas"
    aula.mkdir(parents=True)
    (modulo / "Skill para atualizar CRM com anotações de - notebook.zip").write_bytes(b"x")

    movidos, indecisos = mig._religar_anexos_orfaos(str(modulo), executar=True)

    assert (movidos, indecisos) == (1, 0)
    assert (aula / "notebook.zip").exists()


def test_religa_mesmo_com_pasta_numerada(tmp_path):
    # Depois da numeração, a pasta da aula é `03 - <titulo>`.
    modulo = tmp_path / "Modulo"
    aula = modulo / "03 - Automatizando Qualificação de Leads com IA"
    aula.mkdir(parents=True)
    (modulo / "Automatizando Qualificação de Leads com I - weblead.json").write_bytes(b"x")

    movidos, _ = mig._religar_anexos_orfaos(str(modulo), executar=True)

    assert movidos == 1
    assert (aula / "weblead.json").exists()


def test_anexo_ambiguo_nao_e_movido(tmp_path):
    """Com 2+ candidatos, escolher seria adivinhar. O arquivo é do usuário."""
    modulo = tmp_path / "Modulo"
    (modulo / "Skill de carrossel A").mkdir(parents=True)
    (modulo / "Skill de carrossel B").mkdir(parents=True)
    orfao = modulo / "Skill de carrossel - pack.zip"
    orfao.write_bytes(b"x")

    movidos, indecisos = mig._religar_anexos_orfaos(str(modulo), executar=True)

    assert (movidos, indecisos) == (0, 1)
    assert orfao.exists(), "moveu um arquivo ambíguo"


def test_nunca_sobrescreve_anexo_ja_no_lugar(tmp_path):
    modulo = tmp_path / "Modulo"
    aula = modulo / "Aula X completa"
    aula.mkdir(parents=True)
    (aula / "pack.zip").write_bytes(b"o bom")
    orfao = modulo / "Aula X - pack.zip"
    orfao.write_bytes(b"a copia")

    movidos, _ = mig._religar_anexos_orfaos(str(modulo), executar=True)

    assert movidos == 0
    assert (aula / "pack.zip").read_bytes() == b"o bom", "sobrescreveu o arquivo bom"
    assert orfao.exists()


def test_video_e_texto_nao_entram_no_religamento(tmp_path):
    """Só anexo usa o prefixo `<Aula> - `. Um vídeo chamado 'Aula 1 - Extra.mp4'
    é de OUTRA aula; movê-lo faria a vizinha rebaixar."""
    modulo = tmp_path / "Modulo"
    (modulo / "Aula 1 completa").mkdir(parents=True)
    video = modulo / "Aula 1 - Extra.mp4"
    video.write_bytes(b"x")

    movidos, _ = mig._religar_anexos_orfaos(str(modulo), executar=True)

    assert movidos == 0
    assert video.exists()


def test_simulacao_nao_move_nada(tmp_path):
    modulo = tmp_path / "Modulo"
    (modulo / "Aula X completa").mkdir(parents=True)
    orfao = modulo / "Aula X - pack.zip"
    orfao.write_bytes(b"x")

    movidos, _ = mig._religar_anexos_orfaos(str(modulo), executar=False)

    assert movidos == 1, "a simulação deve CONTAR o que faria"
    assert orfao.exists(), "a simulação MOVEU um arquivo"


def test_sem_prefixo_de_ordem_so_corta_digitos():
    assert mig._sem_prefixo_de_ordem("03 - Aula X") == "Aula X"
    assert mig._sem_prefixo_de_ordem("007 - Aula X") == "Aula X"
    # "Bônus" não é número: o nome inteiro é o nome da aula.
    assert mig._sem_prefixo_de_ordem("Bonus - Aula X") == "Bonus - Aula X"
    assert mig._sem_prefixo_de_ordem("Aula X") == "Aula X"


# --- PASTAS DE SERVIÇO ---
# A lista fixa já falhou: `_DIAG22` (diagnóstico manual) não estava nela, e um
# `--executar` teria reorganizado uma pasta de serviço como se fosse biblioteca.

def test_pastas_de_servico_conhecidas_sao_ignoradas():
    assert mig._eh_pasta_de_servico("_BENCH")
    assert mig._eh_pasta_de_servico("_DUPLICADOS")


def test_qualquer_pasta_com_underline_e_de_servico():
    """Prefixo é regra; lista é manutenção que alguém esquece."""
    assert mig._eh_pasta_de_servico("_DIAG22")
    assert mig._eh_pasta_de_servico("_qualquer_coisa_nova")


def test_pasta_de_comunidade_nao_e_de_servico():
    for nome in ("AI Makers Club", "BACKROOM.EXE", "YouTube", "Z4 CLIENTS @dougdemarco_"):
        assert not mig._eh_pasta_de_servico(nome), nome


def test_pasta_de_servico_nao_e_reorganizada(output_falso, capsys):
    servico = output_falso / "_DIAG22"
    servico.mkdir()
    (servico / "diag dia 22.mp4").write_bytes(b"x")

    mig.migrar(executar=False)

    assert "Aulas que ganham pasta : 0" in capsys.readouterr().out
