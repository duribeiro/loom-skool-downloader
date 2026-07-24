# Plano de Refactor — 2026-07-23

**Estado (2026-07-24): Fases 1 a 4 CONCLUÍDAS.** Todas commitadas, árvore limpa,
65 testes verdes. Falta só o usuário validar o crawler clicando na extensão e o
disparo real dos downloads.

Decisões do usuário: Fase 1 = "descer" · Fase 3 = só parse estrutural (a API do
Loom devolveu 204 vazio) · Fase 4 = crawler via extensão, curso inteiro,
pastas Comunidade/Curso/Módulo/Aula, texto em Markdown.

### Linha do tempo (commits)

```
60acc93  fix   Loom renomeou playlist.m3u8 -> extração voltou a funcionar
ebabb91  refac Fase 1: estrutura reorganizada + setup.ps1
84cc97b  feat  setup.sh (Linux) + assets/ para dentro
52a2ac1  test  Fase 2: rede de segurança (43 testes, fixtures + smoke ao vivo)
a7b29c4  refac Fase 3.1/3.2: extração por estrutura (Apollo), não por regex
db40b47  refac Fase 3.3/3.4/3.5: parser HLS, falhas visíveis, PASTA_OUTPUT único
7609856  feat  Fase 3.6: recusa porta ocupada + encerramento blindado
9c2147b  docs  Fase 4: exploração e desenho do crawler
ebfa94b  feat  Fase 4: crawler de curso inteiro + captura de texto
2e8ad36  fix   Fase 4: aulas vazias viram .md placeholder
```

---

## Medições que mudam o plano

### 1. A API do Loom NÃO funciona como esperado

```
POST https://www.loom.com/api/campaigns/sessions/<ID>/transcoded-url  -> HTTP 204, 0 bytes
GET  (mesma URL)                                                      -> HTTP 403 (CloudFront)
```

`204 No Content` significa "aceito, sem corpo" — o endpoint **não devolve a URL**. Ou ele
exige CSRF/token de sessão que não temos, ou mudou de forma.

**Consequência:** a perna "API" da opção escolhida não é implementável hoje sem engenharia
reversa do front-end do Loom. Ver decisão pendente D1.

### 2. O parse estrutural funciona — e cobre mais do que o esperado

`window.__APOLLO_STATE__` está presente no HTML. Extraído **sem regex de URL**, usando
`json.JSONDecoder().raw_decode()` (acha o início, deixa o parser JSON achar o fim):

```
__APOLLO_STATE__ no offset 6949 -> 9065 bytes, 5 chaves no topo
nós com campo 'url' contendo .m3u8: 1  (exatamente um, sem ambiguidade)
  __typename : CloudfrontSignedUrlPayload
  caminho    : RegularUserVideo:<ID>.nullableRawCdnUrl({"acceptableMimes":["M3U8"],"password":null})
```

**Bônus:** o título também sai da mesma árvore — `RegularUserVideo.name` =
`"Introdução ao Programa Gang e Dinâmica de Implementação"`. Ou seja, **os dois regex de
`extrair_metadados` morrem de uma vez** (o do `<title>` e o da URL), substituídos por uma
leitura estrutural só.

16 `__typename` distintos na árvore. Ancorar em `CloudfrontSignedUrlPayload` é seguro:
aparece exatamente 1×.

### 3. O venv se RECRIA, não se move (corrigido após feedback do usuário)

Correção: a afirmação anterior ("não pode ser movido") estava errada em espírito — o
usuário tem razão de que deixar o venv fora da pasta do projeto é bagunça e deve ser
resolvido. O que muda é a **técnica**.

Medido em `hsl-lab/venv` — 31,6 MB, 2507 arquivos, caminhos absolutos em:

```
pyvenv.cfg                                     -> texto (fácil de editar)
Scripts/activate, activate.bat, activate.fish  -> texto (fácil de editar)
Scripts/{flask,pip,pip3,normalizer,idna,...}.exe -> BINÁRIOS com o caminho embutido
```

Os `.exe` são launchers do Windows com o caminho do python **dentro do binário**. Mover e
corrigir exigiria regerar cada um.

**Decisão:** um venv é artefato **derivado**, não fonte — sai inteiro de um
`pip install -r requirements.txt` em ~20 s, e é por isso que está no `.gitignore`. Então
ele é **destruído e recriado** no lugar certo. Sem patch de binário, sem risco de um venv
meio-quebrado que só falha semanas depois.

Pré-requisito: **o servidor precisa estar parado** — não dá para apagar um venv em uso.

### 4. O .gitignore não precisa mudar

Padrões sem âncora (`output/`, `venv/`, `hls-temp/`) casam em qualquer profundidade.
Mover arquivos não afeta.

---

## Decisão D1 — RESOLVIDA

**Escolha do usuário: (a)** — só o parse estrutural do Apollo. A perna "API" sai do escopo;
o endpoint devolve 204 vazio e implementá-la exigiria engenharia reversa sem garantia.
O parse estrutural já está provado e é estritamente melhor que o regex atual.

---

## Ponto de partida

Commit `60acc93` na branch `Dev` — conserto do regex + registro do diagnóstico + este plano.
Árvore de trabalho limpa. É o ponto de rollback de tudo que vier a seguir.

---

## ✅ FASE 1 — CONCLUÍDA (2026-07-23)

| Tarefa | Resultado |
|---|---|
| 1.1 Mover requirements + README | `git mv`, histórico preservado, destino estava livre |
| 1.1b Recriar venv | Antigo removido; novo em `loom-downloader-tool/venv`, 18 pacotes |
| 1.2 Verificar imports | `IMPORT OK`, `PASTA_TEMP_RAIZ` resolvendo |
| 1.3 `setup.ps1` | Idempotente (2× seguidas) + clone limpo do zero |
| 1.4 README | Setup de um comando; caminho da imagem corrigido |

### Validação do setup.ps1 em clone limpo

```
venv existe antes? False
=== 3/5  Ambiente virtual ===
  Criando venv...
  [OK] venv criado
=== 4/5  Instalando dependencias ===
  [OK] flask, flask-cors, requests, rich
venv existe depois? True

PORTA 5000 ESCUTANDO apos 1s
POST /baixar -> HTTP 200 {"mensagem":"Adicionado à fila","status":"ok"}
porta 5000 livre depois? True
```

### Estrutura resultante

```
hsl-lab/
├── assets/                  (imagens do README)
├── plan/                    (registro durável)
├── AGENTS.md, CLAUDE.md, opencode.json
└── loom-downloader-tool/
    ├── README.md            ← desceu
    ├── requirements.txt     ← desceu
    ├── setup.ps1            ← novo
    ├── venv/                ← recriado aqui
    ├── server/, extension/, output/
```

### Achados durante a execução

1. **`assets/image.png` no README quebrou ao mover.** A imagem mora na raiz do repo;
   com o README um nível abaixo, o caminho relativo deixou de resolver. Corrigido para
   `../assets/image.png` e verificado.
2. **Dois bugs meus no `setup.ps1`, pegos pelo teste:** precedência do cast `[version]`
   (aplicava ao array antes do `-join`) e `Write-Host "x" + "y"`, que o PowerShell trata
   como argumentos posicionais em vez de concatenar. Ambos só apareceram porque o script
   foi executado de verdade — revisão visual não teria pego.
3. **O venv novo tinha as dependências já satisfeitas** logo após ser criado. Não tenho
   explicação confirmada (provável cache de wheels do pip). O que **foi** verificado:
   `sys.prefix` aponta para o venv novo, `flask.__file__` está dentro dele e
   `include-system-site-packages = false`. Isolamento correto.

---

# FASE 1 — Reestruturação e setup

### Tarefa 1.1 - Mover requirements.txt e README.md

**Objetivo:** acabar com a contradição do README (manda `cd loom-downloader-tool` mas os
arquivos estão fora).
**Arquivo/Local Alvo:** `E:\...\hsl-lab\{requirements.txt,README.md}` →
`E:\...\hsl-lab\loom-downloader-tool\`
**Comando Exato:**
```bash
cd "E:/CURSOS/Programação/Projetos/loom-downloader/hsl-lab"
git mv requirements.txt loom-downloader-tool/requirements.txt
git mv README.md loom-downloader-tool/README.md
```
**Quando Executar:** primeiro passo, com a árvore de trabalho limpa.
**Como Validar:** `git status` mostra 2 renomeações; `ls loom-downloader-tool/` lista os
dois arquivos; `ls` na raiz não os lista mais.
**Rollback:** `git reset --hard HEAD` (só se não houver outra mudança não commitada).
**Risco:** Baixo — `git mv` preserva histórico.
**Critério para Avançar:** ambos os arquivos existem no novo local e o git registrou o rename.

Status:
- [ ] feito
- [ ] bloqueado

---

### Tarefa 1.1b - Recriar o venv dentro da pasta do projeto

**Objetivo:** acabar com o venv órfão na raiz. Ele é artefato derivado — recria-se, não se move.
**Arquivo/Local Alvo:** destruir `hsl-lab\venv` → criar `hsl-lab\loom-downloader-tool\venv`
**Comando Exato:**
```powershell
# 1. PARAR o servidor primeiro -- nao da para apagar um venv em uso
Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# 2. conferir que a porta ficou livre ANTES de apagar
Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue

# 3. recriar no lugar certo
cd "E:\CURSOS\Programação\Projetos\loom-downloader\hsl-lab"
Remove-Item -Recurse -Force venv
cd loom-downloader-tool
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```
**Quando Executar:** após 1.1, com o servidor parado e confirmado parado.
**Como Validar:**
`.\venv\Scripts\python.exe -c "import flask, rich, requests; print('DEPS OK')"` imprime `DEPS OK`;
`Test-Path ..\venv` retorna `False`.
**Rollback:** recriar na raiz com os mesmos comandos. O venv não está no git (é ignorado),
então não há histórico a perder — só 20 s de reinstalação.
**Risco:** **Médio.** É um `Remove-Item -Recurse -Force` numa pasta que o usuário criou.
Só executar depois de confirmar a porta livre. O `.gitignore` já cobre `venv/` em qualquer
profundidade, então o novo local não vaza para o git.
**Critério para Avançar:** `DEPS OK` a partir do venv novo e o antigo inexistente.

Status:
- [ ] feito
- [ ] bloqueado

---

### Tarefa 1.2 - Verificar que nada quebrou

**Objetivo:** provar que mover arquivos não afetou o runtime.
**Arquivo/Local Alvo:** `loom-downloader-tool/`
**Comando Exato:**
```bash
cd "E:/CURSOS/Programação/Projetos/loom-downloader/hsl-lab/loom-downloader-tool"
../venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'server'); import app; print('IMPORT OK')"
```
**Quando Executar:** logo após 1.1.
**Como Validar:** imprime `IMPORT OK` sem traceback.
**Rollback:** reverter 1.1.
**Risco:** Baixo — nenhum código referencia `requirements.txt` ou `README.md`.
**Critério para Avançar:** `IMPORT OK`.

Status:
- [ ] feito
- [ ] bloqueado

---

### Tarefa 1.3 - Criar script de setup

**Objetivo:** substituir os 5 passos manuais do README por um comando.
**Arquivo/Local Alvo:** criar `loom-downloader-tool/setup.ps1`
**O quê:** o script deve, de forma idempotente:
1. verificar Python 3.10+ e **abortar com mensagem clara** se ausente;
2. verificar `ffmpeg` no PATH e abortar com link de instalação se ausente
   (mesma checagem de `app.py:22`, mas *antes* de instalar qualquer coisa);
3. criar `venv/` **se não existir** — nunca sobrescrever um venv existente;
4. instalar `requirements.txt`;
5. imprimir as instruções de carregar a extensão no Chrome (isso não dá para automatizar)
   e o comando para subir o servidor.
**Quando Executar:** após 1.2.
**Como Validar:** rodar em um clone limpo num diretório temporário e ver o servidor subir.
Rodar 2× seguidas: a segunda não pode recriar o venv nem dar erro.
**Rollback:** `git rm loom-downloader-tool/setup.ps1`.
**Risco:** **Médio** — o passo 3 mexe com venv. Deve conter guarda explícita
`if (-not (Test-Path venv))`. Nunca `Remove-Item venv`.
**Critério para Avançar:** clone limpo sobe com um comando; rodar 2× é seguro.

Status:
- [ ] feito
- [ ] bloqueado

---

### Tarefa 1.4 - Reescrever o README

**Objetivo:** refletir a estrutura real e o setup de um comando.
**Arquivo/Local Alvo:** `loom-downloader-tool/README.md`
**O quê:** substituir a sequência de 5 passos por `.\setup.ps1`; documentar que `venv/`
mora na raiz do repo (um nível acima) e por quê; manter a instrução da extensão.
**Quando Executar:** após 1.3 estar validada.
**Como Validar:** seguir o README do zero, em outra máquina ou pasta, sem consultar mais nada.
**Rollback:** `git checkout loom-downloader-tool/README.md`.
**Risco:** Baixo.
**Critério para Avançar:** um terceiro conseguiria subir o projeto só com o README.

Status:
- [ ] feito
- [ ] bloqueado

---

## ✅ FASE 2 — CONCLUÍDA (2026-07-24)

| Tarefa | Resultado |
|---|---|
| 2.1 Fixtures | 4 arquivos reais, credenciais sanitizadas, 0 remanescentes |
| 2.2 Testes de unidade | 39 testes, verdes, sem rede |
| 2.3 Smoke ao vivo | 4 testes, verdes, `-m rede` |

### A validação que importa: mutation test

Uma suíte que não falha quando o código quebra não vale nada. Reverti o regex para a
versão quebrada e rodei:

```
FAILED tests/test_extracao.py::test_extrai_url_do_stream
FAILED tests/test_extracao.py::test_url_extraida_nao_tem_escape_de_json
FAILED tests/test_extracao.py::test_nao_exige_o_nome_literal_playlist_ponto_m3u8
FAILED tests/test_extracao.py::test_sobrevive_a_rename_do_arquivo_pelo_loom[playlist-multibitrate.m3u8]
FAILED tests/test_extracao.py::test_sobrevive_a_rename_do_arquivo_pelo_loom[playlist-v2.m3u8]
FAILED tests/test_extracao.py::test_sobrevive_a_rename_do_arquivo_pelo_loom[stream-principal.m3u8]
FAILED tests/test_extracao.py::test_sobrevive_a_rename_do_arquivo_pelo_loom[qualquer-nome-que-o-loom-inventar.m3u8]
7 failed, 32 passed, 4 deselected
```

Código restaurado via `git checkout` e suíte de volta a `39 passed`.
**A rede de segurança está comprovadamente armada** — a Fase 3 pode começar.

### Decisão sobre as fixtures

As URLs do Loom carregam `Signature`, `Policy` e `Key-Pair-Id` — credenciais de acesso ao
vídeo. Os **valores** foram substituídos por placeholders, preservando a **estrutura**, que
é o que os testes parseiam. Verificado programaticamente: 0 credenciais remanescentes.
Sem isso, publicar o repo vazaria acesso ao conteúdo.

Consistência das fixtures com a realidade: 33 segmentos de vídeo + 42 de áudio = 75,
exatamente o total medido no download real de 23/07.

### Cobertura

- `limpar_nome_arquivo` — caracteres proibidos no Windows, entidades HTML, vazios
- `extrair_metadados` — título, URL, escape de JSON, página sem stream, erro de rede
- **resiliência a rename** — 5 nomes diferentes de arquivo, incluindo o antigo
- `processar_download` — maior BANDWIDTH, vídeo + áudio, 75 segmentos, playlists gravadas,
  pulo por arquivo existente, arquivo truncado, master sem áudio

---

# FASE 2 — Rede de segurança (ANTES da reescrita)

> **Por que antes:** reescrever a extração sem teste é reescrever no escuro. A Fase 2 é o
> que torna a Fase 3 verificável.

### Tarefa 2.1 - Congelar fixtures

**Objetivo:** ter entrada real e estável para testar sem rede.
**Arquivo/Local Alvo:** criar `loom-downloader-tool/tests/fixtures/`
**O quê:** salvar (a) o HTML de embed do Loom já baixado, (b) o `master.m3u8`,
(c) uma `mediaplaylist` de vídeo e uma de áudio.
**Quando Executar:** início da Fase 2.
**Como Validar:** os arquivos existem e contêm `__APOLLO_STATE__` / `#EXT-X-STREAM-INF`.
**Rollback:** apagar o diretório.
**Risco:** Baixo.
**Critério para Avançar:** fixtures em disco, commitadas.

Status:
- [ ] feito
- [ ] bloqueado

---

### Tarefa 2.2 - Testes de unidade sobre as fixtures

**Objetivo:** travar o comportamento atual antes de mexer nele.
**Arquivo/Local Alvo:** criar `loom-downloader-tool/tests/test_extracao.py` e
`test_playlist.py`
**O quê:** cobrir `limpar_nome_arquivo`, extração de título, extração da URL `.m3u8`,
escolha do maior `BANDWIDTH`, separação vídeo/áudio. **Sem rede.**
**Quando Executar:** após 2.1.
**Como Validar:** `pytest -v` — saída literal, todos verdes.
**Rollback:** apagar os arquivos de teste.
**Risco:** Baixo.
**Critério para Avançar:** suíte verde contra o código **atual**, ainda com regex.

Status:
- [ ] feito
- [ ] bloqueado

---

### Tarefa 2.3 - Smoke test ao vivo (separado)

**Objetivo:** **este é o teste que teria pego o bug do Loom.** Fixture não pega mudança de
terceiro; só medição contra o site real pega.
**Arquivo/Local Alvo:** criar `loom-downloader-tool/tests/test_smoke_ao_vivo.py`
**O quê:** marcar com `@pytest.mark.rede` (excluído do `pytest` padrão). Bate no Loom real
e afirma que uma URL `.m3u8` foi extraída. Rodar sob demanda: `pytest -m rede`.
**Quando Executar:** após 2.2.
**Como Validar:** `pytest -m rede -v` passa; `pytest -v` **não** o executa.
**Rollback:** apagar o arquivo.
**Risco:** Baixo — read-only contra o Loom.
**Critério para Avançar:** os dois modos se comportam como descrito.

Status:
- [ ] feito
- [ ] bloqueado

---

# FASE 3 — Extração por estrutura

### Tarefa 3.1 - Extrair o Apollo state estruturalmente

**Objetivo:** parar de depender do formato do texto.
**Arquivo/Local Alvo:** `loom-downloader-tool/server/services/utils.py`
**O quê:** função nova `_extrair_apollo_state(html)`: localiza `window.__APOLLO_STATE__` e
usa `json.JSONDecoder().raw_decode()` para deixar o **parser JSON** achar o fim do objeto.
Sem contar chaves, sem regex do corpo.
**Quando Executar:** com a Fase 2 verde.
**Como Validar:** contra a fixture, retorna dict com 5 chaves no topo.
**Rollback:** `git checkout services/utils.py`.
**Risco:** Baixo.
**Critério para Avançar:** dict parseado a partir da fixture.

Status:
- [ ] feito
- [ ] bloqueado

---

### Tarefa 3.2 - Achar a URL caminhando na árvore

**Objetivo:** eliminar o regex que quebrou o projeto.
**Arquivo/Local Alvo:** `loom-downloader-tool/server/services/utils.py`
**O quê:** caminhar a árvore procurando o nó com `__typename == "CloudfrontSignedUrlPayload"`
e ler `url`. Título vem de `RegularUserVideo.name` na mesma passada.
**Manter o regex antigo como último fallback**, com log explícito quando usado — assim uma
mudança futura degrada em vez de quebrar.
**Quando Executar:** após 3.1.
**Como Validar:** testes da Fase 2 verdes **sem alteração**; `pytest -m rede` verde.
Prova extra: renomear `playlist-multibitrate.m3u8` na fixture para outra coisa e confirmar
que a extração **continua funcionando** — é a prova de que a fragilidade morreu.
**Rollback:** `git checkout services/utils.py`.
**Risco:** **Médio** — coração do sistema.
**Critério para Avançar:** suíte verde + o teste do rename passa.

Status:
- [ ] feito
- [ ] bloqueado

---

### Tarefa 3.3 - Falha silenciosa nunca mais

**Objetivo:** a pendência nº 1, que já custou duas horas hoje.
**Arquivo/Local Alvo:** `utils.py`, `downloader.py`, `routes.py`
**O quê:** trocar `except:` nus por `except Exception as e:` com log; logar quando a
extração falhar e **por quê**; propagar o motivo até o dashboard em vez de só `'erro'`.
**Quando Executar:** após 3.2.
**Como Validar:** forçar uma URL inválida e confirmar que a causa aparece no terminal.
**Rollback:** `git checkout` dos três arquivos.
**Risco:** Baixo.
**Critério para Avançar:** falha provocada produz mensagem legível.

Status:
- [ ] feito
- [ ] bloqueado

---

### Tarefa 3.4 - Parsear o m3u8 sem regex

**Objetivo:** o outro regex frágil, ainda não explodido (`downloader.py:85`).
**Arquivo/Local Alvo:** `loom-downloader-tool/server/services/downloader.py`
**O quê:** parser linha a linha do HLS (formato com gramática própria: uma linha
`#EXT-X-STREAM-INF:` seguida da URI na linha seguinte), no lugar do `re.findall` com `.*\n`.
**Quando Executar:** após 3.3.
**Como Validar:** testes de playlist da Fase 2 verdes sem alteração.
**Rollback:** `git checkout services/downloader.py`.
**Risco:** Médio.
**Critério para Avançar:** suíte verde + download real ainda funciona.

Status:
- [ ] feito
- [ ] bloqueado

---

### Tarefa 3.5 - Matar a duplicação de PASTA_OUTPUT

**Objetivo:** o `CLAUDE.md` avisa "mexeu num, mexa no outro" — isso é um bug esperando.
**Arquivo/Local Alvo:** `downloader.py:11-14` e `converter.py:8-11`
**O quê:** centralizar em `services/__init__.py` (que já define `PASTA_TEMP_RAIZ`) e
importar nos dois. Atualizar o `CLAUDE.md` removendo o aviso.
**Quando Executar:** após 3.4.
**Como Validar:** `grep -rn "PASTA_OUTPUT" server/` mostra **uma** definição.
**Rollback:** `git checkout`.
**Risco:** Baixo.
**Critério para Avançar:** definição única e download real funciona.

Status:
- [ ] feito
- [ ] bloqueado

---

### Tarefa 3.6 - Ctrl+C precisa matar o servidor

**Objetivo:** o zumbi das 21:44 custou meia hora de diagnóstico.
**Arquivo/Local Alvo:** `server/app.py` e `server/dashboard.py`
**O quê:** o `Live` do Rich provavelmente captura o `KeyboardInterrupt` antes do handler de
`app.py:35`. **Diagnosticar primeiro**, depois consertar. Além disso: detectar porta 5000
já ocupada no boot e abortar com mensagem clara em vez de morrer obscuramente.
**Quando Executar:** após 3.5.
**Como Validar:** subir, `Ctrl+C`, e confirmar com `Get-NetTCPConnection -LocalPort 5000`
que **nada** sobrou. Subir duas vezes e ver a mensagem de porta ocupada.
**Rollback:** `git checkout`.
**Risco:** Médio — mexe no ciclo de vida do processo.
**Critério para Avançar:** zero processo órfão após Ctrl+C.

Status:
- [ ] feito
- [ ] bloqueado

---

# FASE 4 — Crawler de curso (via extensão)

## Exploração no navegador — CONCLUÍDA (2026-07-24)

Feita com claude-in-chrome na sessão logada do usuário, curso GANG.EXE. Só foram lidos
nomes de chave, contagens e enums — nenhum valor sensível (o filtro de segurança bloqueou
o conteúdo do `__NEXT_DATA__`, que carrega tokens; medimos só o shape).

### Descoberta central

Todas as aulas do curso estão no `__NEXT_DATA__` da página (JSON de SSR do Next.js, 274 KB).
**Não é preciso navegar aula a aula** — o crawler lê o JSON e enfileira tudo de uma vez.

Decisões de arquitetura que isso força:
- **O crawler MORA na extensão**, não no agente. A ferramenta de automação é bloqueada de
  ler o `__NEXT_DATA__` (tokens de sessão). A extensão roda como código do usuário no
  contexto da página, sem esse filtro.
- O crawler extrai só `title`/`videoLink`/caminho e faz POST ao `localhost:5000`. Nenhum
  token sai da página.

### Modelo de dados (validado)

`props.pageProps`:
- `currentGroup.name` → nome da **Comunidade**
- `course` → a árvore do curso

Cada "unit" é um objeto com `{ id, unitType, parentId, rootId, metadata }`. `metadata` tem
`{ title, videoLink, videoLenMs, ... }`. Três `unitType` no curso medido:

| unitType | contagem | papel | tem Loom |
|---|---|---|---|
| `course` | 1 | o curso (raiz, sem parentId) | — |
| `set` | 3 | módulo / seção agrupadora | não |
| `module` | 22 | aula (folha) | 20 de 22 |

25 de 26 units têm `parentId` (só a raiz não tem). Alguns `module` não têm vídeo (aula de
texto) — o crawler pula quem não tem `videoLink` de Loom. Havia YouTube em OUTRA parte da
página (não dentro de `course`), então filtrar por `loom.com` no `videoLink` é obrigatório.

### Algoritmo do crawler (robusto por parentesco, não por aninhamento)

1. Parseia `__NEXT_DATA__`.
2. Travessia genérica de `props.pageProps.course`: coleta todo objeto que seja unit
   (`id` + `unitType` + `metadata`) num mapa `id -> unit`. Genérica de propósito — não
   depende de como o Skool aninha, sobrevive a mudança de estrutura.
3. Para cada unit `module` cujo `metadata.videoLink` contém `loom.com`:
   - `filename` = `metadata.title`
   - sobe pela cadeia `parentId`: o `set` pai dá o **Módulo**, a raiz dá o **Curso**
   - `folder` = `{currentGroup.name}/{curso}/{modulo}` (decisão do usuário: incluir módulo)
   - reutiliza `limparTexto` (já existe em content.js) em cada segmento do caminho
4. Um POST `/baixar` por aula, com **rate limit** entre eles (ex.: 300–500 ms) para não
   floodar o servidor nem o CDN.
5. Feedback no botão: "enfileirando X de N".

Decisões do usuário: **curso inteiro** (não só o módulo atual); pastas
**Comunidade/Curso/Módulo/Aula**.

### O que NÃO muda

- `max_workers=3` (`routes.py`) é concorrência, não capacidade. 20 aulas na fila
  funcionam; processa 3 por vez. Não mexer.
- A extração no lado do servidor: cada `videoLink` é uma URL de embed do Loom que já passa
  pela `extrair_metadados` reescrita na Fase 3.

## ✅ FASE 4 — CONCLUÍDA (2026-07-24)

Commits `ebfa94b` (crawler + texto) e `2e8ad36` (aulas vazias).

| Entregue | Como |
|---|---|
| Botão "Baixar curso inteiro" | `content.js`, fixo no canto, dry-run em 2 cliques |
| Coleta do curso | lê `__NEXT_DATA__`, travessia por `parentId` |
| Captura de texto | `desc`+`resources` → `.md` via `services/texto.py` |
| Conversor rich-text `[v2]` | ProseMirror-like → Markdown, tolerante |
| 3 casos de aula | vídeo+texto / só vídeo / só texto — todos no `worker_download` |
| Aulas vazias | `.md` placeholder, nenhuma omitida |

### Validado (dry-run ao vivo, curso GANG.EXE)

- **22 aulas**: 20 com vídeo + 2 placeholders (`Intro. MoneySkills`, `Storyads`)
- Pastas `BACKROOM.EXE/GANG.EXE/{Money Skills,Ativos digitais,Moneybrand}` — corretas
- Comunidade via `currentGroup.metadata.displayName` (não o slug) — bate com o botão individual
- 65 testes verdes (25 novos)

### Dois bugs pegos no dry-run, ANTES de baixar

1. Comunidade saía como slug `backroomexe-3259` → corrigido para `BACKROOM.EXE`.
2. Duas aulas (não uma) eram puladas por estarem vazias → agora viram placeholder.

### NÃO testado ainda (depende do usuário)

- Clicar no botão real na extensão recarregada.
- O disparo real dos downloads (~350 MB, decisão do usuário no momento).
- Cursos com estrutura diferente de GANG.EXE (o dry-run é a proteção).

---

## Microtarefas (referência do desenho — todas executadas acima)

### Tarefa 4.1 - Função que lê o __NEXT_DATA__ e monta a lista de aulas
**Arquivo:** `extension/content.js`. Função `coletarAulasDoCurso()` que devolve
`[{url, folder, filename}]`. Testável isolando o JSON.

### Tarefa 4.2 - Botão "Baixar curso inteiro"
**Arquivo:** `extension/content.js` + `extension/style.css`. Injetado na área do classroom.
Ao clicar: chama 4.1, confirma a contagem, dispara os POSTs com rate limit, dá feedback.

### Tarefa 4.3 - Validação no navegador
Medir com a sessão logada: a lista sai correta (20 aulas, caminhos certos)? Idealmente um
**dry-run** que só LOGА os POSTs no console antes de disparar de verdade — para conferir
folder/filename sem baixar nada.

### Risco a tratar
Disparar 20 downloads (~350 MB, ~20 min) é ação de efeito colateral em massa. O teste real
exige consentimento explícito do usuário no momento. O dry-run (4.3) mitiga: valida os
caminhos sem baixar.

---

## ✅ FASE 3 — CONCLUÍDA (2026-07-24)

| Tarefa | Resultado |
|---|---|
| 3.1 Extrair Apollo state | `raw_decode`, sem contar chaves |
| 3.2 URL/título por __typename | regex vira reserva com aviso; provado com URL isca |
| 3.3 Falhas visíveis | retry 3×, parcial removido, contagem de falhas, avisos |
| 3.4 m3u8 sem regex | parser HLS linha a linha, respeita aspas |
| 3.5 PASTA_OUTPUT único | `services/caminhos.py`; grep confirma 1 definição |
| 3.6 Ctrl+C + porta ocupada | porta ocupada: MEDIDO. Ctrl+C real: ver ressalva |

### Ressalva honesta sobre a 3.6

**Detecção de porta ocupada: funciona, medido.** Subi o servidor, tentei subir um
segundo, ele recusou com `exit 1` e a mensagem certa. Isto resolve o sintoma que
custou o diagnóstico de ontem (zumbi segurando a porta enquanto você acha que
reiniciou).

**Ctrl+C real: NÃO reproduzido.** Testar Ctrl+C de um terminal interativo no Windows,
de forma automatizada, é notoriamente instável (`CTRL_C_EVENT` entre processos exige
attach de console). Blindei por construção — handler de SIGINT/SIGTERM + `try/except
KeyboardInterrupt` em volta do `app.run()` + `encerrar()` idempotente — mas não pude
provar que o Ctrl+C do SEU terminal cai num desses caminhos. Precisa de um teste seu:
subir, apertar Ctrl+C, e rodar `Get-NetTCPConnection -LocalPort 5000` para ver se
sobrou algo.

### Incidente durante o teste

A varredura de órfãos do meu próprio teste tinha filtro largo demais (`*server*app.py*`)
e matou o servidor que o usuário tinha rodando, além dos do teste. Sem download em
curso e a temp é limpa no encerramento, então o efeito foi só "precisa subir de novo".
Registrado para não repetir: nunca varrer processos por nome de script no ambiente do
usuário.

---

## Checklist final (rodar ao término de todas as fases)

- [ ] `pytest -v` verde
- [ ] `pytest -m rede -v` verde
- [ ] Setup em clone limpo sobe com um comando
- [ ] Servidor sobe e o dashboard aparece
- [ ] Botão da extensão aparece numa aula do Skool
- [ ] Download real ponta a ponta → `.mp4` com vídeo **e** áudio no `ffprobe`
- [ ] `Ctrl+C` não deixa processo órfão
- [ ] `output/` intacta (268 MB preservados)
- [ ] `git status` sem arquivo indesejado
