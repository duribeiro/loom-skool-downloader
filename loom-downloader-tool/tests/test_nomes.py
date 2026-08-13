"""limpar_nome_arquivo: função pura, testável direto."""
import pytest

from services.utils import limpar_nome_arquivo, cortar_preservando_extensao, LIMITE_NOME


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


# --- TETO DE COMPRIMENTO (MAX_PATH do Windows) ---
# Com pasta por aula, o nome entra DUAS vezes no caminho (`Aula X/Aula X.mp4`),
# então título longo custa o dobro. Ver LIMITE_NOME em services/utils.py.

def test_nome_longo_e_cortado_no_limite():
    nome = "A" * 300
    assert len(limpar_nome_arquivo(nome)) == LIMITE_NOME


def test_nome_dentro_do_limite_nao_e_tocado():
    # O corte não pode encostar em nome bom: renomear em massa faria o servidor
    # não achar o que já baixou e rebaixar tudo.
    nome = "B" * LIMITE_NOME
    assert limpar_nome_arquivo(nome) == nome


def test_corte_e_deterministico():
    # É o que sustenta o "já baixei?": o mesmo título tem que virar sempre o
    # mesmo nome, senão cada execução procura o arquivo num nome diferente.
    nome = "C" * 250
    assert limpar_nome_arquivo(nome) == limpar_nome_arquivo(nome)


def test_corte_nao_deixa_espaco_na_ponta():
    # Windows descarta espaço no fim do nome; deixá-lo faria o nome gravado
    # diferir do nome procurado, e o arquivo seria rebaixado toda vez.
    nome = "D" * (LIMITE_NOME - 1) + " palavra"
    assert not limpar_nome_arquivo(nome).endswith(" ")


# --- ANEXO: o corte não pode comer a extensão ---
# REGRESSÃO PEGA NA REVISÃO (12/08/2026): remover `_nome_do_anexo` (que usava
# splitext) e, no mesmo patch, pôr um corte cego de LIMITE_NOME em
# `limpar_nome_arquivo` fazia um anexo de 90 chars perder o `.pdf`. Sem extensão o
# Windows não abre o arquivo — e em curso como a Biblioteca de Templates o anexo
# É o produto.

def test_anexo_longo_mantem_a_extensao():
    nome = "C" * 100 + ".pdf"
    saida = cortar_preservando_extensao(nome)
    assert saida.endswith(".pdf"), "sem extensão o Windows não abre o arquivo"
    assert len(saida) <= LIMITE_NOME


def test_anexo_curto_passa_intacto():
    assert cortar_preservando_extensao("relatorio.xlsx") == "relatorio.xlsx"


def test_ponto_no_meio_do_nome_nao_e_extensao():
    # `splitext` corta no ÚLTIMO ponto: 'Aula 1.5 - Introducao' virava
    # base='Aula 1' + ext='.5 - Introducao' e o nome saía mutilado.
    assert cortar_preservando_extensao("Aula 1.5 - Introducao") == "Aula 1.5 - Introducao"
    assert cortar_preservando_extensao("Fluxo v2.3 backup") == "Fluxo v2.3 backup"


def test_extensao_composta_sobrevive():
    assert cortar_preservando_extensao("arquivo.tar.gz") == "arquivo.tar.gz"


def test_nome_vazio_vira_anexo():
    assert cortar_preservando_extensao("") == "anexo"
    assert cortar_preservando_extensao(None) == "anexo"


# --- PONTO/ESPAÇO NO FIM: três camadas normalizando diferente ---
# MEDIDO em 13/08/2026 com a aula "#12 ... por Luis F." (ponto no fim):
#   nosso nome -> '...F.'   |  Windows cria -> '...F'  |  yt-dlp -> '...F#'
# O yt-dlp baixou 161 MB em `F#/`, o código procurou em `F./` e o temporário ficou
# órfão. Duas aulas, 349,8 MB parados em disco.

def test_ponto_no_fim_e_removido():
    assert limpar_nome_arquivo("por Luis F.") == "por Luis F"
    assert limpar_nome_arquivo("Bem-vindo.") == "Bem-vindo"


def test_espaco_no_fim_e_removido():
    assert limpar_nome_arquivo("Aula   ") == "Aula"


def test_ponto_no_meio_sobrevive():
    # Só o do FIM é problema; ponto no meio é parte do título.
    assert limpar_nome_arquivo("Aula 1.5 - Intro") == "Aula 1.5 - Intro"


def test_nome_so_de_pontos_nao_vira_vazio():
    assert limpar_nome_arquivo("...") == "sem_titulo"


def test_nosso_nome_sobrevive_ao_sanitize_do_ytdlp():
    """A propriedade que importa: o yt-dlp não pode MUDAR o nome que escolhemos.

    Se ele mudar, baixa numa pasta e o servidor procura noutra — exatamente o que
    deixou 349,8 MB órfãos.
    """
    from yt_dlp.utils import sanitize_path

    for bruto in ("por Luis F.", "Erick C.", "Bem-vindo.", "Aula   ",
                  "Aula normal", "Aula 1.5 - Intro"):
        nosso = limpar_nome_arquivo(bruto)
        assert sanitize_path(nosso) == nosso, \
            f"yt-dlp reescreveria {nosso!r} como {sanitize_path(nosso)!r}"


# --- ORÇAMENTO DO CAMINHO INTEIRO ---
# `LIMITE_NOME` é teto por COMPONENTE; o limite do Windows é do caminho inteiro.
# MEDIDO em 13/08/2026: com a output/ dentro do projeto (82 chars só de prefixo), o
# pior caso deu 277 mesmo com o nome já em 80 — e aí o Get-ChildItem do PowerShell
# reporta a pasta como VAZIA, escondendo 1,1 GB de vídeo.

import os as _os
from services.utils import limite_do_nome, MAX_CAMINHO, PISO_NOME


def _caminho_final(pai, nome, prefixo="03 - ", ext=".mp4"):
    """O caminho que o servidor realmente monta: o nome entra DUAS vezes."""
    return _os.path.join(pai, prefixo + nome, nome + ext)


def test_caminho_final_cabe_seja_qual_for_a_pasta_pai():
    nome = "A" * 200
    for pai in (r"C:\Users\Eduardo Ribeiro\Videos\Sifao\YouTube\Hashtag Treinamentos",
                r"E:\CURSOS\Programação\Projetos\loom-downloader\hsl-lab\loom-downloader-tool\output\X",
                r"C:\a\b\c\d\e\f\g\h\i\j\k\l\m\n\o\p\q\r\s\t\u\v\w\x\y\z\Comunidade\Curso\Modulo"):
        limite = limite_do_nome(pai, extensao=".mp4", prefixo="03 - ")
        curto = limpar_nome_arquivo(nome, limite=limite)
        assert len(_caminho_final(pai, curto)) <= 260, \
            f"estourou com pai de {len(pai)} chars"


def test_pasta_rasa_nao_encurta_nada():
    # Com a biblioteca num lugar normal, o orçamento não deve agir: teto continua 80.
    pai = r"C:\Users\Eduardo Ribeiro\Videos\Sifao\Comunidade\Curso\01 - Modulo"
    assert limite_do_nome(pai) == LIMITE_NOME


def test_pasta_funda_encurta_o_nome():
    pai = "C:\\" + "\\".join(["pasta_bem_comprida"] * 8)
    assert limite_do_nome(pai) < LIMITE_NOME


def test_nunca_devolve_menos_que_o_piso():
    """Abaixo do piso o nome deixa de identificar a aula; aí o problema é a pasta
    de destino, e o servidor avisa em vez de picotar mais."""
    pai = "C:\\" + "\\".join(["x" * 40] * 8)
    assert limite_do_nome(pai) == PISO_NOME


def test_limite_e_deterministico():
    # Mesmo pai -> mesmo limite -> mesmo nome, senão o "já baixei?" quebra.
    pai = r"C:\Users\X\Videos\Sifao\Com\Curso\Modulo"
    assert limite_do_nome(pai) == limite_do_nome(pai)


def test_extensao_e_prefixo_entram_na_conta():
    pai = r"C:\Users\X\Videos\Sifao\Com\Curso\Modulo"
    assert limite_do_nome(pai, prefixo="003 - ") <= limite_do_nome(pai, prefixo="")
