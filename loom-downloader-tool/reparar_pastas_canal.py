"""Remove as pastas de CANAL do YouTube que se infiltraram na árvore de cursos.

Até a v4.0 o servidor criava uma subpasta com o nome do canal do YouTube para
QUALQUER vídeo de lá — inclusive aula do Skool cujo `videoLink` aponta pro YouTube.
Isso inseriu um nível que não existe no Skool (ex.: `Chatwoot/Gabriel Morais/`), e
tirou aulas da sequência do módulo. O bug já está corrigido; isto conserta o passado.

NÃO adivinha: compara com a estrutura REAL do Skool, medida na API da comunidade.
Uma pasta é legítima se for um MÓDULO do curso ou uma PASTA DE AULA (aquela que
contém um arquivo com o mesmo nome dela). O resto é intruso e tem o conteúdo
promovido um nível acima.

SIMULA por padrão. Só mexe com `--executar`.
"""
import os
import re
import sys

PASTA_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# Medido em 2026-08-11 na API do Skool (pageProps.course, unitType == 'set').
# Curso -> módulos reais. Lista vazia = curso sem módulos: QUALQUER subpasta que
# não seja pasta de aula ali é intrusa.
ESTRUTURA = {
    "AI Makers Club": {
        "Comece por aqui": [],
        "Biblioteca de Templates": ["Claude", "Make.com", "N8N"],
        "Agentes IA de WhatsApp": ["API Oficial", "Chatwoot", "Implementando seu Agente"],
        "Bootcamp: Pré-programa": [],
        "Office Hours com Well Pires": [],
        "Bootcamp: Mês 1": [f"Dia {n}:" for n in range(1, 31)],
        "N8N Pro": ["Bônus: Lovable", "Fundamentos"],
        "Founders Talk": [],
        "Claude Code": [],
        "Agência de IA do ZERO": ["Tudo sobre o modelo de negócios"],
        "Supabase": [],
    },
}

# A extensão limpa o nome antes de virar pasta; comparamos igual.
_PROIBIDOS = re.compile(r'[<>:"/\\|?*]')


def limpar(nome):
    return " ".join(_PROIBIDOS.sub("", nome).split())


def eh_pasta_de_aula(caminho):
    """Pasta de aula contém um arquivo com o mesmo nome dela (Aula X/Aula X.mp4)."""
    nome = os.path.basename(caminho)
    try:
        itens = os.listdir(caminho)
    except OSError:
        return False
    return any(os.path.splitext(f)[0] == nome
               for f in itens if os.path.isfile(os.path.join(caminho, f)))


PASTA_QUARENTENA = "_DUPLICADOS"


def _inventario(caminho):
    """{caminho relativo: tamanho} de tudo abaixo de `caminho`."""
    itens = {}
    for raiz, _, arquivos in os.walk(caminho):
        for a in arquivos:
            completo = os.path.join(raiz, a)
            itens[os.path.relpath(completo, caminho)] = os.path.getsize(completo)
    return itens


def _eh_duplicata_segura(origem, destino):
    """True se o destino já contém tudo o que a origem tem (nome + tamanho).

    Conservador de propósito: só considera seguro quando NADA da origem falta no
    destino. Se a origem tiver um arquivo exclusivo, ela não é descartável.
    """
    if not os.path.isdir(origem) or not os.path.isdir(destino):
        return False
    io_, id_ = _inventario(origem), _inventario(destino)
    return all(id_.get(k) == v for k, v in io_.items())


def promover(pasta_intrusa, executar):
    """Move tudo que está dentro da pasta intrusa para o nível de cima."""
    pai = os.path.dirname(pasta_intrusa)
    movidos = conflitos = 0

    for nome in sorted(os.listdir(pasta_intrusa)):
        origem = os.path.join(pasta_intrusa, nome)
        destino = os.path.join(pai, nome)
        if os.path.exists(destino):
            # Colisão: o mesmo conteúdo já existe fora (efeito de reorganização
            # manual). Se o destino contém tudo o que está aqui, isto é duplicata
            # pura — vai para QUARENTENA, não para a lixeira: em disco externo o
            # delete não é reversível, e conferir depois é barato.
            if _eh_duplicata_segura(origem, destino):
                rel = os.path.relpath(origem, PASTA_OUTPUT)
                quarentena = os.path.join(PASTA_OUTPUT, PASTA_QUARENTENA, rel)
                print(f"      ♻️  duplicata -> {PASTA_QUARENTENA}: {nome}")
                movidos += 1
                if executar:
                    os.makedirs(os.path.dirname(quarentena), exist_ok=True)
                    try:
                        os.replace(origem, quarentena)
                    except OSError as erro:
                        print(f"      ❌ falhou: {erro}")
                continue
            print(f"      ⚠️  existe fora mas com conteúdo diferente, mantido: {nome}")
            conflitos += 1
            continue
        print(f"      {nome}  ↑")
        movidos += 1
        if executar:
            try:
                os.replace(origem, destino)
            except OSError as erro:
                print(f"      ❌ falhou: {erro}")

    if executar and not conflitos:
        try:
            os.rmdir(pasta_intrusa)
        except OSError as erro:
            print(f"      ⚠️  não consegui remover a pasta vazia: {erro}")
    return movidos, conflitos


def reparar(executar=False):
    total_intrusas = total_movidos = total_conflitos = 0

    for comunidade, cursos in ESTRUTURA.items():
        raiz_com = os.path.join(PASTA_OUTPUT, comunidade)
        if not os.path.isdir(raiz_com):
            print(f"⏭️  comunidade não encontrada no disco: {comunidade}")
            continue

        for curso, modulos in cursos.items():
            raiz_curso = os.path.join(raiz_com, limpar(curso))
            if not os.path.isdir(raiz_curso):
                continue

            validos = {limpar(m) for m in modulos}

            # De baixo para cima: uma intrusa pode estar dentro de um módulo.
            for atual, subpastas, _ in os.walk(raiz_curso, topdown=False):
                if atual == raiz_curso:
                    alvos = subpastas
                elif limpar(os.path.basename(atual)) in validos:
                    alvos = subpastas       # dentro de um módulo real
                else:
                    continue                # dentro de pasta de aula: não mexe

                for sub in list(alvos):
                    caminho = os.path.join(atual, sub)
                    if limpar(sub) in validos or eh_pasta_de_aula(caminho):
                        continue

                    rel = os.path.relpath(caminho, PASTA_OUTPUT)
                    print(f"\n🚫 intrusa: {rel}")
                    total_intrusas += 1
                    m, c = promover(caminho, executar)
                    total_movidos += m
                    total_conflitos += c

    print("\n" + "=" * 60)
    print(f"Pastas intrusas   : {total_intrusas}")
    print(f"Itens promovidos  : {total_movidos}")
    if total_conflitos:
        print(f"Conflitos mantidos: {total_conflitos}")
    if executar:
        print("\n✅ Reparo executado.")
    else:
        print("\n🔎 SIMULAÇÃO — nada foi movido.")
        print("   Para aplicar:  python reparar_pastas_canal.py --executar")
    return 0


if __name__ == "__main__":
    sys.exit(reparar(executar="--executar" in sys.argv))
