# CLAUDE.md

Orientações para o Claude Code (claude.ai/code) trabalhar neste repositório.

> **Números de linha conferidos em 11/08/2026** (branch `Dev`). Se o código mudou,
> confirme antes de citar — este arquivo já esteve errado por não fazer isso.

## O que é

**Sifão** (nome do programa, `dashboard.py:293`; versão `4.0`, `dashboard.py:297`).
Baixador de aulas de comunidades do **Skool**, mais vídeos avulsos de YouTube, Vimeo
e Loom. Arquitetura **híbrida**: uma extensão Chrome injeta um botão (pill) no player
— ou enfileira um curso/comunidade inteira pelo popup — e dispara pedidos para um
**servidor Flask local**, que baixa, converte com FFmpeg e organiza em `output/`.

Quatro origens de vídeo, cada uma com seu caminho:

| Origem | Detecção | Motor |
|---|---|---|
| Loom (embed no Skool ou `loom.com/share`) | fallback (nenhuma das outras) | HLS próprio — `services/downloader.py` |
| YouTube | `eh_url_youtube` (`services/youtube.py:9`) | yt-dlp |
| Vimeo (inclusive privado do Skool) | `eh_url_vimeo` (`services/vimeo.py:13`) | yt-dlp + `Referer` |
| Vídeo hospedado no Skool (Mux) | `eh_url_skool_video` (`services/skool.py:40`) | yt-dlp |

**Uma quinta forma de CHEGAR no motor do Skool:** a aula não tem vídeo próprio e o
vídeo mora num **post fixado** — campo `videoIds` (PLURAL) em
`pinnedPosts[].post.metadata`. MEDIDO em 12/08/2026: **52 das 280 aulas** da
ai-makers são assim (37 de 85 em "Office Hours com Well Pires", 12 de 20 em
"Founders Talk"), e todas eram perdidas em silêncio — viravam só um `.md`
placeholder. Resolvido por `resolverVideoDePostFixado` (`extension/content.js:411`).
As armadilhas estão em `plan/feito/video-em-post-fixado.md (índice de tudo em `plan/README.md`)`; vale ler antes de mexer no
enfileiramento.

Além do vídeo, uma aula pode render um **`.md`** (descrição + recursos do Skool,
`services/texto.py`) e **anexos** (`baixar_anexos`, `services/skool.py:117`).

Existe um projeto irmão em `../loom-dl-extension`: uma extensão **standalone** (sem
Python, sem FFmpeg) que resolve o mesmo problema de forma portátil. Este repo aqui é
o mais completo. Nenhum dos dois é legado.

## Como rodar

```bash
pip install -r requirements.txt          # flask, flask-cors, requests, rich, yt-dlp
cd loom-downloader-tool
python server/app.py                     # sobe em localhost:5000 + dashboard no terminal
```

Rodar **a partir de `loom-downloader-tool/`**, não da raiz do repo. `server/app.py:10-12`
importa `dashboard`, `services` e `routes` como módulos top-level, então `server/`
precisa estar no `sys.path` — o que o Python faz automaticamente ao executar
`python server/app.py`, mas quebra se o import for reorganizado em pacote. E
`PASTA_TEMP_RAIZ` é relativo ao cwd (ver Convenções).

**FFmpeg no PATH é obrigatório.** `verificar_ffmpeg()` (`server/app.py:26-36`) faz
`sys.exit(1)` se `shutil.which("ffmpeg")` retornar `None`. Um "o servidor não sobe" é
quase sempre isso — ou a porta ocupada: `porta_ocupada()` (`app.py:39`) recusa subir
um segundo servidor, para você não ficar com o processo ANTIGO atendendo os cliques.

Concorrência ajustável sem editar código (`routes.py:42-45`):

```bash
SIFAO_DOWNLOADS_SIMULTANEOS=6 python server/app.py    # padrão: 4
```

O padrão **4 foi medido, não chutado** — ver `loom-downloader-tool/plan/feito/benchmark-concorrencia.md`.

Extensão: `chrome://extensions` → Modo desenvolvedor → "Carregar sem compactação" →
selecionar `loom-downloader-tool/extension`.

## Fluxo de um download

Vale seguir esse trace antes de mexer em qualquer coisa:

1. **Entrada.** Quatro portas, todas terminando no mesmo `POST http://localhost:5000/baixar`:
   - pill sobre o iframe do Loom — `criarBotaoDownload` (`extension/content.js:775`, POST em `:798`);
   - pill do Vimeo (`content.js:910`), do Loom nativo (`content.js:976`) e do vídeo do
     Skool (`content.js:1066`, que resolve `playbackId`+token **no clique** porque o token expira);
   - popup: curso inteiro / comunidade inteira (`extension/popup.js:71` e `:128`), que
     manda a execução para o content script — ela sobrevive ao popup fechar;
   - popup: link colado (`popup.js:185`), aceitando YouTube, Loom e Vimeo.

   A pasta sai de `dadosDaAulaAtual()` (caminho completo com módulo) e, como reserva,
   de `obterDadosDaPagina()` (`content.js:15`), que parseia o `document.title` do Skool
   pelo ponto médio `·` para separar comunidade / curso / aula.

2. `server/routes.py:278` `rota_receber_pedido` — anexa um dict em `DASHBOARD_DATA` e
   responde `200` **imediatamente**, sem esperar o download. Aceita
   `{url, folder, filename, desc, resources, referer, anexos}` (todos além dos três
   primeiros são opcionais). `url` vazia é caso válido: aula só de texto.

3. `server/routes.py:47` — `ThreadPoolExecutor(max_workers=_SIMULTANEOS)` (padrão 4)
   executa `worker_download` (`routes.py:105`) em background; o resto fica na fila.

4. `worker_download`, na ordem em que as coisas acontecem:
   - resolve o nome quando o pedido veio sem ele, roteando por origem (`routes.py:124-136`);
   - YouTube **de link colado** ganha subpasta de canal (`routes.py:153`) — e **só**
     nesse caso; ver o comentário longo ali, é uma regressão já vivida;
   - dá à aula uma **pasta própria, sempre** — com 1 arquivo ou com 5. O lugar é função
     da **identidade** da aula; o conteúdo só decide QUAIS arquivos existem, nunca ONDE
     ficam. Até 12/08/2026 a pasta só nascia a partir de 2 artefatos, o que amarrava o
     caminho ao conteúdo do pedido: com `desc` a aula ganhava pasta, sem `desc` o arquivo
     ficava solto. Medido no uso real: o "já baixei?" procurava o `.mp4` num caminho que a
     própria regra tinha mudado, e um curso inteiro foi rebaixado com os vídeos soltos ao
     lado das pastas antigas. `_adotar_arquivos_soltos` (`routes.py:66`) recolhe o que já
     havia sido baixado no layout antigo, para não rebaixar;
   - grava o `.md` (`routes.py:195`) e baixa os **anexos** (`routes.py:208`) **antes** do
     vídeo — em curso onde o anexo é o produto, ele não pode depender do vídeo dar certo;
   - roteia o vídeo (`routes.py:231-265`).

5. **Caminho Loom (HLS próprio):** `services/utils.py:143` `extrair_metadados` lê o
   `window.__APOLLO_STATE__` da página de embed (estrutura, não regex — ver o comentário
   em `utils.py:42-50`; o regex sobrevive só como último recurso em `utils.py:131`).
   Depois `services/downloader.py:207` `processar_download`:
   - pula tudo se o `.mp4` final já existir com mais de 1 MB (`downloader.py:224`);
   - baixa o master com `_baixar_texto` (`downloader.py:179`) — com timeout e retry;
   - parseia o master linha a linha (`_parsear_master`, `downloader.py:62`), sem regex;
   - escolhe o stream de maior `BANDWIDTH` (`downloader.py:251`);
   - resolve vídeo **e** áudio como duas playlists separadas (`downloader.py:278-279`);
   - baixa os segmentos com 12 workers paralelos (`downloader.py:298`);
   - conta quantos segmentos falharam e avisa (`downloader.py:302-306`);
   - grava `master.m3u8` + as playlists locais em `hls-temp/` para o FFmpeg ler depois.

6. `services/converter.py:7` `converter_final` — FFmpeg com `-c copy` (sem re-encode)
   gravando em `temp_convertido.mp4` dentro da pasta temp, depois `shutil.move` para o
   destino final. O nome curto na temp é proposital: evita estourar o limite de caminho
   do Windows.

7. `services/utils.py:31` `limpar_pasta` — apaga `hls-temp/`.

**Caminho yt-dlp (YouTube / Vimeo / Skool):** não passa por 5-7. `baixar_com_ytdlp`
(`services/ytdlp.py:108`) grava direto o `.mp4` final, com nome temporário
`._yt_<uuid>` + rename (blindagem contra `%` no título e contra colisão entre
downloads simultâneos). O vídeo do Skool ainda passa por `_diagnosticar`
(`services/skool.py:55`) antes, para distinguir "token expirado" de erro genérico.

## Convenções

- **Código em português.** Funções, variáveis e comentários (`processar_download`,
  `limpar_nome_arquivo`, `encerrar`). Manter — não traduzir para inglês.
- **Importar de `services`, não de `services.downloader`.** `services/__init__.py`
  reexporta a API pública inteira.
- **Caminhos moram em `services/caminhos.py`.** `PASTA_OUTPUT` (`caminhos.py:18`) é
  absoluto, calculado subindo dois níveis a partir do arquivo; `PASTA_TEMP_RAIZ`
  (`caminhos.py:22`) é `"hls-temp"`, **relativo ao cwd** — por isso o servidor precisa
  rodar de `loom-downloader-tool/`. O cálculo já foi duplicado em `downloader.py` e
  `converter.py`; **não duplique de novo** — importe de `.caminhos`.
- **Comentário explica o porquê, não o quê.** O padrão da casa é registrar a medição e
  a regressão que motivaram a decisão (veja `services/skool.py:1-23` ou
  `routes.py:142-152`). Ao mexer, preserve esses blocos; eles são a memória do projeto.

### Reutilizar antes de criar

- `limpar_nome_arquivo` (`services/utils.py:15`) — para qualquer nome de arquivo ou
  pasta. Faz `html.unescape` e remove `< > : " / \ | ? *`.
- `HEADERS` (`services/utils.py:9`) — em **toda** requisição ao Loom. O `Referer`/`Origin`
  são necessários para não levar bloqueio.
- `limpar_pasta` (`services/utils.py:31`) — remoção recursiva tolerante a erro.
- `_baixar_texto` / `_baixar_segmento` (`services/downloader.py:179` e `:126`) — **toda**
  requisição nova no caminho HLS passa por uma delas. Elas carregam a política de
  timeout + retry; um `requests.get` cru volta a ter o bug que elas resolvem.
- `baixar_com_ytdlp` (`services/ytdlp.py:108`) — origem nova que o yt-dlp suporte não
  precisa de motor novo, só de um wrapper fino (`youtube.py`/`vimeo.py`/`skool.py` são
  isso, ~30 linhas cada).
- `montar_markdown` / `salvar_aula_md` (`services/texto.py:141` e `:168`) — para
  qualquer `.md` de aula. A regra de "tem texto?" mora lá; não replique.
- `registrar_erro` (`services/registro.py`) — **todo** caminho novo que marque uma aula
  como erro passa por `_marcar_erro` (`routes.py`), que guarda o motivo no item **e** em
  `logs/erros.log`. Um `print` solto some no repaint do dashboard em ~250ms; foi assim
  que um erro real ficou irrecuperável em 12/08/2026.
- `corpoDoPedido` (`extension/content.js`) — os **cinco** POSTs da extensão montam o
  corpo aqui. Campo novo entra num lugar e vale para os cinco.
- `pacoteDaAula` (`extension/content.js`) — pasta, nome e texto de uma aula. Os três
  botões (comunidade, curso e pill) passam por ela; é o que garante que a mesma aula
  caia sempre no mesmo caminho.

### Estado compartilhado

`DASHBOARD_DATA` (`server/dashboard.py:15`) é uma lista global mutada pelas threads de
download e lida 4×/s pela thread do Rich (`_loop_visual`, `dashboard.py:396`).
**Não há lock.** Apenas anexe itens ou mute campos de um dict existente; nunca reordene
nem remova elementos com o dashboard rodando. A thread de desenho se protege tirando um
snapshot por quadro (`_instantaneo`, `dashboard.py:26`) — mantenha isso.

O dashboard também **ocupa a tela inteira** (`Live(..., screen=True)`, `dashboard.py:405`)
e repinta 4×/s. Consequência prática: qualquer `print()` vindo de uma thread de download
aparece por um quadro e some no repaint. O `ytdlp.py` já contorna isso silenciando o
yt-dlp (`_LogadorSilencioso`, `ytdlp.py:28`), mas os avisos do `downloader.py` continuam
saindo por `print` — ver Limitações.

## Limitações conhecidas

Documentadas de propósito — não são bugs "para consertar de passagem":

- **Segmento que falha vira buraco, mas não vira erro.** Desde `db40b47`, `_baixar_segmento`
  (`services/downloader.py:126`) tenta `TENTATIVAS_POR_SEGMENTO = 3` vezes com backoff,
  apaga o arquivo parcial ao desistir e devolve `False`; `processar_download` conta as
  falhas e imprime um aviso (`downloader.py:302-306`). **O que ainda não acontece:**
  `processar_download` devolve `True` mesmo assim, o FFmpeg converte o vídeo furado e o
  dashboard marca a aula como **sucesso**. E o aviso sai por `print`, que o dashboard
  repinta por cima (ver Estado compartilhado). Ou seja: a falha deixou de ser
  *silenciosa no código*, mas ainda é *invisível na tela*.
- ~~**Retry por HTTP != 200 não espera.**~~ **Corrigido em 11/08/2026.** O `time.sleep`
  do backoff estava dentro do `except`, então um status ruim caía num `continue` e
  re-tentava na hora — três marteladas instantâneas justamente em cima de um HTTP 429,
  que é o servidor pedindo calma. Hoje o backoff está **fora** do `except`
  (`downloader.py:159-166`) e vale para os dois caminhos, igual ao `_baixar_texto`.
- **Limiar de 1 MB.** A checagem de "já existe" aceita qualquer `.mp4` acima de 1 MB como
  completo, em **três** lugares que precisam concordar: `downloader.py:224`,
  `converter.py:28` e `ytdlp.py:129`. Um arquivo truncado maior que isso nunca é
  rebaixado. (Anexos têm limiar próprio, `_ANEXO_MINIMO = 64` bytes, `skool.py:89`.)
- **Sem cancelamento.** Depois de submetido ao executor, um download só para matando o
  processo. `Ctrl+C` → `encerrar()` (`app.py:57`), que limpa a temp e chama `os._exit(0)`;
  há handler de `SIGINT`/`SIGTERM` (`app.py:78-79`) **e** um `except KeyboardInterrupt`
  em volta do `app.run()` (`app.py:114`), porque no Windows o Ctrl+C nem sempre chega
  como sinal.
- **Token do Skool expira (~24h).** A extensão resolve `playbackId`+`playbackToken` no
  enfileiramento; uma fila muito longa pode alcançar a expiração. `_diagnosticar`
  (`skool.py:55`) detecta (403/400) e diz o que fazer — reenfileirar o curso, já que o
  que baixou é pulado. Mas não há renovação automática: o servidor não tem sessão do Skool.

## Scripts na raiz de `loom-downloader-tool/`

Ferramentas de manutenção, fora do servidor. **Os três primeiros simulam por padrão** e
só agem com `--executar`:

- `migrar_layout.py` — reorganiza a `output/` para o layout de pasta por aula (4.0).
  Idempotente: reconhece pasta que já é de aula e não cria `Aula X/Aula X/`.
- `reparar_pastas_canal.py` — remove as pastas de canal do YouTube que se infiltraram
  na árvore de cursos até a 4.0. Não adivinha: compara com a estrutura real do Skool,
  hardcoded em `ESTRUTURA` a partir de uma medição na API (`reparar_pastas_canal.py:24`).
- `bench_concorrencia.py` — mede o tempo real por nível de concorrência baixando as
  mesmas aulas em `output/_BENCH`. Foi o que produziu o padrão 4.

`output/_BENCH` e `output/_DUPLICADOS` são **pastas de serviço**, ignoradas pelos scripts
de migração (`migrar_layout.py:30`). Não trate como biblioteca.

## Testes

```bash
python -m pip install -r requirements-dev.txt
python -m pytest            # rápido, fixtures congeladas, sem internet
python -m pytest -m rede    # bate no Loom de verdade
```

`tests/` cobre extração, nomes, parser de playlist, texto, worker, youtube e vimeo.
Um teste `-m rede` falhando **não é bug do código** — é o Loom tendo mudado a página;
atualize a extração junto com a fixture `tests/fixtures/loom_embed.html`.

## Não commitar

`output/` guarda os vídeos baixados (**917 arquivos, ~46 GB** em 11/08/2026) e já está no
`.gitignore`, junto com `hls-temp/`, `venv/`, `__pycache__/` e `*.stackdump`. Confira
antes de qualquer `git add -A`.
