# AGENTS.md

> Versão deste arquivo para o opencode do `CLAUDE.md`. **Os dois contam a mesma
> verdade sobre o código: mexeu num, mexa no outro.** O `CLAUDE.md` é o mais
> narrativo (explica o porquê das decisões); este é a ficha técnica.
>
> Fatos e números de linha conferidos em 11/08/2026, branch `Dev`.

## Estrutura do repositório

Dois sub-projetos independentes (cada um com seu próprio `.git`):

- **`hsl-lab/`** — Full-stack: servidor Flask em Python + extensão Chrome. O projeto principal.
- **`loom-dl-extension/`** — Extensão Chrome standalone (sem servidor, conversão no
  navegador via mux.js). **Não é legado** — resolve o mesmo problema de forma portátil.

Sem git na raiz, sem monorepo, sem config compartilhada.

## O que o programa faz

**Sifão v4.0** (`server/dashboard.py:293` e `:297`; a extensão carrega a mesma versão em
`extension/manifest.json`). Baixa aulas de comunidades do **Skool** — seja qual for onde
o vídeo mora — mais vídeos avulsos. Uma aula pode render **três coisas**: o `.mp4`, um
`.md` com o texto da aula e os **arquivos anexos**.

Cinco entradas, quatro motores:

| Origem | Detecção | Motor |
|---|---|---|
| Loom (embed no Skool ou `loom.com/share`) | fallback (nenhuma das outras) | HLS próprio (`services/downloader.py`) |
| YouTube | `eh_url_youtube` (`services/youtube.py:9`) | yt-dlp |
| Vimeo (inclusive privado do Skool) | `eh_url_vimeo` (`services/vimeo.py:13`) | yt-dlp + `Referer` |
| Vídeo hospedado no Skool (Mux white-label) | `eh_url_skool_video` (`services/skool.py:40`) | yt-dlp |
| Vídeo em **post fixado** (`videoIds`, plural) | `resolverVideoDePostFixado` (`extension/content.js:411`) | yt-dlp (mesma URL do Mux) |
| Aula só de texto (`url` vazia) | — | grava só o `.md` |

O post fixado é resolvido **na extensão**, não no servidor: a aula não tem
`videoLink` nem `videoId`, e o vídeo mora em `pinnedPosts[].post.metadata.videoIds`.
MEDIDO em 12/08/2026: **52 das 280 aulas** da ai-makers, todas perdidas em silêncio
até então. Ver `loom-downloader-tool/plan/feito/video-em-post-fixado.md (índice de tudo em `plan/README.md`)`.

## Servidor Python

### Ponto de entrada

```
python loom-downloader-tool/server/app.py
```

Flask na **porta 5000**. Exige **FFmpeg no PATH** (`verificar_ffmpeg`, `app.py:26-36`,
faz `sys.exit(1)` se faltar). Rodar **de dentro de `loom-downloader-tool/`**: `app.py:10-12`
importa `dashboard`, `services` e `routes` como módulos top-level, e `PASTA_TEMP_RAIZ` é
relativo ao cwd.

### Instalação

```bash
cd loom-downloader-tool
.\setup.ps1        # Windows   — verifica Python/FFmpeg, cria venv, instala
./setup.sh         # Linux/macOS
```

Os scripts são idempotentes e nunca apagam um `venv` existente. Manualmente:
`python -m venv venv` + `pip install -r requirements.txt`.

Dependências (`requirements.txt`, sem versões fixadas exceto uma): `flask`, `flask-cors`,
`requests`, `rich`, `yt-dlp>=2026.7.4`. Desenvolvimento (`requirements-dev.txt`): `pytest`.

### Concorrência

```bash
SIFAO_DOWNLOADS_SIMULTANEOS=6 python server/app.py     # padrão: 4
```

`_SIMULTANEOS` (`routes.py:42-45`) alimenta o `ThreadPoolExecutor` (`routes.py:47`).
**O padrão 4 foi medido, não escolhido por intuição** — 19,8% mais rápido que 1, 2,5%
mais rápido que 8 (que ainda travou uma rodada). Metodologia, ruído da máquina e
conclusões refutadas em `loom-downloader-tool/plan/feito/benchmark-concorrencia.md`.
Paralelismo de **segmento** são 12 workers por aula (`downloader.py:298`) — as conexões
reais são `nível × 12`.

### Particularidades que quebram se mexidas

- `use_reloader=False` no `app.run()` (`app.py:113`) — **nunca remover**: duplica a
  thread do dashboard.
- `porta_ocupada()` (`app.py:39`) recusa subir um segundo servidor. Sem isso você fica
  com o processo **antigo** (código velho) atendendo os cliques achando que reiniciou.
- `DASHBOARD_DATA` (`dashboard.py:15`) é uma lista global mutada pelas threads de
  download e lida 4×/s pela thread do Rich (`_loop_visual`, `dashboard.py:396`).
  **Não há lock.** Só anexe itens ou mute campos de um dict existente; nunca reordene nem
  remova elementos. A thread de desenho tira um snapshot por quadro (`_instantaneo`,
  `dashboard.py:26`) — mantenha. Não introduza async nem multiprocessing aqui.
- O dashboard ocupa a **tela inteira** (`Live(..., screen=True)`, `dashboard.py:405`).
  Qualquer `print()` de thread de download aparece por um quadro e some no repaint. Por
  isso o yt-dlp é silenciado (`_LogadorSilencioso`, `ytdlp.py:28`).
- **Caminhos moram em `services/caminhos.py`**: `PASTA_OUTPUT` (`:18`, absoluto) e
  `PASTA_TEMP_RAIZ` (`:22`, `"hls-temp"`, relativo ao cwd). O cálculo já esteve duplicado
  em `downloader.py` e `converter.py` — **não duplique de novo**, importe de `.caminhos`.
- **Importe de `services`, não de `services.downloader`** — `services/__init__.py`
  reexporta a API pública inteira.
- Temporários em `hls-temp/`, limpos na subida (`app.py:102`) e no encerramento
  (`encerrar()`, `app.py:57`, com handlers de SIGINT/SIGTERM em `:78-79` **e**
  `except KeyboardInterrupt` em `:114` — no Windows o Ctrl+C nem sempre vira sinal).
- **Layout da saída (mudou na 4.0):** `output/<Comunidade>/<Curso>/<Módulo>/`, e a aula
  que gera **2+ arquivos** ganha pasta própria com o nome dela (`routes.py:161`); com um
  arquivo só, ele fica solto. `_adotar_arquivos_soltos` (`routes.py:66`) recolhe o que
  foi baixado no layout antigo, para não rebaixar.
- **Dedup:** pula se o `.mp4` final existe e passa de 1 MB — em **três** lugares que
  precisam concordar: `downloader.py:224`, `converter.py:28`, `ytdlp.py:129`.
- Subpasta de canal do YouTube (`output/YouTube/<Canal>/`) vale **só para link colado**
  (`routes.py:153`). Aula do Skool cujo vídeo mora no YouTube **não** ganha esse nível —
  isso foi uma regressão real, que tirava aulas da sequência do módulo.

### Ordem de execução do worker

`worker_download` (`routes.py:105`) grava **texto e anexos antes do vídeo**
(`routes.py:195` e `:208`). Não é detalhe: em curso onde o anexo é o produto, ele não
pode depender de o vídeo dar certo.

### Testes

```bash
python -m pytest            # padrão: fixtures congeladas, sem internet
python -m pytest -m rede    # bate no Loom de verdade
```

Existem: `pytest.ini` (que exclui `-m rede` do padrão), `requirements-dev.txt` e 9
arquivos em `tests/` (`conftest.py` + 8 `test_*.py`: extração, nomes, playlist, texto,
worker, youtube, vimeo, smoke ao vivo), mais fixtures em `tests/fixtures/`.
Não há linter nem type checker configurados. **Teste `-m rede` falhando não é bug do
código** — é o Loom tendo mudado a página; atualize a extração junto com a fixture.

### Mapa de arquivos

| Arquivo | Papel |
|---|---|
| `server/app.py` | App Flask, checagem de FFmpeg, guarda de porta, handlers de sinal, entrypoint |
| `server/routes.py` | `POST /baixar`, roteamento por origem, pasta-por-aula, orquestração do worker |
| `server/dashboard.py` | UI do terminal (Rich), `DASHBOARD_DATA`, ETA pelo ritmo observado |
| `server/services/__init__.py` | API pública reexportada — importe daqui |
| `server/services/caminhos.py` | `PASTA_OUTPUT` e `PASTA_TEMP_RAIZ`, definição única |
| `server/services/utils.py` | `HEADERS`, `limpar_nome_arquivo`, `limpar_pasta`, extração via `__APOLLO_STATE__` |
| `server/services/downloader.py` | Parser HLS estrutural, download de segmentos com timeout e retry |
| `server/services/converter.py` | FFmpeg (TS→MP4, `-c copy`), grava com nome curto na temp e move |
| `server/services/ytdlp.py` | Engine yt-dlp compartilhada (formato, progresso, rename atômico) |
| `server/services/youtube.py` | Detecção de URL + wrappers finos sobre o ytdlp |
| `server/services/vimeo.py` | Idem, normalizando para `player.vimeo.com` + `Referer` |
| `server/services/skool.py` | Vídeo do Skool (Mux) e **download dos anexos** da aula |
| `server/services/texto.py` | Rich-text `[v2]` do Skool → Markdown (`.md` da aula) |

Scripts de manutenção na raiz de `loom-downloader-tool/` — **simulam por padrão**, só
agem com `--executar`: `migrar_layout.py` (layout de pasta por aula, idempotente),
`reparar_pastas_canal.py` (remove pastas de canal do YouTube infiltradas na árvore),
`bench_concorrencia.py` (mede tempo por nível, escreve em `output/_BENCH`).
`output/_BENCH` e `output/_DUPLICADOS` são pastas de serviço, fora da biblioteca.

## Extensão Chrome (embutida)

Em `loom-downloader-tool/extension/`. Manifest V3. Fala com o servidor Flask local
(**não** usa mux.js). Content scripts rodam em `skool.com`, `loom.com` (`content.js`) e
`youtube.com` (`youtube.js`); `host_permissions` inclui `http://localhost/*`.

Todos os caminhos terminam no mesmo `POST http://localhost:5000/baixar` com
`{url, folder, filename[, desc, resources, referer, anexos]}`:

- pill sobre o iframe do Loom — `criarBotaoDownload` (`content.js:775`);
- pill do Vimeo (`content.js:910`), do Loom nativo (`content.js:976`) e do vídeo do Skool
  (`content.js:1066`, que resolve `playbackId`+token **no clique**, porque o token expira);
- popup: curso inteiro (`popup.js:71`) e comunidade inteira com confirmação em dois passos
  (`popup.js:128`) — a execução roda no content script e sobrevive ao popup fechar, mas
  não à aba fechar;
- popup: link colado (`popup.js:185`), aceitando YouTube, Loom e Vimeo.

A árvore do curso sai do `__NEXT_DATA__`/`_next/data` do Skool, não de navegar aula a
aula. Buscar um curso por slug exige **seguir o `__N_REDIRECT`** para pegar o `md`.

## Extensão standalone (repo irmão)

Em `../loom-dl-extension/`. Manifest V3. Usa `lib/mux.min.js` para transmuxar TS→MP4 no
próprio navegador — sem servidor. Carregue como "sem compactação" em `chrome://extensions`.

## Limitações conhecidas

Documentadas de propósito — não são bugs "para consertar de passagem":

- **Segmento perdido não vira erro.** `_baixar_segmento` (`downloader.py:126`) tenta 3×
  com backoff, apaga o parcial ao desistir e devolve `False`; `processar_download` conta
  e avisa (`:302-306`). Mas devolve `True` mesmo assim: o FFmpeg converte o vídeo furado
  e o dashboard marca **sucesso** — e o aviso é repintado pelo painel.
- **Limiar de 1 MB.** Um `.mp4` truncado acima de 1 MB conta como completo e nunca é
  rebaixado. (Anexo tem limiar próprio: `_ANEXO_MINIMO = 64` bytes, `skool.py:89`.)
- **Sem cancelamento.** Depois de submetido ao executor, um download só para matando o
  processo.
- **Token do Skool expira (~24h).** `_diagnosticar` (`skool.py:55`) detecta 403/400 e
  manda reenfileirar o curso (o que já baixou é pulado), mas não renova sozinho — o
  servidor não tem sessão do Skool.
- **Curso sem acesso não expõe vídeo.** O Skool devolve a estrutura e remove os links no
  servidor; esses cursos são pulados e reportados no popup.

## Não commitar

`output/` guarda os vídeos baixados (**917 arquivos, ~46 GB** em 11/08/2026) e está no
`.gitignore`, junto com `hls-temp/`, `venv/`, `__pycache__/` e `*.stackdump`. Confira
antes de qualquer `git add -A`.

## Idioma

**Código e documentação em português.** Funções, variáveis, comentários e UI
(`processar_download`, `limpar_nome_arquivo`, `encerrar`). Não traduzir para inglês.
Comentário aqui explica **o porquê**, não o quê: o padrão da casa é registrar a medição
e a regressão que motivaram a decisão (veja `services/skool.py:1-23` ou
`routes.py:142-152`). Ao mexer, preserve esses blocos — são a memória do projeto.
