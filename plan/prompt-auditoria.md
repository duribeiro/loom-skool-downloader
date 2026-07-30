# Prompt — Auditoria e conserto do loom-downloader

> Salvo em 2026-07-23. Colar no Fable (opencode) ou no Claude Code.
> Escopo desta rodada: **validar e consertar**. Testes automatizados ficam para depois.

---

## Tarefa: fazer o loom-downloader voltar a funcionar

Repo: `E:\CURSOS\Programação\Projetos\loom-downloader\hsl-lab`
Branch: `Dev`. Leia `CLAUDE.md` antes de tocar em qualquer coisa — ele documenta o
trace completo de um download e quais limitações são propositais.

### Contexto já medido (confie, não re-verifique)

- Python 3.14.2, FFmpeg 8.1.2 no PATH, `venv/` na raiz com flask 3.1.3 / flask-cors /
  requests / rich instalados.
- O projeto **não tem nenhum teste automatizado**. Não crie testes nesta rodada.
- Último download bem-sucedido: dez/2025 (ver `loom-downloader-tool/output/`).
- Rodar **sempre** a partir de `loom-downloader-tool/`, nunca da raiz do repo.

### Alvo de teste

- **ID do vídeo:** `7a0abb7d8ae14ab480f963cc2f49ec67`
- **URL de entrada da ferramenta:** `https://www.loom.com/embed/7a0abb7d8ae14ab480f963cc2f49ec67`
- **Controle de baixo nível:** existe uma URL de segmento `.ts` assinada, válida até
  **25/07/2026** (CloudFront `DateLessThan: 1784940326`). Serve para provar que o CDN
  ainda entrega bytes, mas **expira** — não usar como fixture permanente.
- O usuário tem uma página do Skool **logada** e pode inspecionar via DevTools, e pode
  conectar o agente ao navegador (Claude in Chrome).

### Regra crítica de validação

Este projeto engole exceções de propósito: `_baixar_segmento`
(`services/downloader.py:40-42`) e os `except:` nus em `downloader.py:76` e `:129`.
Portanto **"não deu erro" não é prova de que funcionou**.

Toda validação tem que olhar o **artefato**, nunca o exit code:
- tamanho do `.mp4` final;
- `ffprobe` → duração > 0, stream de vídeo **e** stream de áudio presentes;
- nº de segmentos baixados vs. nº de segmentos listados na playlist.

Cuidado com o **limiar de 1 MB** (`downloader.py:63`): a checagem de "já existe" aceita
qualquer `.mp4` acima de 1 MB como completo. Um arquivo truncado de rodada anterior
nunca é rebaixado e vai te dar falso verde. Apague o alvo antes de cada teste.

---

## Execução em camadas — pare e reporte na primeira que quebrar

### Camada 0 — Smoke

Suba o servidor. Confirme que fica de pé e que `POST localhost:5000/baixar` com um JSON
dummy responde `200`.
**Prova:** o corpo literal da resposta HTTP, colado no relatório.

### Camada 1 — O elo suspeito: página → `.m3u8`

`extrair_metadados` (`services/utils.py:41`) acha a URL `.m3u8` por **regex no HTML** da
página de embed do Loom. Se o Loom mudou o HTML, isso quebrou silenciosamente.

1. Baixe o HTML de `https://www.loom.com/embed/7a0abb7d8ae14ab480f963cc2f49ec67`
   usando `HEADERS` (`services/utils.py:8`) — sem o `Referer`/`Origin` você leva bloqueio
   e vai concluir errado que o código quebrou.
2. Salve esse HTML em disco para inspeção.
3. Rode o regex **atual** contra ele. Casa? **Cole o resultado literal.**
4. Se não casar: descubra o formato novo e conserte o regex. Se o Loom passou a montar a
   URL via JS/XHR (e não mais no HTML servido), diga isso explicitamente — a correção é
   outra e precisa de decisão do usuário, não invente um workaround sozinho.

### Camada 2 — Download ponta a ponta

Com o `.m3u8` em mãos, rode o fluxo completo: master → escolha do maior `BANDWIDTH`
(`downloader.py:92`) → playlists de vídeo e áudio (`downloader.py:133-134`) → segmentos
→ FFmpeg `-c copy` → `.mp4` em `output/`.

**Prova:** saída literal do `ffprobe` sobre o `.mp4` final, mostrando duração e os dois
streams.

### Camada 3 — Extensão

Não tente automatizar sozinho: depende do login do usuário no Skool.
Revise `extension/content.js` e `manifest.json` procurando o que quebraria hoje:
- versão do manifest (v2 vs v3);
- seletores de DOM do player;
- o parse do `document.title` pelo ponto médio `·` (`content.js:14`) — o Skool pode ter
  mudado o formato do título, o que quebra a organização em pastas sem quebrar o download.

Entregue um **checklist do que o usuário deve clicar** para validar, e peça a ele os
prints/DevTools de que você precisar.

---

## Restrições

- **Código em português.** Funções, variáveis e comentários. Não traduzir para inglês.
- Importar de `services`, nunca de `services.downloader`.
- `HEADERS` (`services/utils.py:8`) em **toda** requisição ao Loom.
- **Não deletar nada de `output/`** (~268 MB de vídeos já baixados).
- O cálculo de `PASTA_OUTPUT` está **duplicado** em `downloader.py:11-14` e
  `converter.py:8-11`. Mexeu num, mexa no outro.
- **Prioridade é voltar a funcionar.** Não conserte de passagem as limitações listadas no
  `CLAUDE.md` (falhas silenciosas, limiar de 1 MB, ausência de cancelamento). Anote o que
  encontrar numa lista de "depois" e proponha antes de mexer.

## Registro

Grave plano, estado, decisões e resultados em `<repo>/plan/`.

## Entrega

Relatório com: o que passou, o que quebrou (**com a saída literal**), o que foi
consertado, e o que ficou pendente. Se não conseguiu testar algo, diga explicitamente —
nunca escreva "provavelmente funciona".
