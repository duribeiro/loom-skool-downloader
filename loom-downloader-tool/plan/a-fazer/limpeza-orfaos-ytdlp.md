# Órfãos `._yt_*` de reinícios de servidor

> **STATUS: ABERTO.** ~1 GB parado em disco. Precisa de aval antes de apagar.

## O que é

O yt-dlp grava com nome temporário `._yt_<uuid>.<formato>.<ext>` e só renomeia
para o nome final quando termina. Se o servidor morre no meio, o temporário fica.

Medido em 12/08/2026, com a fila ainda rodando: **19 arquivos em 8 downloads
distintos, 946 MB**. Mas a concorrência é 4 — no máximo 4 podiam estar vivos.
Medindo o crescimento em 60s:

```
_yt_06e36622   515,1 MB   +223,6 MB   CRESCENDO
_yt_a3e308e6   126,2 MB   +35,6 MB    CRESCENDO
_yt_19ec6cba    87,1 MB   +0 MB       parado
_yt_72d8aab0    52,5 MB   +0 MB       parado
_yt_99a982f9     8,2 MB   +0 MB       parado
_yt_a57001fc    69,9 MB   +0 MB       parado
_yt_cd6c6efb   105,5 MB   +0 MB       parado
```

Os parados são restos dos reinícios de servidor feitos durante a depuração de
hoje.

## Como limpar sem risco

**Com a fila vazia, todo `._yt_*` é lixo** — não há download vivo para confundir.
Esse é o momento seguro, e não exige heurística nenhuma:

```bash
# conferir antes
find output -name "._yt_*" -type f | wc -l
find output -name "._yt_*" -type f -printf "%s\n" | awk '{s+=$1} END {print s/1048576 " MB"}'
```

Só apagar com a porta 5000 fechada ou o painel ocioso. **Não apagar com download
em andamento**: um `._yt_*` vivo é o arquivo que está sendo escrito naquele
instante.

## Prevenção (não implementado)

`_limpar_temporarios` (`ytdlp.py:50`) já remove as sobras quando o download falha
de forma controlada, mas não roda quando o processo é morto. Uma limpeza na
SUBIDA do servidor resolveria: ao iniciar, nenhum download pode estar em curso,
então qualquer `._yt_*` presente é órfão por definição.

É o mesmo raciocínio que `app.py` já aplica ao `hls-temp/`.

## Cuidado

`output/` é do usuário e tem ~46 GB de aulas baixadas. Qualquer limpeza aqui
lista o alvo antes e só apaga o que casa com o padrão `._yt_*` — nunca `.mp4`,
`.md` ou anexos.
