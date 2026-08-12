# Barra de progresso que não mente

> **STATUS: PARCIAL.** Três defeitos corrigidos, um aberto — o principal.

## O problema, na palavra do dono do projeto

> "ele tá aparecendo aqui 100% baixando o vídeo e não avança (…) a barra precisa
> estar mais alinhada. Se tá ainda um processo em andamento, ela precisa mostrar
> andando, não travada aqui no 100% de morte"

Barra parada dá impressão de travamento. Já quase custou um servidor derrubado no
meio de 400 MB baixados — a pessoa achou que estava pendurado e ia matar o
processo. **Barra parada não é problema de estética: é informação errada.**

## Já corrigido

**Barra congelada em 100% durante o áudio.** O yt-dlp baixa vídeo e áudio como
downloads SEPARADOS. O contador `ultimo_pct` só crescia, então a barra enchia no
fim do vídeo e ficava lá durante todo o áudio. Hoje a faixa nova reinicia o
contador (`ytdlp.py`, `_hook`).

**Status genérico.** Dizia só "Baixando". Hoje diz a fase: `Baixando vídeo ⬇`,
`Baixando áudio 🔊`, `Convertendo ⚙️` (`_ROTULO_STATUS` em `dashboard.py`,
alimentado por `ao_fase` → `marcar_fase` em `routes.py`).

**Barra passando de 100%.** `atualizar_progresso(total=100)` definia o total sem
zerar o progresso, e o contador do áudio seguia de onde o vídeo parou: 140%, 200%
na tela. Corrigido na origem, com trava `0..100` no painel por garantia. Coberto
por `test_barra_nao_passa_de_100_entre_faixas`.

## Aberto: os 100% mortos entre etapas

Continua havendo um intervalo em que a barra marca 100% e nada acontece — entre
uma faixa terminar e a próxima começar, e durante a conversão.

### Desenho proposto (não implementado)

Cada etapa ocupa uma FAIXA da barra, em vez dos 100%:

| Etapa | Faixa |
|---|---|
| Baixando vídeo | 0% → 45% |
| Baixando áudio | 45% → 85% |
| Convertendo | 85% → 99% |
| Pronto | 100% |

Ganhos: a barra nunca anda para trás (hoje ela zera na troca de faixa, o que
também incomoda) e **100% passa a significar pronto**, só isso. Etapa que não
existir — vídeo com faixa única — faz a barra saltar para frente, que é
movimento e não confunde.

### Progresso REAL da conversão

Medido em 12/08/2026, não suposto:

```
ffmpeg -progress pipe:1 -nostats ...   ->   out_time_ms=2800000
                                            progress=end
```

Num vídeo de 3s o ffmpeg reportou 2,8s processados. Com a duração total em mãos,
`out_time_ms / duracao_total` dá **percentual de verdade** — não estimativa.

**Onde dá para usar:** `services/converter.py:49`, que é o ffmpeg que NÓS
chamamos (caminho do Loom). Hoje ele roda com `subprocess.call` e
`stderr=DEVNULL`; viraria `Popen` lendo a saída de progresso.

**Onde NÃO dá:** a fusão do yt-dlp. O ffmpeg roda por dentro dele e não há como
injetar o parâmetro. Os `postprocessor_hooks` do yt-dlp só dizem "começou" e
"terminou". Alternativas honestas ali: mostrar tempo decorrido, ou um indicador
animado que não finge ser medição.

A duração total do vídeo está disponível nos dois caminhos: no Loom sai da soma
dos `#EXTINF` da playlist; no Skool vem em `metadata.videoLenMs`.

## Ordem sugerida

1. Faixas por etapa — resolve o "100% morto" em todos os caminhos.
2. `-progress` no `converter.py` — troca a faixa estimada por medição real no
   caminho do Loom.
3. Indicador animado para a fusão do yt-dlp, onde medir é impossível.

## Critério para dar por pronto

Assistir uma aula longa baixar do começo ao fim sem a barra ficar parada mais que
uns poucos segundos em nenhum ponto, e 100% aparecer só quando o `.mp4` existir.
