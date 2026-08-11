# Baixar todos os cursos de uma comunidade (Skool)

> **STATUS: IMPLEMENTADO E EM USO.** Conferido no código em 11/08/2026:
> `ehPaginaComunidade` (`extension/content.js:572`), `buscarPagePropsDeCurso`
> (`:578`), `listarCursosDaComunidade` (`:616`) e o card de confirmação em dois
> passos no popup (`extension/popup.js:101-170`). Só o último item do checklist
> — teste de ponta a ponta com a extensão recarregada — **não é verificável por
> leitura de código**; ficou como estava.

Data: 2026-08-10 · Branch: Dev

## Objetivo

No popup do Sifão, quando a aba estiver em `skool.com/{grupo}/classroom` (listagem de
cursos, sem curso selecionado), oferecer **"Baixar todos os cursos"** — enfileirando
todas as aulas de todos os cursos acessíveis, com confirmação prévia no popup.

## Por que não funcionava (medido)

`slugsDaUrl()` (`extension/content.js:200-201`) tira o curso de `pathname.split('/')[3]`.
Em `/ai-makers/classroom` esse índice não existe → `obterPagePropsDoCurso()` devolve
`null` → `contextoCurso()` responde `{ok:false}` → `popup.js:56` nunca revela o card.

## Medições na página real (https://www.skool.com/ai-makers/classroom)

Feitas via Chrome com a sessão logada do usuário. Todas confirmadas em execução.

### 1. A listagem de cursos vive em `pageProps.allCourses`

Rota Next.js: `/[group]/classroom`. `pageProps` **não** tem `course`/`courses`; tem
`allCourses` — array de 22 objetos, cada um:

| campo | exemplo | uso |
|---|---|---|
| `name` | `"d7dbd06a"` | **slug** do curso (vai na URL) |
| `metadata.title` | `"Claude Code"` | nome exibível |
| `metadata.hasAccess` | `1` ou `null` | **gate de acesso** |
| `metadata.numModules` | `8` | nº de aulas (ver §4) |
| `unitType` | `"course"` | — |

### 2. Buscar o JSON de um curso exige seguir um redirect lógico

`GET /_next/data/{buildId}/{group}/classroom/{slug}.json?group=..&course=..`
responde **200** com corpo de redirect, não com o curso:

```json
{"pageProps":{"__N_REDIRECT":"/ai-makers/classroom/d7dbd06a?md=c4fc4327...","__N_REDIRECT_STATUS":307}}
```

É preciso extrair o `md` do `__N_REDIRECT` e refazer o fetch com `&md={md}`. Aí sim vem
`pageProps.course` + `pageProps.currentGroup`. Por isso o código atual só funciona
*dentro* de um curso: a URL já carrega o `md`.

**Consequência de projeto:** `obterPagePropsDoCurso()` precisa ganhar um irmão
genérico que aceite slug e siga o redirect.

### 3. Curso sem acesso não expõe vídeo — não há o que baixar

| curso | aulas | com `videoLink` |
|---|---|---|
| Claude Code (`hasAccess:1`) | 8 | **8** |
| Bootcamp Mês 2 (`hasAccess:null`) | 63 | **0** |

O Skool devolve a *estrutura* (títulos, módulos) mas remove os links de vídeo no
servidor. Filtrar por `hasAccess === 1` é obrigatório — não por política apenas, mas
porque os 11 bloqueados renderiam 0 vídeos e só gastariam requests.

### 4. `numModules` == contagem real de aulas

Soma de `numModules` dos 11 acessíveis = **280**. Varredura real das árvores = **280**.
Batem exatamente. Logo o popup mostra o total **instantaneamente**, sem varrer antes
da confirmação.

### 5. Ensaio de volume (concorrência 3 + 150ms de respiro)

11 cursos varridos em **7,8s**, sem rate-limit. Resultado agregado:

- 280 aulas · 181 com vídeo · **78 Loom** · **103 YouTube** · 0 de outra plataforma

### 6. Endpoint fresco da listagem funciona

`GET /_next/data/{buildId}/{group}/classroom.json?group={group}` → 200 com
`allCourses` (22) e `currentGroup.metadata.displayName` = `"AI Makers Club"`.
Usar isso em vez do `__NEXT_DATA__` evita o mesmo bug de cache velho em navegação SPA
já documentado em `content.js:204`.

### 7. Nome da pasta permanece consistente

`currentGroup.metadata.displayName` vem igual no JSON de cada curso, e é o que
`extrairAulas()` (`content.js:269-270`) já usa. Os downloads caem na mesma pasta de
comunidade dos botões existentes. Nada a mudar.

## Riscos identificados

1. **`ctx` por curso.** `enfileirarCurso(aulas, ctx, ...)` recebe **um** ctx, e
   `obterContexto()` tira o slug do curso da URL. Em modo comunidade não há curso na
   URL, e cada aula pertence a um curso diferente → o ctx precisa ser **por curso**,
   senão a fase de captura de texto busca no curso errado (ou em nenhum).
2. **Volume da fase de texto.** 280 aulas × 1 fetch, concorrência 4 + 200ms de respiro
   ≈ 30-60s. Aceitável, mas o progresso precisa ser visível e o guarda
   `beforeunload` (`content.js:763`) precisa cobrir o processo inteiro.
3. **Reabrir o popup no meio.** O enfileiramento roda no content script e sobrevive ao
   fechamento do popup (design atual). O popup reaberto deve conseguir reencontrar o
   estado em vez de disparar tudo de novo.

## Abordagem

Reutilizar `extrairAulas()` inteiro — ele já resolve caminho, módulo, Loom/YouTube e
aula de texto. O que entra de novo é só a camada de **listar cursos → buscar cada um →
concatenar**, mais o card de comunidade no popup com confirmação em dois passos.

## O que foi implementado

### `extension/content.js`

- `enfileirarCurso()` — passa a preferir `aula._ctx` ao ctx da aba (risco nº 1).
- **Seção 1.7** nova:
  - `ehPaginaComunidade()` — detecta `/{grupo}/classroom` sem slug de curso.
  - `buscarPagePropsDeCurso(slug, buildId, group)` — busca por slug **seguindo o
    `__N_REDIRECT`** (máx. 2 saltos).
  - `listarCursosDaComunidade()` — listagem fresca + fallback validado por grupo;
    separa `cursos` (hasAccess === 1) de `bloqueados`.
  - `contextoComunidade()` — resumo instantâneo via `numModules`.
  - `enfileirarComunidadeDaAba()` — varre a 3 de concorrência + 150ms, marca `_ctx`
    por aula, delega a `enfileirarCurso`, devolve `bloqueados` e `falharam`.
- Handlers `sifao:contextoComunidade` e `sifao:baixarComunidade`.

### `extension/popup.html` / `popup.js`

- Card `#ctxComunidade` + confirmação em 2 passos (1º clique arma e mostra o total,
  2º dispara) + botão Cancelar.
- Progresso roteado para o botão que está rodando; fase nova `cursos`.
- `.hint` com `white-space:pre-line` para o relatório final multi-linha.

## Validação

| item | resultado |
|---|---|
| `node --check` nos dois arquivos | OK |
| Listagem fresca `classroom.json` | 200 · 22 cursos · 11 acessíveis · 280 aulas |
| Redirect `__N_REDIRECT` seguido | OK em curso com e sem acesso (1 salto) |
| Varredura dos 11 acessíveis | 7,8s · 280 aulas · 181 vídeos · sem rate-limit |
| `extrairAulas` sobre pp **por slug** | 77 aulas, **0 sem pasta** |
| Pasta — curso raso | `AI Makers Club/Claude Code` |
| Pasta — curso com módulos | `AI Makers Club/Bootcamp Mês 1/Dia 1` |
| Servidor local | HTTP 404 em `/` = online (só existe `/baixar`) |

Pendente: teste de ponta a ponta com a extensão recarregada no Chrome.

## Status

- [x] Medição da página real
- [x] Implementação em `content.js`
- [x] Implementação no popup
- [x] Validação da lógica e dos dados contra a página real
- [ ] Teste de ponta a ponta com a extensão recarregada
