"""Mede o tempo real de download em varios niveis de concorrencia.

Para achar o numero ideal desta maquina sem chutar. Cada nivel baixa AS MESMAS
aulas numa pasta propria, entao os bytes sao identicos e o tempo e comparavel.

    python bench_concorrencia.py                 # piloto: 4 aulas, niveis 2 e 6
    python bench_concorrencia.py 12 4,8,12       # 12 aulas nos niveis 4, 8 e 12

Ao final apaga a pasta _BENCH.
"""
import os
import random
import shutil
import subprocess
import sys
import time

import requests

RAIZ = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(RAIZ, "venv", "Scripts", "python.exe")
APP = os.path.join(RAIZ, "server", "app.py")
OUT = os.path.join(RAIZ, "output")
PASTA_BENCH = "_BENCH"
SERVIDOR = "http://localhost:5000/baixar"

# Aulas reais do Bootcamp Mes 1 (Loom). URLs sem token, entao servem de fixture.
IDS = """3d001568221540bc895c39adbabad628,1ef2135b93dc48e7b78498649e0ea409,
de51a866533b4c33844485b93499ffd8,960c53583abd4dccb446a9325ae568ec,
e98dab8329c14ec78727d078ef5b7586,d5db5d68f15d44d792c582bbe5827342,
a5c1e91b991e4077bec5527123c1c6d3,7edc212972024dd192140892a19a87dc,
f43a3cb428f04d2fb4bacf5e3cbc5824,f3781d8d807c4800819378e855a40cc0,
8130ce0a82004df697b00863684be437,574f5be29f1940c68b40fc30d78f58e1,
483b0587714945059db331bac898769a,3a712415abb84d199fd73fad393488f2,
ee8f34365e3f41d69a5200751f42518d,095ec91493054a4b85684b3aa7a36b54,
1981559d720c40e6972ba5fb253ac51a,b396a5dc10dd433a8e5a4525be10ada5,
51b8059ff9ae469cbc49a2c52bf53997,c7290b0bf202485481168f100773f5ca""".split(",")
IDS = [i.strip() for i in IDS if i.strip()]

OCIOSO_S = 120      # sem arquivo novo por tanto tempo => a rodada acabou
TETO_S = 1800       # trava de seguranca por nivel


def porta_ocupada():
    import socket
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", 5000)) == 0


def matar_servidor():
    subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue |"
         " ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"],
        capture_output=True)
    for _ in range(20):
        if not porta_ocupada():
            return
        time.sleep(0.5)


def subir_servidor(concorrencia):
    """Sobe o servidor com o nivel pedido, guardando a saida num log.

    Mandar a saida para DEVNULL (a 1a versao) escondeu o motivo de os niveis 2 e 3
    renderem 0 arquivos: sem o log, so dava para especular. Agora cada nivel deixa
    um bench_servidor_c{N}.log para leitura.
    """
    env = dict(os.environ, SIFAO_DOWNLOADS_SIMULTANEOS=str(concorrencia))
    log = open(os.path.join(RAIZ, f"bench_servidor_c{concorrencia}.log"), "w",
               encoding="utf-8", errors="replace")
    proc = subprocess.Popen([PYTHON, APP], cwd=RAIZ, env=env,
                            stdout=log, stderr=subprocess.STDOUT)
    for _ in range(60):
        if porta_ocupada():
            time.sleep(1)       # respiro para o executor ficar pronto
            return proc
        time.sleep(0.5)
    proc.kill()
    raise RuntimeError("servidor nao subiu")


def _finais(pasta_abs):
    """Arquivos .mp4 CONCLUIDOS (ignora temporarios do yt-dlp e .part)."""
    achados = []
    for raiz, _, arquivos in os.walk(pasta_abs):
        for a in arquivos:
            if a.lower().endswith(".mp4") and not a.startswith("._yt_"):
                achados.append(os.path.join(raiz, a))
    return achados


def _bytes_em_progresso(pasta_abs):
    """Bytes ja em disco: os finais + os temporarios (.part, segmentos HLS).

    Inclui a hls-temp porque o caminho do Loom baixa os segmentos la e so gera o
    .mp4 no fim: sem isso, uma aula longa pareceria congelada durante todo o
    download.
    """
    total = 0
    for base in (pasta_abs, os.path.join(RAIZ, "hls-temp")):
        for raiz, _, arquivos in os.walk(base):
            for a in arquivos:
                try:
                    total += os.path.getsize(os.path.join(raiz, a))
                except OSError:
                    pass
    return total


def rodar_nivel(conc, n_aulas):
    pasta_rel = f"{PASTA_BENCH}/c{conc}"
    pasta_abs = os.path.join(OUT, PASTA_BENCH, f"c{conc}")
    shutil.rmtree(pasta_abs, ignore_errors=True)

    # CONTAMINACAO ENTRE RODADAS: hls-temp e indexado pelo NOME da aula. Usando os
    # mesmos nomes em todo nivel, a rodada seguinte encontrava segmentos da anterior
    # e `_baixar_segmento` os dava como prontos (retomada), fazendo o ffmpeg converter
    # lixo -> 0 arquivos. Medido no piloto: nivel 6 rendeu 0/4 por causa disto.
    # Nome unico por nivel + limpeza da temp resolvem os dois lados.
    shutil.rmtree(os.path.join(RAIZ, "hls-temp"), ignore_errors=True)

    matar_servidor()
    proc = subir_servidor(conc)
    try:
        alvo = IDS[:n_aulas]
        t0 = time.time()
        for n, vid in enumerate(alvo, 1):
            requests.post(SERVIDOR, json={
                "url": f"https://www.loom.com/embed/{vid}",
                "folder": pasta_rel,
                # O nivel entra no NOME: hls-temp e indexado por ele, e nomes iguais
                # entre rodadas foi o que contaminou o piloto.
                "filename": f"bench c{conc} {n:02d}",
            }, timeout=15)

        # PROGRESSO SE MEDE EM BYTES, NAO EM ARQUIVOS PRONTOS.
        # Contando so os .mp4 concluidos, a espera parecia "parada": com
        # concorrencia alta a banda se divide e NENHUMA aula termina nos primeiros
        # minutos (medido: ~46s/aula sequencial vira ~185s ate a 1a conclusao com 4
        # simultaneos). O detector desistia antes e reportava 0 downloads -- falso.
        # Bytes em disco crescem o tempo todo, entao ocioso de verdade e ocioso.
        ultima_mudanca = time.time()
        bytes_vistos = -1
        while True:
            time.sleep(5)
            agora_bytes = _bytes_em_progresso(pasta_abs)
            if agora_bytes != bytes_vistos:
                bytes_vistos = agora_bytes
                ultima_mudanca = time.time()
            if len(_finais(pasta_abs)) >= len(alvo):
                break
            if time.time() - ultima_mudanca > OCIOSO_S:
                print(f"    (sem progresso de bytes por {OCIOSO_S}s com "
                      f"{len(_finais(pasta_abs))}/{len(alvo)} prontas)")
                break
            if time.time() - t0 > TETO_S:
                print("    (teto de tempo atingido)")
                break

        segundos = time.time() - t0
        arquivos = _finais(pasta_abs)
        bytes_ = sum(os.path.getsize(f) for f in arquivos)
        return {"conc": conc, "s": segundos, "ok": len(arquivos),
                "de": len(alvo), "mb": bytes_ / 1048576}
    finally:
        matar_servidor()
        try:
            proc.kill()
        except Exception:
            pass


def main():
    n_aulas = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    niveis = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [2, 6]
    n_aulas = min(n_aulas, len(IDS))

    # Ordem embaralhada: se rodassem sempre em ordem crescente, um aquecimento de
    # cache/CDN favoreceria sistematicamente os ultimos niveis.
    ordem = niveis[:]
    random.shuffle(ordem)
    print(f"{n_aulas} aulas por nivel | niveis {niveis} | ordem de execucao {ordem}\n")

    resultados = []
    for conc in ordem:
        print(f"[nivel {conc}] baixando {n_aulas} aulas...")
        r = rodar_nivel(conc, n_aulas)
        resultados.append(r)
        print(f"    {r['s']:.0f}s | {r['ok']}/{r['de']} aulas | "
              f"{r['mb']:.0f} MB | {r['mb']/max(r['s'],0.01):.1f} MB/s\n")

    shutil.rmtree(os.path.join(OUT, PASTA_BENCH), ignore_errors=True)

    print("=" * 58)
    print(f"{'nivel':>6} | {'tempo':>8} | {'aulas':>7} | {'MB':>7} | {'MB/s':>7}")
    print("-" * 58)
    for r in sorted(resultados, key=lambda x: x["conc"]):
        print(f"{r['conc']:>6} | {r['s']:>7.0f}s | {r['ok']:>3}/{r['de']:<3} |"
              f" {r['mb']:>7.0f} | {r['mb']/max(r['s'],0.01):>7.1f}")
    completos = [r for r in resultados if r["ok"] == r["de"]]
    if completos:
        melhor = min(completos, key=lambda r: r["s"])
        print(f"\nMais rapido (rodadas completas): nivel {melhor['conc']} "
              f"({melhor['s']:.0f}s)")
    print("\nATENCAO: uma unica medicao por nivel. Diferencas menores que ~10% "
          "estao dentro do ruido de rede.")


if __name__ == "__main__":
    main()
