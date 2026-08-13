# Benchmark de concorrência — quantos downloads simultâneos?

> **STATUS: CONCLUÍDO** (11/08/2026). A decisão está no código: `_SIMULTANEOS`
> (`server/routes.py:42-45`), padrão 4, ajustável por `SIFAO_DOWNLOADS_SIMULTANEOS`.
> A pendência que este documento levantou no fim (retry de segmento) **também foi
> resolvida** — ver a seção final, atualizada.

**Decisão: 4** (já é o padrão em `server/routes.py`, via `SIFAO_DOWNLOADS_SIMULTANEOS`).

Medido em 11/08/2026. Cada rodada baixa **as mesmas 12 aulas** (1198 MB) do
Bootcamp Mês 1 — o nível não muda o volume, só quantas ficam em voo.

## Resultado final (máquina limpa, n=3 por nível)

| Nível | Rodadas | Média | Dispersão | Completas |
|---|---|---|---|---|
| 1 | 411 / 401 / 411 | 407,7s | 2,5% | 3/3 |
| **4** | **329 / 328 / 324** | **327s** | **1,5%** | **6/6** |
| 8 | 334 / 338 / 334 | 335,3s | 1,2% | 3/4 |

As faixas **não se sobrepõem**: nível 4 em [324, 329], nível 8 em [334, 338].
SD ≈ 2,5s nos dois; diferença de 8,3s dá t ≈ 4,1 (df=4), acima do crítico 2,78.
Significativa.

- 1 → 4: **19,8% mais rápido**
- 4 → 8: **2,5% mais lento**

O nível 8 ainda **travou uma rodada** (11/12 aulas, 1108 MB) na máquina limpa,
sem interferência externa. O nível 4 completou 6 de 6.

## 5, 6 e 7 não foram medidos — decisão consciente

O teste chegou a ser lançado (15 rodadas: 4,5,6,7,8 × 3, ~90 min) e foi
**cancelado de propósito**. Motivo: o intervalo inteiro entre 4 e 8 vale 8,3s
(2,5%). Se a degradação for regular, cada vaga custa ~2s — e com SD ≈ 2,5s e n=3
o teste só declara significativa uma diferença ≥ 5,7s. Ou seja: 90 minutos para,
no melhor caso, descobrir um ganho abaixo de 2% que provavelmente nem seria
declarável.

O topo da curva é chato. **4 fica como número oficial.**

Se algum dia valer a pena refazer: o caminho não é comparar pares, é ajustar uma
reta de tempo × vagas sobre os 15 pontos — a tendência aparece onde o teste-t
entre dois grupos de 3 não alcança.

## O ruído, medido (a questão central)

Não dá para comparar níveis sem saber quanto a máquina oscila sozinha. Método:
rodar o **mesmo** nível 3× com as rodadas **espalhadas** entre as outras. Se
fossem consecutivas, compartilhariam as condições do minuto e subestimariam a
variância.

| Estado da máquina | Ruído (amplitude) |
|---|---|
| CPU ~100% (build Tauri + VS Code + Chrome + Taskmgr) | **11%** |
| CPU ~22% em repouso | **1,5% – 2,5%** |

**O ruído era da máquina, não da rede.** Isso invalida os dois limiares que
tinham sido propostos por palpite — 5% (apertado demais para a máquina suja) e
10% (frouxo demais para a limpa). Nenhum dos dois era medido.

Consequência prática: **limpar a máquina rendeu mais que qualquer ajuste de
concorrência.** Nível 4 caiu de 441s (CPU 100%) para 327s (CPU 22%) — 26%.

## O downloader é pesado de CPU

Registrado pelo `carga.csv`: durante o download a CPU fica em **~80% de média**,
tanto no nível 1 quanto no 8. São 12 workers de segmento por aula
(`services/downloader.py:292` — era `:257` quando isto foi escrito) em Python. Por isso qualquer carga externa
degrada tanto — ela disputa com um processo que já consome quase tudo.

Conexões reais por nível = `nível × 12`: nível 1 = 12, nível 4 = 48, nível 8 = 96.

## Rodada contaminada (NÃO usar para comparar)

Primeira medição, com CPU a ~100%: 1 → 578s, 4 → 441s, 12 → 656s (10/12).
Serve só para mostrar a degradação; os números não são comparáveis com os de
cima.

## Conclusões anteriores que caíram

**"O nível 12 falhou por abrir ~144 sockets."** Teoria inventada, nunca medida.
O nível 10 completou 12/12 limpo. A variável entre os dois testes era a carga da
máquina.

**"4 e 8 são equivalentes, escolha o menor por segurança."** O empate era
artefato do ruído de 11%. Com ruído de 1,5%, o 4 é mensuravelmente mais rápido.
A conclusão sobreviveu, mas por motivo diferente do alegado na época.

**"O ruído deve continuar em ~11% mesmo com a máquina limpa, porque o disco está
ocioso e o download é ligado à rede."** Previsão registrada antes do teste e
refutada: caiu para 2,5%. A CPU havia sido descartada como gargalo sem medição.

## Erros de instrumentação (para não repetir)

- **Registrador de carga não rodou na 2ª rodada.** `Start-Process pwsh
  -ArgumentList '-File','C:\Users\Eduardo Ribeiro\...'` — o espaço em "Eduardo
  Ribeiro" quebrou o caminho; o pwsh recebeu `C:\Users\Eduardo` e morreu na hora.
  Correto: `-ArgumentList @('-NoProfile','-File',"`"$caminho`"")`, e **conferir
  que o arquivo de saída existe** antes de lançar o teste.
- **Detector de progresso contava `.mp4` prontos** com timeout de 120s. Com
  concorrência alta a 1ª conclusão leva ~185s, então ele desistia e reportava
  0 downloads — falso. Corrigido para medir bytes em disco, incluindo `.part` e
  `hls-temp`.
- **O script imprime "Mais rapido: nivel N"** pegando o mínimo, sem considerar
  ruído. Ignorar essa linha.

## Pendência de maior retorno — ATENDIDA (11/08/2026)

**O que este documento registrou na época:** o nível 8 travou perdendo uma aula
**sem erro visível**. `_baixar_segmento` engolia exceções e não tinha retry — uma
aula travada virava arquivo faltando ou vídeo com buraco. Causa provável das "2
aulas que faltaram de 280".

**O que existe hoje** (`services/downloader.py`, após `db40b47` + o timeout):

- `TENTATIVAS_POR_SEGMENTO = 3` (`:10`) com backoff `0.5 × tentativa`;
- `_baixar_segmento` (`:126`) devolve `True`/`False` e **apaga o arquivo parcial**
  ao desistir, para o parcial não passar como sucesso na retomada;
- `processar_download` conta as falhas e imprime o total (`:296-300`);
- `TIMEOUT_SEGUNDOS = 20` (`:22`) em **todas** as requisições, e `_baixar_texto`
  (`:173`) leva master e mediaplaylists pela mesma política.

O timeout veio de uma trava observada **nesta própria bateria**: numa rodada de
nível 8, uma aula ficou com ZERO bytes por mais de 120s enquanto as outras 11
terminaram. Zero bytes significa trava **antes** do primeiro segmento — ou seja,
no download do master/playlist, que era exatamente o trecho sem timeout. E como
`requests` sem `timeout` nunca levanta exceção, o retry jamais era acionado: a
thread ficava presa para sempre. **A trava que motivou esta pendência era um
socket pendurado, não sobrecarga de concorrência.**

**O que continua em aberto:** `processar_download` devolve `True` mesmo com
segmentos perdidos, então o vídeo furado é convertido e a aula aparece como
sucesso no dashboard. A falha deixou de ser silenciosa no código, mas ainda não
vira status de erro.
