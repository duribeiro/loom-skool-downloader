# Relatório de cobertura de downloads — 2026-07-29

Cruzamento entre as aulas de vídeo acessíveis nas duas classrooms do Skool e os
`.mp4` presentes em `loom-downloader-tool/output/`.

Escopo: apenas cursos com `metadata.hasAccess === 1` (bloqueados/"Unlock"/"Private
Course" ficam de fora — não há como baixar). Comparadas apenas aulas **com vídeo**
(`videoLink`); aulas de texto/links de GPT são ignoradas de propósito.

Fonte da verdade da árvore de aulas: `props.pageProps.course` do `__NEXT_DATA__` de
cada curso. Fonte do baixado: `find output -name "*.mp4"`.

## Z4 CLIENTS @dougdemarco_ — 6 de 49 cursos acessíveis

| Curso | Vídeos no Skool | Baixados | Status |
|---|---|---|---|
| Comece aqui | 2 | 0 | ❌ faltam 2 |
| 🔓 Conteúdo desbloqueável | 1 | 1 | ✅ |
| CASH.doc | 10 | 10 | ✅ |
| AGENTE$ | 8 | 4 | ❌ faltam 4 |
| CAIXA 2.0 | 5 | 5 | ✅ |
| 〄 DOC + LOOM | 7 | 7 | ✅ |

## BACKROOM.EXE — 10 de 10 cursos acessíveis

| Curso | Vídeos no Skool | Baixados | Status |
|---|---|---|---|
| GANG.EXE | 20 | 20 | ✅ |
| DOUG.EXE 10 | 4 | 4 | ✅ |
| Implementação com claude code | 2 | 2 | ✅ |
| SKILLS | 1 | 1 | ✅ |
| AGENTES FUNCIONAIS | 9 | 8 | ❌ falta 1 |
| AGENTES NEURAIS | 16 | 16 | ✅ |
| IMPERIO SOLO | 5 | 5 | ✅ |
| RAYA METHOD (imagens e vídeos) | 11 | 10 | ❌ falta 1 |
| PROMPTBOOK DOUG.EXE | 0 (50 prompts de texto) | — | ✅ n/a |
| AGENTES GPTs | 0 (links de GPT) | — | ✅ n/a |

## Vídeos faltando

Genuinamente ausentes (não existem em nenhuma pasta):

1. **Criando sua oferta** — em `AGENTE$` (Z4) **e** `AGENTES FUNCIONAIS` (BACKROOM);
   falta nas duas. Só existe `AGENTES FUNCIONAIS/Criando sua oferta.md` (descrição),
   sem `.mp4` → provável falha silenciosa de download (limitação conhecida do projeto).
2. **〄 TAKE // agente vídeos** — `RAYA METHOD` › Vídeos ultra realistas.
3. **Ecossistema de produtos** — `Comece aqui` (Z4). Vídeo de intro.
4. **Problemas com acesso** — `Comece aqui` (Z4). Vídeo administrativo.

Faltam na pasta da Z4/AGENTE$ mas já baixados como duplicata em
BACKROOM/AGENTES FUNCIONAIS (mesmo conteúdo entre comunidades):

- Agente pronto para vender
- Resolvendo problemas com agentes
- Melhorando seu agente

## Notas

- `output/BACKROOM.EXE/Mini workshop (tesouro escondido)/2307.mp4` existe localmente
  mas não corresponde a nenhum curso atual das classrooms (conteúdo antigo ou de post
  de comunidade). Não é problema, só não bate com o inventário atual.
- Total: de ~101 aulas de vídeo acessíveis, faltam 4 vídeos únicos (2 deles apenas
  intros administrativos). Conteúdo de aula real faltando: "Criando sua oferta" e
  "〄 TAKE // agente vídeos".

## Causa raiz (relatada pelo usuário)

O botão "Baixar curso inteiro" enfileira sequencialmente no navegador; ao trocar de
curso e recarregar a página no meio do enfileiramento, as aulas ainda não enviadas se
perdem. Ver correções em `content.js` (bugs de enfileiramento + navegação SPA).
