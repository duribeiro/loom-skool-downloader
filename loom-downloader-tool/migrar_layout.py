"""Reorganiza a `output/` para o layout de pasta por aula (Sifão 4.0).

Regra (a mesma do servidor): aula que gerou 2+ arquivos ganha pasta com o nome dela;
aula com um arquivo só continua solta.

    Modulo/Aula X.mp4                 ->  Modulo/Aula X/Aula X.mp4
    Modulo/Aula X.md                  ->  Modulo/Aula X/Aula X.md
    Modulo/Aula X - template.json     ->  Modulo/Aula X/template.json
    Modulo/Aula Y.mp4   (sozinha)     ->  fica onde está

SIMULA por padrão. Só move de verdade com `--executar`.

    python migrar_layout.py              # mostra o que faria
    python migrar_layout.py --executar   # faz
"""
import os
import sys

PASTA_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# Extensões que DEFINEM uma aula. O resto (json, zip, pdf...) é anexo e se liga a uma
# aula pelo prefixo "<Aula> - ". Sem essa distinção, uma aula chamada
# "Aula 1 - Introdução.mp4" seria confundida com um anexo de "Aula 1".
EXT_PRINCIPAIS = {".mp4", ".md"}


def _eh_pasta_de_aula(pasta):
    """True se a pasta JÁ é a pasta de uma aula (contém arquivo com o mesmo nome)."""
    nome = os.path.basename(pasta)
    try:
        itens = os.listdir(pasta)
    except OSError:
        return False
    return any(os.path.splitext(f)[0] == nome
               for f in itens if os.path.isfile(os.path.join(pasta, f)))


def _agrupar(pasta):
    """Agrupa os arquivos soltos de uma pasta por aula. Devolve {aula: [arquivos]}."""
    # IDEMPOTÊNCIA: dentro de `Aula X/` existem `Aula X.mp4` e `Aula X.md` — um grupo
    # de 2 arquivos. Sem esta guarda o script "consertaria" o que já está certo,
    # criando `Aula X/Aula X/` a cada nova execução. Medido: de 278 grupos
    # reportados numa 2a rodada, 262 eram este falso positivo.
    if _eh_pasta_de_aula(pasta):
        return {}

    try:
        nomes = os.listdir(pasta)
    except OSError:
        return {}

    arquivos = [n for n in nomes if os.path.isfile(os.path.join(pasta, n))]

    # 1) As aulas são definidas pelos .mp4/.md.
    grupos = {}
    for nome in arquivos:
        base, ext = os.path.splitext(nome)
        if ext.lower() in EXT_PRINCIPAIS:
            grupos.setdefault(base, []).append(nome)

    # 2) Anexos entram na aula cujo prefixo casar. Se dois prefixos casarem
    #    (ex.: "Aula 1" e "Aula 1 - Extra"), vence o mais longo — o mais específico.
    for nome in arquivos:
        base, ext = os.path.splitext(nome)
        if ext.lower() in EXT_PRINCIPAIS:
            continue
        candidatos = [a for a in grupos if nome.startswith(f"{a} - ")]
        if candidatos:
            grupos[max(candidatos, key=len)].append(nome)

    return {aula: sorted(fs) for aula, fs in grupos.items() if len(fs) >= 2}


def _destino_do_arquivo(aula, nome):
    """Dentro da pasta da aula o prefixo é redundante: 'Aula - t.json' vira 't.json'."""
    prefixo = f"{aula} - "
    return nome[len(prefixo):] if nome.startswith(prefixo) else nome


def migrar(executar=False):
    if not os.path.isdir(PASTA_OUTPUT):
        print(f"❌ Não achei a pasta output em {PASTA_OUTPUT}")
        return 1

    total_aulas = total_arquivos = conflitos = 0

    for raiz, subpastas, _ in os.walk(PASTA_OUTPUT):
        grupos = _agrupar(raiz)
        if not grupos:
            continue

        # Não descer para as pastas de aula que acabamos de criar.
        subpastas[:] = [s for s in subpastas if s not in grupos]

        rel = os.path.relpath(raiz, PASTA_OUTPUT)
        print(f"\n📂 {rel}")

        for aula, arquivos in sorted(grupos.items()):
            pasta_aula = os.path.join(raiz, aula)
            print(f"   └─ {aula}/  ({len(arquivos)} arquivos)")
            total_aulas += 1

            for nome in arquivos:
                origem = os.path.join(raiz, nome)
                destino = os.path.join(pasta_aula, _destino_do_arquivo(aula, nome))

                if os.path.exists(destino):
                    print(f"      ⚠️  já existe, pulando: {os.path.basename(destino)}")
                    conflitos += 1
                    continue

                print(f"      {nome}  ->  {os.path.basename(destino)}")
                total_arquivos += 1

                if executar:
                    os.makedirs(pasta_aula, exist_ok=True)
                    try:
                        os.replace(origem, destino)
                    except OSError as erro:
                        print(f"      ❌ falhou: {erro}")

    print("\n" + "=" * 60)
    print(f"Aulas que ganham pasta : {total_aulas}")
    print(f"Arquivos movidos       : {total_arquivos}")
    if conflitos:
        print(f"Conflitos pulados      : {conflitos}")
    if executar:
        print("\n✅ Migração executada.")
    else:
        print("\n🔎 SIMULAÇÃO — nada foi movido.")
        print("   Para aplicar:  python migrar_layout.py --executar")
    return 0


if __name__ == "__main__":
    sys.exit(migrar(executar="--executar" in sys.argv))
