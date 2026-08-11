# Brechas descobertas: anexos e vídeo hospedado no Skool

> **STATUS: AS DUAS BRECHAS ESTÃO FECHADAS.** Conferido no código em 11/08/2026:
>
> | item | onde está hoje |
> |---|---|
> | Vídeo do Skool (Mux) | `server/services/skool.py` (`eh_url_skool_video:40`, `_diagnosticar:55`, `baixar_skool:180`), roteado em `routes.py:241` |
> | **Anexos (`file_id`)** | `baixar_anexos` (`skool.py:117`), chamado em `routes.py:208` — **antes** do vídeo, de propósito |
> | Dashboard reescrito | `server/dashboard.py` inteiro; já rodou e foi reescrito outra vez desde então (marca, tabela de Cursos, orçamento de altura) |
> | Botão individual do vídeo do Skool | `criarBotaoVideoSkool` (`extension/content.js:1066`) — **saiu do "fora de escopo"**, existe |
>
> Duas afirmações **deste documento envelheceram** e estão anotadas no corpo:
> a de que `processar_download` já baixaria o HLS do Mux (refutada mais abaixo,
> no próprio texto) e a de que um 403 cairia nos `except:` nus do downloader
> (esses `except:` não existem mais — hoje há retry com backoff e falha reportada).

Data: 2026-08-10 · Medido em `ai-makers` (280 aulas, 11 cursos acessíveis)

## Resumo: o que se perde hoje

| situação | aulas | hoje |
|---|---|---|
| `metadata.videoLink` (Loom/YouTube) | 181 | baixa ✓ |
| **só `metadata.videoId`** (vídeo do próprio Skool) | **32** | **nada é baixado** |
| sem vídeo (aula de texto) | 67 | `.md` ✓ |
| **`resources` com `file_id`** (arquivo anexo) | **44** | só o nome vai pro `.md` |

Casos extremos do `videoId`: **Supabase** (7 de 7 aulas — o curso inteiro baixa zero
vídeos) e **Agentes IA de WhatsApp** (16 de 21).

`extrairAulas` (`content.js:288-290`) só testa `videoLink`, então as aulas de `videoId`
saem com `_temVideo:false` e viram só `.md`. Não há aviso — é falha silenciosa.

---

## Brecha 1 — Arquivos anexos (`resources` com `file_id`)

### O `resources` tem DUAS formas

```jsonc
// (a) link  — já tratado
[{"title":"...", "link":"https://..."}]
// (b) arquivo — o nome é registrado, os bytes NÃO
[{"title":"Workflow de disparos",
  "file_id":"c865dac770b445c0b8d79eadd0e97a63",
  "file_name":"Disparo WhatsApp -_ ProspectOS (1).json",
  "file_content_type":"application/json"}]
```

`pareceResources()` (`content.js:134`) aceita a forma (b) porque ela tem `title` — por
isso o anexo *parece* capturado quando na verdade só o rótulo foi.

### Protocolo de download (medido)

1. `POST https://api2.skool.com/files/{file_id}/download-url?expire=28800`
   com `credentials:'include'`. **POST, não GET** (GET responde `405`).
2. A resposta é **texto puro** (não JSON): a URL final em `files.skool.com/f/{groupId}/{hash}`.
3. Essa URL **não precisa de cookie** — é assinada. `Range: bytes=0-0` devolveu `206`.

Descoberto abrindo o modal do anexo: **abrir o modal já dispara o POST**, o botão
DOWNLOAD não precisa ser clicado.

---

## Brecha 2 — Vídeo hospedado pelo Skool (`videoId`)

O player não é iframe nem `<video>` com src direto: é **HLS via Mux white-label**
(o beacon `inferred.litix.io` entrega o Mux).

### O mapeamento `videoId` → playback vem no JSON da própria aula

`pageProps.video` do JSON da aula ABERTA (`?md=<id>`):

```jsonc
"video": {
  "id": "40243e8c1cea46debb35f386593f71ae",   // == metadata.videoId
  "playbackId": "wtE52QYMvvTN9U401c7SZPm7EQuXy5mca418xacVUz8c",
  "playbackToken": "<JWT assinado>",
  "thumbnailToken": "...", "storyboardToken": "...",
  "expire": ..., "duration": ..., "aspectRatio": ..., "status": ...
}
```

### URL do stream (medido)

```
https://stream.video.skool.com/{playbackId}.m3u8?token={playbackToken}
```

| | resultado |
|---|---|
| sem `token` | **403** |
| com `token` | **200**, `#EXTM3U` válido (master playlist, 15 linhas) |

### Por que isso encaixa bem na arquitetura atual

> ⛔ **REFUTADO no mesmo dia** — ver "Por que NÃO reaproveitamos o `processar_download`",
> mais abaixo. O master do Mux é incompatível com o motor HLS do Loom em dois pontos
> medidos. Ficou registrado como exemplo do que acontece ao supor compatibilidade
> por "é HLS também" sem abrir o arquivo.

- É **HLS** — `processar_download` (`services/downloader.py:44`, hoje `:201`) já baixa
  exatamente isso. **O servidor não precisa de motor novo**; basta receber a URL `.m3u8`.
- `pageProps.video` vem **na mesma resposta** que `buscarTextoDaAula(md, ctx)`
  (`content.js:358`) já busca por aula. Dá para ler o vídeo **sem nenhum request extra**.

### RISCO — o token expira

`video.expire` existe e a URL sem token dá 403. Enfileirar 280 aulas pode levar horas;
um token capturado no início pode estar morto quando a aula chegar na vez, e o
resultado seria um 403 engolido pelos `except:` nus do downloader — **falha silenciosa,
de novo**. Precisa de decisão: resolver o token no momento do download (servidor pede à
extensão / refaz o fetch) ou detectar 403 e re-resolver. Não implementar sem tratar isso.

> **Resolvido (Opção A, ver adiante) e o cenário do 403 mudou:** os `except:` nus
> citados aqui não existem mais no `downloader.py`. De qualquer forma o vídeo do Skool
> nem passa por ele — vai pelo yt-dlp, com `_diagnosticar` (`skool.py:55`) checando o
> master antes e traduzindo 403/400 numa mensagem acionável.

---

---

## Dashboard do terminal — FEITO (o restart já aconteceu; painel novo em produção)

Reescrito `server/dashboard.py`. Só esse arquivo mudou: o `folder` já era gravado em
cada item (`routes.py:163`), então o agrupamento por curso/módulo saiu de graça.

- **Painel Progresso Geral**: concluídas / erros / baixando / na fila, "faltam N de M",
  barra global e **ETA**.
- **Tabela Cursos**: por curso — módulo atual, barra, `feitas/total` e erros. Mostra
  pendentes primeiro, no máximo 8 linhas.
- Fila cortada em 5 + contador (200+ aulas empurravam o painel para fora da tela).
- Leitura sempre de `list(DASHBOARD_DATA)`: a lista é mutada por threads sem lock e
  iterar direto arriscava `list changed size during iteration`.
- ETA pelo ritmo **observado** (intervalo entre conclusões), não pelo tempo desde a
  subida do servidor — senão a ociosidade inicial envenenaria a média. Devolve `None`
  com menos de 3 conclusões: melhor não mostrar nada do que inventar.

Validado fora do servidor (`scratchpad/testar_dashboard.py`, 108 itens sintéticos):
ETA 924s para 77 restantes a 12s/aula = exato; agrupamento correto; casos-limite `None`.

**Pendente: reiniciar o servidor** para o painel novo entrar. Não reiniciei porque havia
download em andamento.

---

## Vídeo do Skool — IMPLEMENTADO (Opção A)

Decisão: **a extensão resolve o token no enfileiramento e manda o `.m3u8` pronto**.
Motivo: o servidor **não tem sessão do Skool** — nenhum cookie —, então ele é
*incapaz* de resolver o token. A alternativa (servidor detecta 403 e pede token novo)
exigiria um canal servidor→extensão que hoje não existe e que morre quando a aba
fecha. Com o token valendo ~24h e a fila levando ~3h, a folga é grande.

### Por que NÃO reaproveitamos o `processar_download`

O master do Mux é incompatível com ele em dois pontos **medidos**:

1. URIs **absolutas em outro host** (`manifest-*.fastly.video.skool.com`), enquanto o
   downloader monta `base_url + uri` assumindo caminho relativo.
2. Segmentos de vídeo e áudio com **nomes idênticos** (`0.m4s`, `1.m4s`, … — 147 de
   cada). Gravando por `basename` numa pasta só, o áudio sobrescreveria o vídeo; e o
   check de retomada ("existe e tem bytes → sucesso") faria os 147 segmentos de áudio
   passarem instantaneamente. Resultado: mp4 corrompido **sem um único erro na tela**.

Por isso usamos o `baixar_com_ytdlp`, o mesmo motor de YouTube/Vimeo — ele já trata
URI absoluta, áudio separado e fMP4.

### Arquivos

- **NOVO** `server/services/skool.py` — `eh_url_skool_video`, `url_stream_skool`,
  `_diagnosticar`, `baixar_skool`.
- `server/services/__init__.py` — reexporta os três públicos.
- `server/routes.py` — roteia `stream.video.skool.com` para `baixar_skool`.
- `extension/content.js`:
  - `extrairAulas` marca `_videoId` quando não há `videoLink`; `_temVideo` passa a
    considerar os dois.
  - `extrairVideoSkool(pp, videoId)` monta a URL, **conferindo `v.id === videoId`** —
    as buscas por aula são concorrentes e sem essa checagem uma resposta trocada
    colaria o vídeo de outra aula.
  - `buscarTextoDaAula(md, ctx, videoId)` devolve também `urlVideo` — **na mesma
    resposta que já buscava o texto, zero request extra**.
  - Fase 1 do `enfileirarCurso` passa a buscar também quando falta vídeo (antes, uma
    aula que já tivesse `desc` pulava o fetch e o vídeo sumia).
  - Aviso no console listando vídeos do Skool que não resolveram.

### Falha alta (o ponto inegociável)

`_diagnosticar` checa o master antes de gastar o yt-dlp. **Medido:** sem token → 403;
token malformado → 400. Os dois viram a MESMA mensagem acionável ("token expirado —
reenfileire; as aulas já baixadas são puladas"), em vez de um status cru ou, pior, de
um buraco silencioso.

### Validação

| item | resultado |
|---|---|
| `node --check content.js` | OK |
| `import services` / `import routes` | OK |
| `eh_url_skool_video` (skool / loom / yt / vazio) | True / False / False / False |
| `url_stream_skool` sem token | `None` |
| `_diagnosticar` sem token | 403 → mensagem acionável |
| `_diagnosticar` token malformado | 400 → mesma mensagem |
| `baixar_skool` com URL ruim | `False` + motivo impresso |
| yt-dlp sobre master Mux | 6 formatos, 1080p avc1, extrator genérico |
| Servidor sobe após as mudanças | OK (janela própria, porta 5000) |

### Motor HLS validado com fixture local

Os testes contra o asset público do Mux morreram por **duração** (meu `timeout` matando
o ffmpeg — exit 143 = SIGTERM), nunca por defeito do código. Para fechar a questão,
geramos um HLS local curto com a mesma estrutura (master + **áudio separado** + fMP4)
e servimos em `127.0.0.1` (`scratchpad/teste_hls_local.py`):

| | resultado |
|---|---|
| `baixar_com_ytdlp` sobre HLS c/ áudio separado | `True` |
| `.mp4` final | existe, 273 KB |
| streams no arquivo (ffprobe) | `video/h264` + `audio/aac` |
| **áudio presente no mp4** | **sim** — a fusão funciona |
| progress hook | `total=100` + **100 incrementos** |

**A barra do dashboard anda em vídeo do Skool.** Chegamos a suspeitar do contrário
(um teste anterior voltou sem callbacks), e por isso NÃO mexemos no `ytdlp.py` —
ele é compartilhado com YouTube/Vimeo e a suspeita se provou falsa. Medir primeiro
evitou uma mudança errada em código que já funcionava.

**Não validado de ponta a ponta:** o POST real da extensão com token vivo. A página
HTTPS não alcança `localhost` no *main world* (só o content script, que tem
`host_permissions`), então não deu para simular sem recarregar a extensão.

### Escopo deliberadamente deixado de fora — DEPOIS FEITO

Aula com vídeo do Skool **não ganha botão individual** na página (o player é Mux, não
iframe, e o pill atual só nasce em iframe do Loom). O caminho de curso/comunidade
cobre essas aulas. Anexos (`file_id`) seguem pendentes.

> ✅ **Os dois foram implementados depois.**
> - **Botão individual:** `criarBotaoVideoSkool` (`extension/content.js:1066`). Acha o
>   player pela `background-image` de `image.video.skool.com` — medido: antes do play
>   não existe `<video>` nem `<img>`, a thumbnail é background de uma div, e a primeira
>   tentativa (`img[src*=…]`) nunca casava. Resolve o token **no clique**, nunca guarda
>   token velho, e se auto-limita por `md` para o MutationObserver não virar enxurrada
>   de fetch.
> - **Anexos:** `baixar_anexos` (`server/services/skool.py:117`) + resolução da URL
>   assinada na extensão. O nome vira `<Aula> - <arquivo.ext>` com orçamento de
>   caracteres dividido entre os dois (`_nome_do_anexo`, `skool.py:97`) — truncar só o
>   arquivo deixava o nome final estourar 90 chars com título de aula longo (medido:
>   147). Dentro da pasta própria da aula o prefixo é dispensado (`prefixar=False`).

## Ordem sugerida — CUMPRIDA

1. ~~**Vídeo `videoId`**~~ — 32 aulas de vídeo perdidas, e um curso inteiro (Supabase)
   zerado. **Feito** (Opção A: extensão resolve o token e manda o `.m3u8`).
2. ~~**Anexos**~~ — 44 aulas; conteúdo complementar, não a aula em si. **Feito.**

Ambos dependiam de decidir o tratamento do token/URL expirável — decidido em favor de
resolver na extensão, com detecção explícita de expiração no servidor.
