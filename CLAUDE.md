# CLAUDE.md

Orientações para o Claude Code (claude.ai/code) trabalhar neste repositório.

## O que é

Baixador de aulas do Loom hospedadas dentro de comunidades do Skool. Arquitetura **híbrida**: uma extensão Chrome injeta um botão no player e dispara um pedido para um **servidor Flask local**, que baixa os fragmentos HLS (`.ts`) em paralelo, converte para `.mp4` com FFmpeg e organiza em `output/Comunidade/Curso/Aula.mp4`.

Existe um projeto irmão em `../loom-dl-extension`: uma extensão **standalone** (sem Python, sem FFmpeg) que resolve o mesmo problema de forma portátil. Este repo aqui é o mais completo — trata áudio, escolhe a maior qualidade e organiza em pastas. Nenhum dos dois é legado.

## Como rodar

```bash
pip install -r requirements.txt          # flask, flask-cors, requests, rich
cd loom-downloader-tool
python server/app.py                     # sobe em localhost:5000 + dashboard no terminal
```

Rodar **a partir de `loom-downloader-tool/`**, não da raiz do repo. `server/app.py:9-11` importa `dashboard`, `services` e `routes` como módulos top-level, então `server/` precisa estar no `sys.path` — o que o Python faz automaticamente ao executar `python server/app.py`, mas quebra se o import for reorganizado em pacote.

**FFmpeg no PATH é obrigatório.** `verificar_ffmpeg()` (`server/app.py:22-32`) faz `sys.exit(1)` se `shutil.which("ffmpeg")` retornar `None`. Um "o servidor não sobe" é quase sempre isso.

Extensão: `chrome://extensions` → Modo desenvolvedor → "Carregar sem compactação" → selecionar `loom-downloader-tool/extension`.

## Fluxo de um download

Vale seguir esse trace antes de mexer em qualquer coisa:

1. `extension/content.js:119` — botão faz `POST http://localhost:5000/baixar` com `{url, folder, filename}`. A pasta vem de `obterDadosDaPagina()` (`content.js:14`), que parseia o `document.title` do Skool procurando o ponto médio `·` para separar comunidade / curso / aula.
2. `server/routes.py:93` `rota_receber_pedido` — anexa um dict em `DASHBOARD_DATA` e responde `200` **imediatamente**, sem esperar o download.
3. `server/routes.py:24` — `ThreadPoolExecutor(max_workers=3)` executa `worker_download` (`routes.py:28`) em background. No máximo 3 aulas simultâneas; o resto fica na fila.
4. `server/services/utils.py:41` `extrair_metadados` — busca a URL `.m3u8` por regex no HTML da página de embed do Loom.
5. `server/services/downloader.py:44` `processar_download`:
   - pula tudo se o `.mp4` final já existir com mais de 1 MB (`downloader.py:63`);
   - escolhe o stream de maior `BANDWIDTH` (`downloader.py:92`);
   - resolve vídeo **e** áudio como duas playlists separadas (`downloader.py:133-134`);
   - baixa os segmentos com 12 workers paralelos (`downloader.py:156`);
   - grava `master.m3u8` + as playlists locais em `hls-temp/` para o FFmpeg ler depois.
6. `server/services/converter.py:13` `converter_final` — FFmpeg com `-c copy` (sem re-encode) gravando em `temp_convertido.mp4` dentro da pasta temp, depois `shutil.move` para o destino final. O nome curto na temp é proposital: evita estourar o limite de caminho do Windows.
7. `server/services/utils.py:30` `limpar_pasta` — apaga `hls-temp/`.

## Convenções

- **Código em português.** Funções, variáveis e comentários (`processar_download`, `limpar_nome_arquivo`, `fechar_forçado`). Manter — não traduzir para inglês.
- **Importar de `services`, não de `services.downloader`.** `services/__init__.py` reexporta a API pública e define `PASTA_TEMP_RAIZ`.
- `PASTA_TEMP_RAIZ = "hls-temp"` é **relativo ao cwd**; `PASTA_OUTPUT` é absoluto e calculado subindo três níveis a partir do arquivo. Esse cálculo está **duplicado** em `downloader.py:11-14` e `converter.py:8-11` — mexeu num, mexa no outro.

### Reutilizar antes de criar

- `limpar_nome_arquivo` (`services/utils.py:14`) — para qualquer nome de arquivo ou pasta. Faz `html.unescape` e remove `< > : " / \ | ? *`.
- `HEADERS` (`services/utils.py:8`) — em **toda** requisição ao Loom. O `Referer`/`Origin` são necessários para não levar bloqueio.
- `limpar_pasta` (`services/utils.py:30`) — remoção recursiva tolerante a erro.

### Estado compartilhado

`DASHBOARD_DATA` (`server/dashboard.py:12`) é uma lista global mutada pelas threads de download e lida 4×/s pela thread do Rich (`dashboard.py:94`). **Não há lock.** Apenas anexe itens ou mute campos de um dict existente; nunca reordene nem remova elementos com o dashboard rodando.

## Limitações conhecidas

Documentadas de propósito — não são bugs "para consertar de passagem":

- **Falhas silenciosas no download.** `_baixar_segmento` (`services/downloader.py:40-42`) e os `except:` nus em `downloader.py:76` e `:129` engolem qualquer exceção. Um segmento que falha vira um buraco no vídeo final sem nenhum aviso, e não há retry.
- **Limiar de 1 MB.** A checagem de "já existe" (`downloader.py:63`) aceita qualquer `.mp4` acima de 1 MB como completo. Um arquivo truncado maior que isso nunca é rebaixado.
- **Sem cancelamento.** Depois de submetido ao executor, um download só para matando o processo (`Ctrl+C` → `fechar_forçado` em `app.py:35`, que limpa a temp e chama `os._exit(0)`).

## Não commitar

`output/` guarda os vídeos baixados (~268 MB atualmente) e já está no `.gitignore`, junto com `hls-temp/`, `venv/` e `__pycache__/`. Confira antes de qualquer `git add -A`.
