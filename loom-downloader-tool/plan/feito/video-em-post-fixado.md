# Vídeo que mora num post fixado

> **STATUS: IMPLEMENTADO** (12/08/2026, v4.1). Código em `extension/content.js`:
> `postsFixadosComVideo` (`:400`), `resolverVideoDePostFixado` (`:411`) e a
> condição `semVideoNenhum` na fase 1 do enfileiramento (`:548`).

## O sintoma

Aulas que na tela do Skool mostram um vídeo (dentro de um modal) não baixavam.
Nenhum erro, nenhum aviso: geravam um `.md` placeholder e a fila seguia. Foi
percebido só porque o dono do projeto reparou num vídeo que ele sabia existir.

## A causa

A leitura da unit (`content.js:287-299`) só reconhecia duas formas de vídeo:

| Campo | Onde | Motor |
|---|---|---|
| `metadata.videoLink` | Loom / YouTube / Vimeo | yt-dlp ou HLS próprio |
| `metadata.videoId` | vídeo hospedado no Skool (Mux) | yt-dlp |

Existe uma terceira, que ninguém tinha visto: o vídeo fica num **post fixado** à
aula, e o campo do post se chama **`videoIds`** — plural. Nome parecido o
bastante para não levantar suspeita, diferente o bastante para nunca casar.

Nessas aulas, o `metadata` da unit é:

```
videoLink: null
videoId:   null
desc:      "[v2][{"type":"paragraph"}]"    <- parágrafo VAZIO
resources: "[]"
```

## A medição (12/08/2026, comunidade ai-makers)

280 aulas no total, 67 sem vídeo próprio. Dessas 67:

| Curso | Órfãs | De |
|---|---|---|
| Office Hours com Well Pires | **37** | 85 |
| Founders Talk | **12** | 20 |
| Biblioteca de Templates | 2 | 38 |
| N8N Pro | 1 | 18 |
| **Total** | **52** | 280 |

As outras **15 são vazias de verdade** — sem vídeo em lugar nenhum. O `.md`
placeholder delas está correto.

**52 de 280 = 18,6% do acervo** estava sendo perdido em silêncio.

Uma aula tem **2 posts fixados com vídeo** (o resto tem 1). Baixamos o primeiro e
avisamos no console — perder o segundo calado seria repetir o bug.

## Onde cada dado mora (medido, não suposto)

- **`pinnedPosts` pertence à aula ABERTA**, não à unit. Fica em `pageProps` e em
  `pageProps.renderData`, ao lado de `selectedModule`. Varrer a listagem do curso
  nunca acha: cada requisição só revela os pins de UMA aula. Por isso a detecção
  exige uma busca por aula candidata.
- O JSON da aula traz **só o ID** do vídeo (hex de 32 chars). O par
  `playbackId` + `playbackToken` exige buscar o post, pelo slug em `post.name`:
  `/_next/data/{buildId}/{group}/{post.name}.json`.
- Com o par em mãos, a URL é a mesma que o projeto já usava para vídeo do Skool:
  `https://stream.video.skool.com/{playbackId}.m3u8?token={playbackToken}`.

## Duas armadilhas que quase estragaram a medição

**1. O `desc` truthy.** A condição da fase 1 era
`if (!aula.desc || faltaVideo)`. O `desc` das órfãs é `[v2][{"type":"paragraph"}]`
— **string não vazia**, logo `!aula.desc` é `false`. E `faltaVideo` depende de
`_videoId`, que elas não têm. Resultado: a busca era pulada e o post fixado nunca
seria visto, mesmo com o resto do código correto. Daí a condição nova
`semVideoNenhum`.

**2. O redirect comendo o `md`.** O script de varredura seguia o `__N_REDIRECT`
reaproveitando a querystring **do redirect**, que carrega o `md` da aula PADRÃO do
curso. Toda sondagem voltava a mesma aula, e o detector reportou **0 órfãs** —
inclusive no curso onde uma órfã já estava provada. O erro só apareceu porque o
resultado foi conferido contra um caso conhecido; a "validação" anterior tinha
passado por acidente, testando a lógica solta em vez da função de verdade.

Lição registrada: **validar o validador contra um caso que ele TEM que pegar**,
e garantir que o teste percorra o mesmo caminho de código da execução real.

## O que não foi verificado

- Se a fase 1 resolve as 52 na prática. A implementação está conferida por
  sintaxe (`node --check`) e as chamadas foram medidas uma a uma no navegador,
  mas o fluxo completo com a extensão recarregada **não** foi executado.
- Se outras comunidades (BACKROOM.EXE, Vibe Coding Base, Vibe Coding School +,
  Z4 CLIENTS) têm o mesmo padrão. A medição cobriu só a ai-makers.
- Se `videoIds` algum dia traz mais de um id na mesma string. Nas 52 medidas veio
  sempre um hex de 32 chars sem vírgula, mas o nome no plural pede cuidado.

## Custo em requisições

A condição nova faz o enfileiramento buscar também as aulas sem vídeo — 67 a mais
na ai-makers, das quais 52 disparam uma segunda busca (a do post). Vai com a mesma
concorrência 4 e o mesmo respiro de 200 ms das outras fases.
