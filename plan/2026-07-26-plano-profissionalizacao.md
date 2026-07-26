# Plano — Profissionalização (dev → ferramenta pessoal open source)

**Criado:** 2026-07-26. **Decisão do usuário:** fazer **os dois** —
(A) o **híbrido** (extensão + servidor) empacotado num instalador estilo IDM, e
(B) terminar a **extensão pura** (`../loom-dl-extension`, o "1.0") com mux.js.

Alvo: **ferramenta pessoal polida**, distribuída **open source no GitHub**. Uso legítimo
(cursos pagos; blindagem contra plataforma que some). Como terceiros usam não é escopo nosso.

Necessidades declaradas: **YouTube** (além do Loom), **jornada ultra-fácil** (não é barra de
progresso — é tirar toda fricção de instalar/usar), e **qualidade profissional**.

## Premissas (assumidas — corrigir se errado)

1. **Windows primeiro.** Mac/Linux ficam para depois (usuário está em Win11; modelo IDM é Win).
2. **Loom continua no caminho próprio** já testado do `hsl-lab`; **yt-dlp entra só para YouTube**
   (não reescrever o que funciona). yt-dlp poderá, mais tarde, endurecer tudo — fora de escopo agora.
3. **Granularidade honesta:** a Fase imediata (A1) vai em microtarefas completas (comando/rollback).
   As fases seguintes ficam em objetivos + lista de tarefas e são **detalhadas quando chegarmos**
   — escrever comandos exatos de PyInstaller/Inno Setup agora seria chutar sem medir (viola
   "medir, não afirmar"). Cada uma exige um spike curto antes.

## Sequência e porquê

**Track A primeiro.** O híbrido já baixa Loom 100%; falta só YouTube + empacotar. Isso entrega
a necessidade central (backup dos cursos, Loom+YouTube) **mais rápido** e é o caminho robusto.
**Track B depois** — a versão portátil "instalação zero", que reusa a lógica já endurecida no A.

Reaproveitamento: a extração HLS correta (áudio separado, maior BANDWIDTH, parser linha a linha)
vive em `server/services/downloader.py` — é a **fonte de verdade** para portar ao mux.js no B.

---

# TRACK A — Híbrido profissional (instalador estilo IDM)

## Fase A1 — YouTube via yt-dlp  ← primeira a executar

**Por quê:** é a necessidade nova mais bem delimitada e não depende do empacotamento.

### Tarefa A1.1 — Provar o yt-dlp num vídeo do YouTube (spike, sem integrar)

**Objetivo:** medir que yt-dlp + ffmpeg baixam um YouTube em `.mp4` (vídeo+áudio) antes de
escrever qualquer integração.
**Arquivo/Local Alvo:** nenhum código; rodar no venv de `loom-downloader-tool/`.
**Comando Exato:**
```bash
cd "E:/CURSOS/Programação/Projetos/loom-downloader/hsl-lab/loom-downloader-tool"
./venv/Scripts/python.exe -m pip install yt-dlp
./venv/Scripts/python.exe -m yt_dlp -f "bv*+ba/b" -o "output/_spike_yt/%(title)s.%(ext)s" <URL_YOUTUBE_DE_TESTE>
```
**Quando Executar:** primeiro passo do Track A.
**Como Validar:** `ffprobe` no arquivo gerado mostra stream de vídeo **e** de áudio.
**Rollback:** apagar `output/_spike_yt/`; `pip uninstall yt-dlp` se não seguir.
**Risco:** Baixo (read-only contra o YouTube).
**Critério para Avançar:** `.mp4` com vídeo+áudio confirmado por ffprobe.

Status:
- [ ] feito
- [ ] bloqueado

### Tarefa A1.2 — `requirements`: fixar yt-dlp

**Objetivo:** yt-dlp vira dependência declarada.
**Arquivo/Local Alvo:** `loom-downloader-tool/requirements.txt`
**O quê:** adicionar `yt-dlp` (com versão mínima medida no A1.1).
**Como Validar:** `pip install -r requirements.txt` num venv limpo instala yt-dlp.
**Rollback:** `git checkout requirements.txt`.
**Risco:** Baixo.

Status:
- [ ] feito

### Tarefa A1.3 — Serviço `baixar_youtube` no servidor

**Objetivo:** um caminho de download paralelo ao do Loom, para links de YouTube.
**Arquivo/Local Alvo:** novo `server/services/youtube.py`; reexportar em `services/__init__.py`.
**O quê:** função `baixar_youtube(url, pasta_destino, nome, callback)` que chama yt-dlp via API
Python (`yt_dlp.YoutubeDL`), grava direto no destino final (yt-dlp já faz mux com ffmpeg),
reusa `limpar_nome_arquivo` e o mesmo `PASTA_OUTPUT` de `services/caminhos.py`. Falhas
**visíveis** (sem `except:` nu), no padrão da Fase 3.
**Como Validar:** teste unitário com yt-dlp mockado (sem rede) + 1 smoke `-m rede`.
**Rollback:** `git rm server/services/youtube.py` e reverter o `__init__`.
**Risco:** Médio (novo caminho de execução).

Status:
- [ ] feito

### Tarefa A1.4 — Roteamento no worker + no crawler

**Objetivo:** o mesmo botão/fila decide Loom vs YouTube pela URL.
**Arquivo/Local Alvo:** `server/routes.py` (`worker_download`) e `extension/content.js`.
**O quê:** em `worker_download`, se a `url` for YouTube → `baixar_youtube`; senão o caminho
Loom atual. No `content.js`, o crawler hoje só marca `_temVideo` para `loom.com` — estender o
regex para aceitar `youtube.com`/`youtu.be` e mandar a URL (o roteamento fica no servidor).
**Como Validar:** enfileirar uma aula Loom e uma YouTube; ambas geram `.mp4` correto.
**Rollback:** `git checkout` dos dois arquivos.
**Risco:** Médio.

Status:
- [ ] feito

## Fase A2 — Matar dependências externas

**Objetivo:** o usuário nunca instala Python nem põe ffmpeg no PATH.

- **A2.1** Embutir `ffmpeg.exe` (build enxuto: h264/aac/mp4/hls) dentro do app; `verificar_ffmpeg()`
  passa a procurar o binário local antes do PATH. Mata a causa nº 1 de "servidor não sobe".
- **A2.2** Congelar o servidor com PyInstaller (spike: ver se `dashboard`/rich/flask congelam limpo;
  o import top-level de `server/` precisa de atenção). Embutir yt-dlp e ffmpeg no bundle.
- **A2.3** Smoke do executável congelado num Windows limpo (VM/pasta sem Python): sobe, recebe POST, baixa.

## Fase A3 — Instalador + auto-start

**Objetivo:** instalar em 1 clique; servidor sobe sozinho.

- **A3.1** Instalador **Inno Setup**: instala o app, cria atalho, registra auto-start no login.
- **A3.2** Extensão: publicar no **Chrome Web Store** (some o "modo desenvolvedor"; instala em 1 clique)
  **OU** empacotar `.crx` + instrução — DECISÃO PENDENTE D-A1 (fee/review do Web Store).
- **A3.3** Porta/erro: se 5000 ocupada, mensagem clara (já existe da Fase 3.6) — validar no fluxo do app.

## Fase A4 — Jornada ultra-fácil

**Objetivo:** "instalei, e agora?" deixa de existir.

- **A4.1** Pós-instalação abre uma página de boas-vindas: 1) extensão já instalada, 2) abra seu Skool,
  3) clique. Sem terminal, sem `cd`.
- **A4.2** Feedback de estado do servidor **na extensão** (online/offline), em vez de só no terminal.
- **A4.3** Bandeja do Windows (tray) com "abrir pasta de downloads" e "sair" — encerramento limpo.

---

# TRACK B — Extensão pura (terminar o 1.0)

Base: `../loom-dl-extension` (mux.js, MV3). O 1.0 tem a arquitetura certa mas está **incompleto**
— o CLAUDE.md dele lista os furos. Fonte de verdade da lógica correta: `hsl-lab`.

## Fase B1 — Extração HLS correta (o furo do áudio)

- **B1.1** Ler a trilha de **áudio** (`#EXT-X-MEDIA:TYPE=AUDIO,URI=...`), hoje ignorada — portar de
  `downloader.py:133-134`.
- **B1.2** Seleção por **maior BANDWIDTH** (não "última linha com .m3u8") — portar de `downloader.py:85-92`.
- **B1.3** Parser HLS linha a linha (respeita aspas) — portar de `downloader.py`.

## Fase B2 — Transmux correto + sem estourar RAM

- **B2.1** `initSegment` único + flush no fim (não por segmento) — o mp4 de headers duplicados que
  players recusam.
- **B2.2** Muxar **áudio+vídeo** juntos no mux.js.
- **B2.3** Não acumular o vídeo inteiro em memória: usar `chrome.downloads` com streaming
  (ou StreamSaver). Spike de viabilidade — é o maior risco técnico do Track B.

## Fase B3 — Crawler + texto no modelo da extensão

- **B3.1** Portar o crawler de curso inteiro (`coletarAulasDoCurso`) e o **fetch de texto por aula**
  (`_next/data`) já provados no `hsl-lab/content.js`.
- **B3.2** Salvar o `.md` do texto via `chrome.downloads` (blob), na mesma árvore de pastas.
- **B3.3** Organização de pastas com `chrome.downloads` (subpastas relativas ao Downloads).

## Fase B4 — Polish + segurança

- **B4.1** Trocar `alert()` por `console.error` (o alert congela automação).
- **B4.2** Preencher `style.css` (portar do `hsl-lab`).
- **B4.3** `host_permissions` restrito a loom/skool (hoje `<all_urls>`).
- **B4.4** Primeiro commit real do código-fonte (hoje só o manifest está versionado).

---

## Riscos transversais

- **Skool/Loom mudam** e quebram extração (já aconteceu — rename do `playlist.m3u8`). A rede de
  testes `-m rede` é a sentinela; manter.
- **YouTube muda** → yt-dlp precisa de update frequente. O instalador deve permitir atualizar yt-dlp
  sem reinstalar tudo (ex.: yt-dlp separado, auto-update).
- **RAM no Track B** pode inviabilizar aulas longas — por isso B2.3 é spike, não certeza.

## Decisões pendentes

- **D-A1 — Chrome Web Store?** Publicar (1 clique, mas fee US$5 + review) vs `.crx`/unpacked
  documentado. Afeta a "jornada ultra-fácil". Decidir na Fase A3.
- **D-A2 — Escopo de SO.** Só Windows agora? (assumido sim).

## Checklist final (ao término de cada Track)

Track A:
- [ ] YouTube baixa `.mp4` com áudio (ffprobe)
- [ ] Servidor congelado sobe sem Python/ffmpeg no sistema
- [ ] Instalador: 1 clique → servidor no ar → botão funciona
- [ ] `pytest` e `pytest -m rede` verdes

Track B:
- [ ] Loom baixa com **áudio** e maior qualidade
- [ ] mp4 aceito por players (sem headers duplicados)
- [ ] Aula longa não derruba o worker
- [ ] Crawler + texto funcionando na extensão pura
