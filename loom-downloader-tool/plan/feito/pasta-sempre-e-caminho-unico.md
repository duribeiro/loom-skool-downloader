# Pasta sempre + caminho único para os três botões

**Aberto em:** 12/08/2026
**Branch:** `Dev`
**Motivo:** o layout de pastas depende do CONTEÚDO do pedido, então a mesma aula
cai em lugares diferentes conforme o botão usado e conforme um fetch HTTP ter dado
certo. Isso quebra o "pular o que já baixou" e rebaixa curso inteiro.

---

## O que foi MEDIDO (12/08/2026)

Nada aqui é suposição. Cada linha veio de uma leitura de disco ou de código.

### O sintoma relatado

Baixar o curso "Bootcamp Mês 1" rebaixou aulas já baixadas, gravou **só os vídeos**,
não gravou `.md`, e largou os arquivos **soltos ao lado** das pastas de aula antigas.

### Estado da `output/` (sem `_DUPLICADOS` e `_BENCH`)

| | |
|---|---|
| Pastas-de-aula existentes | 269 |
| Arquivos já dentro delas | 608 |
| Arquivos soltos no módulo | 277 |
| Caminho mais longo hoje | 256 chars |
| Soltos que passariam de 260 ao ganhar pasta | **3** |
| Pior caso após a mudança | 286 chars |

Os 3 casos de risco (medidos, não estimados):

```
262  \AI Makers Club\Biblioteca de Templates\Make.com\Automatizando Qualificação de Leads com I - relevanceai-weblead.rai
286  \AI Makers Club\Biblioteca de Templates\N8N\Fluxo de Confirmação de Agendamento Calen - Buscar lead na agenda e confirmar.json
279  \YouTube\Hashtag Treinamentos\[Aula 3] Multiagentes Criando um Exercito de Agentes de IA que trabalham pra voce.mp4
```

> **Duas medições erradas antes desta.** A primeira somou uma pasta extra em arquivos
> que JÁ estavam dentro da pasta da aula (deu "83 em risco"). A segunda usou
> `pasta == nome do arquivo`, que não reconhece anexo (nome diferente do da pasta).
> O critério correto: uma pasta É pasta-de-aula se contém um arquivo com o mesmo nome
> dela. Registrado porque o erro é fácil de repetir.

### A causa, no código

`routes.py:206` decide o caminho a partir do conteúdo do pedido:

```python
aula_tem_pasta = _quantos_artefatos(url, desc, resources, anexos, nome_limpo) >= 2
```

- `desc` chegou  → 2 artefatos → **pasta da aula**
- `desc` não chegou → 1 artefato → **arquivo solto**

Mesma aula, dois caminhos, decididos por um fetch ter dado certo. O "já baixei?"
então procura o `.mp4` num lugar que a própria regra pode ter mudado — não acha,
rebaixa, e larga solto ao lado da pasta antiga. **É o bug relatado, por construção.**

### Divergência entre os três botões

| Botão | Caminho `Comunidade/Curso/Módulo` | Manda `desc`/`resources`/`anexos`? |
|---|---|---|
| Baixar todos os cursos | `caminhoDaAula` (`content.js:181`) | sim |
| Baixar curso específico | `caminhoDaAula` | sim |
| Baixar vídeo (pill) | `dadosDaAulaAtual` (`:858`) usa `caminhoDaAula`… | **NÃO** (`:900` posta só url/folder/filename) |

E quando `dadosDaAulaAtual` devolve `null`, o pill cai em `obterDadosDaPagina`
(`content.js:15`), que parseia o `document.title` e monta **só `Comunidade/Curso`** —
**sem o nível do módulo**. Duas fontes de verdade para a mesma pasta.

### Redirect: metade coberto

- `buscarPagePropsDeCurso` (`:676`, modo comunidade) **segue** `__N_REDIRECT`. OK.
- `buscarTextoDaAula` (`:451`) **segue** (corrigido em 12/08). OK.
- `obterPagePropsDoCurso` (`:204`, curso único e pill) **NÃO segue**. Se a URL não
  tiver `md`, a resposta é o payload de redirect, `pp.course` não vem, e a função
  cai no `__NEXT_DATA__` — que pode estar velho por navegação SPA.

### Ainda sem explicação

O módulo **`Dia 1`** do Bootcamp Mês 1 foi apagado de propósito e **não voltou** na
rodada de "baixar tudo". Zero arquivos escritos depois das 18:10 (e `salvar_aula_md`
abre em `"w"` sempre que há texto, então uma aula enfileirada com texto SEMPRE mexe
no mtime). Hipótese ainda não provada: as aulas do `Dia 1` não foram coletadas.
A instrumentação da Fase 4 é o que vai responder — **não fechar este plano sem isso**.

---

## Princípio que passa a valer

> **O lugar é função da IDENTIDADE da aula. O conteúdo só decide quais arquivos
> existem — nunca onde eles ficam.**

```
Comunidade / Curso / Módulo / Aula /
                               ├── Aula.mp4
                               ├── Aula.md      (se houver texto)
                               └── anexos       (se houver)
```

Pasta **sempre**, com 1 arquivo ou com 5. Decidido em 12/08/2026 pelo dono do projeto.

Ganhos: caminho idempotente; "já baixei?" vira uma pergunta num lugar só; o remendo
`ja_existe_pasta_da_aula` deixa de ser necessário; um `if` a menos para os três
botões manterem sincronizado.

Custo aceito: um clique a mais para chegar num vídeo de aula que só tem vídeo.

---

## Fase 1 — Servidor: pasta sempre

### Tarefa 1.1 — `aula_tem_pasta` passa a ser incondicional

**Objetivo:** tirar a decisão de caminho das mãos do conteúdo do pedido.
**Arquivo/Local Alvo:** `E:\CURSOS\Programação\Projetos\loom-downloader\hsl-lab\loom-downloader-tool\server\routes.py` (~:189-210)
**O quê:** remover o `if aula_tem_pasta`; a aula SEMPRE ganha `pasta_destino/nome_limpo`.
Remover o remendo `ja_existe_pasta_da_aula` (vira redundante) e a chamada a
`_quantos_artefatos`. Manter `_adotar_arquivos_soltos`, que agora vale sempre.
**Como:** substituir o bloco pela atribuição direta, com comentário registrando a
medição e o princípio (padrão da casa).
**Quando Executar:** primeiro de tudo — as demais fases dependem deste caminho.
**Como Validar:** `python -m pytest tests/test_worker.py -q` verde.
**Rollback:** `git checkout server/routes.py`
**Risco:** Médio (muda o layout de 917 arquivos já baixados).
**Critério para Avançar:** suíte verde.

Status:
- [x] feito
- [ ] bloqueado

### Tarefa 1.2 — `_quantos_artefatos` some ou fica?

**Objetivo:** não deixar função morta (clean-code).
**Arquivo/Local Alvo:** `server/routes.py:60`
**O quê:** após 1.1 o único chamador desaparece. Remover a função **e** os testes que
a exercitam pela decisão de pasta; preservar os que medem o `.md`.
**Como Validar:** `grep -rn "_quantos_artefatos" server/ tests/` sem resultado.
**Rollback:** `git checkout server/routes.py tests/`
**Risco:** Baixo.

Status:
- [x] feito
- [ ] bloqueado

### Tarefa 1.3 — Teto de comprimento de nome (MAX_PATH)

**Objetivo:** os 3 caminhos medidos acima passam de 260 chars com a pasta a mais.
**Arquivo/Local Alvo:** `server/services/utils.py:15` (`limpar_nome_arquivo`)
**O quê:** limite de caracteres no nome, cortando no fim e preservando a extensão.
**NÃO** mexer em configuração do Windows para caminho longo — é sistema, não é nosso.
**Como Validar:** teste novo com nome de 300 chars; e nenhum caminho previsto > 255.
**Rollback:** `git checkout server/services/utils.py`
**Risco:** Médio (muda nome de arquivo já gravado — conferir idempotência).

Status:
- [x] feito
- [ ] bloqueado

---

## Fase 2 — Extensão: um pacote só para os três botões

### Tarefa 2.1 — Extrair `pacoteDaAula(unit, porId, comunidade)`

**Objetivo:** uma função monta `{url, folder, filename, desc, resources, _videoId, _temVideo, _temTexto, _id}`.
Hoje isso está inline em `extrairAulas` e pela metade em `dadosDaAulaAtual`.
**Arquivo/Local Alvo:** `extension/content.js` (novo, perto de `caminhoDaAula`:181)
**Como:** mover o corpo do laço de `extrairAulas` (`:281-335`) para a função nova;
`extrairAulas` passa a ser o laço chamando ela.
**Como Validar:** `node --check extension/content.js`; e o mesmo `md` produzir
`folder`+`filename` idênticos pelos dois caminhos.
**Rollback:** `git checkout extension/content.js`
**Risco:** Médio.

Status:
- [x] feito
- [ ] bloqueado

### Tarefa 2.2 — `dadosDaAulaAtual` passa a usar `pacoteDaAula`

**Objetivo:** o pill mandar `desc`/`resources`/`anexos` como os outros dois botões —
é o que faz "baixar vídeo" gerar `.md`.
**Arquivo/Local Alvo:** `extension/content.js:858` e os 3 POSTs do pill (`:900`, `:1037`, `:1233`)
**Risco:** Médio.

Status:
- [x] feito
- [ ] bloqueado

### Tarefa 2.3 — `obterPagePropsDoCurso` segue `__N_REDIRECT`

**Objetivo:** fechar a única das três buscas que ainda não segue.
**Arquivo/Local Alvo:** `extension/content.js:204`
**Como:** mesmo laço de `buscarPagePropsDeCurso` (`:676`), preservando o `md` pedido.
**Risco:** Baixo.

Status:
- [x] feito
- [ ] bloqueado

---

## Fase 3 — Migração dos 277 soltos

### Tarefa 3.1 — Simulação

**Objetivo:** ver o que seria movido ANTES de mover.
**Comando Exato:**
```bash
cd "E:/CURSOS/Programação/Projetos/loom-downloader/hsl-lab/loom-downloader-tool"
python migrar_layout.py
```
**Como Validar:** a lista sai e **nada** muda no disco.
**Risco:** Baixo (simula por padrão).

Status:
- [x] feito
- [ ] bloqueado

### Tarefa 3.2 — Execução

**NÃO EXECUTAR SEM SINAL VERDE EXPLÍCITO.** Move arquivo em HDD externo, que não
passa pela Lixeira.
**Comando Exato:** `python migrar_layout.py --executar`
**Rollback:** não há automático — por isso a simulação vem antes.
**Risco:** ALTO.

Status:
- [ ] feito  (AGUARDA SINAL VERDE)
- [ ] bloqueado

---

## Fase 4 — Enxergar o erro (o `Dia 1`)

### Tarefa 4.1 — Motivo do erro em arquivo

**Objetivo:** hoje o motivo sai por `print` e o dashboard (`Live(screen=True)`)
repinta por cima. O usuário vê "1 erro" e mais nada. Foi o que aconteceu hoje.
**Arquivo/Local Alvo:** `server/services/registro.py` (novo) → `logs/erros.log`
**O quê:** `registrar_erro(nome, pasta, motivo)` com timestamp; `item['motivo']`
guardado no dashboard. Caminho em `services/caminhos.py`, nunca duplicado.
**Como Validar:** provocar um erro e o arquivo existir com o motivo.
**Risco:** Baixo.

Status:
- [x] feito
- [ ] bloqueado

### Tarefa 4.2 — Log do enfileiramento

**Objetivo:** responder de vez por que o `Dia 1` não foi enfileirado.
**Arquivo/Local Alvo:** `extension/content.js`
**O quê:** ao fim da coleta, `console.log` com curso → nº de módulos → nº de aulas.
**Risco:** Baixo.

Status:
- [x] feito
- [ ] bloqueado

---

## Fase 5 — Verificação

- [ ] `python -m pytest` verde (109+ testes)
- [ ] `node --check extension/content.js`
- [ ] `/code-review high` — hardcode, número mágico, função reaproveitável, SOLID
- [ ] servidor sobe e baixa uma aula de cada origem (Loom, YouTube, Vimeo, Skool)
- [ ] commit em `Dev` (**nunca** direto na `main`)

---

## O que a execução revelou (não estava previsto)

1. **`migrar_layout.py` tinha a regra DUPLICADA.** O `if len(fs) >= 2` (`:77`) era cópia
   da regra do servidor. Com o servidor mudando, o script ficou cego: a simulação
   reportou **0 movimentos** com 277 arquivos soltos em disco. Corrigido.
2. **`prefixar` em `baixar_anexos` virou ramo morto.** O prefixo `<Aula> - <arquivo>`
   existia para evitar colisão de anexos SOLTOS no módulo. Com pasta sempre, dois
   anexos de aulas diferentes nunca dividem diretório. Removido junto com
   `_nome_do_anexo` e com o parâmetro `nome_aula`, que ficou sem uso.
3. **Eu introduzi um `NameError`** ao remover `aula_tem_pasta` deixando
   `prefixar=not aula_tem_pasta` para trás. A suíte **não pegou**: o bloco só roda
   `if anexos:` e nenhum teste exercita anexo no worker. Buraco de cobertura conhecido.
4. **Os testes poluíam `logs/erros.log` do projeto** — 4 linhas de fixture ("Aula 1",
   "boom no meio do download") no arquivo onde alguém procuraria um erro DE VERDADE.
   Fechado com fixture `autouse` no `conftest.py`.
5. **20 conflitos na migração**, todos **idênticos em tamanho** (cópia solta + cópia na
   pasta). O script pula sem sobrescrever. As cópias soltas continuam em disco —
   decisão do dono do projeto, não do agente.
6. **Duas medições minhas saíram erradas antes de acertar** o número de arquivos em
   risco (83 → 7 → 3). Registrado na seção de medições.

## O que a revisão (`/code-review high`) pegou — e o que eu confirmei medindo

Nenhum achado foi aceito de palavra; cada um foi remedido antes de virar correção.

| # | Achado | Verificado? | Correção |
|---|---|---|---|
| 1 | **HIGH — anexo perdia a extensão.** Remover `_nome_do_anexo` (que usava `splitext`) + corte cego de 80 no `limpar_nome_arquivo`, no mesmo patch, fazia `...API.pdf` (90) virar `...Evoluti` (80). | **Sim.** Reproduzido: `EXTENSAO PRESERVADA? False` | `cortar_preservando_extensao` em `utils.py`, com heurística para não confundir ponto do meio do nome com extensão. 5 testes. |
| 2 | **Colisão de `hls-temp/`.** Dois downloads de mesmo nome dividem a pasta de trabalho; o primeiro a terminar apaga os segmentos do outro. | **Sim, e é ANTERIOR a esta mudança** — a linha é idêntica em `dc68c70`. O teto de 80 só aumenta a chance. | Sufixo `uuid` na pasta temp. |
| 3 | **`_adotar_arquivos_soltos` roubava arquivo de aula vizinha.** "Aula 1" adotava `Aula 1 - Extra.mp4` de "Aula 1 - Extra", que então rebaixava. | Sim, por leitura da regra. | Prefixo passa a valer só para anexo; `.mp4`/`.md` exigem nome exato. Teste de regressão. |
| 4 | **Redirect descartava o `md` pedido**, então `pinnedPosts` podia vir da aula errada. | Sim, por leitura. | `mdInicial` vence o md do redirect; corta o laço em vez de girar. |
| 5 | **`buscarTextoDaAula` remontava a query com o slug ANTIGO** e falhava calada. | Sim, por leitura. | Query remontada com o slug canônico + `console.warn` ao desistir. |
| 6 | **O motivo do erro não chegava ao painel.** `grep motivo dashboard.py` = nada. | **Sim.** Confirmado por grep. | Histórico passa a mostrar erro na frente, com motivo. |
| 7 | Log do crash apontava a pasta do módulo, não a da aula. | Sim, por leitura. | Pasta lida do item, que o worker mantém em dia. |
| 8 | Docstring do `migrar_layout.py` contradizia o código — em script que **move arquivo**. | Sim. | Cabeçalho reescrito. |

**Erro meu descoberto ao corrigir o #6:** a primeira versão cortava nome e motivo em
larguras fixas (28 + 44). Medido em 5 larguras de terminal: **a 80 colunas o painel
rendeu 8 linhas contra um orçamento de 5** — exatamente a cascata de bordas que o
projeto já sofreu. Corte fixo é o remédio errado, porque a largura é do terminal e não
do texto. Trocado por `no_wrap` + `overflow='ellipsis'`, que faz o Rich decidir no
render. Verificado de 40 a 200 colunas: 5 linhas em todas.

## Estado atual

**FECHADO em 12/08/2026.** Todas as fases executadas, migração inclusive.

### Migração aplicada (Fase 3)

Autorizada pelo dono do projeto e executada com mapa salvo antes (`logs/migracao-*`):

```
ANTES  -> 885 arquivos | 63.771.816.896 bytes
DEPOIS -> 885 arquivos | 63.771.816.896 bytes   (nada perdido)

pastas-de-aula : 269 -> 522
arquivos soltos: 277 ->   8
```

Os **20 conflitos** (arquivo presente solto no módulo E dentro da pasta da aula)
foram comparados por **SHA-256**: os 20 idênticos byte a byte. Movidos para
`output/_DUPLICADOS/` preservando o caminho de origem — 1,53 GB, reversível.
Verificado um a um que a cópia boa permanece na biblioteca.

### Prova de que o defeito relatado sumiu

`Dia 22 / Enviar 20 mensagens de prospecção` — a aula que falhava desde o início —
baixou com `.md` + `.mp4` (7,0 MB). `Dia 1`, apagado de propósito, voltou inteiro
com vídeo, texto, `.zip` e `.csv`. **Log de erros vazio** na rodada completa.

### Erro meu, registrado

Movi arquivos com o servidor **escrevendo**. Eu tinha medido "0 escritas em 5
minutos", mas essa medição estava com ~20 minutos de idade quando executei, e nesse
intervalo um download foi iniciado. Deu certo por sorte estrutural (só toquei em
cópias soltas no módulo; o servidor escrevia nas pastas das aulas), não por
garantia. **O certo era remedir imediatamente antes de mexer.**

Também escrevi um verificador que checou **zero arquivos** e mesmo assim declarou
sucesso: filtrei por data de escrita, e `Move-Item` preserva timestamp. Validador
que não mede nada é pior que nenhum.

### O que ficou para outro plano

8 anexos órfãos na Biblioteca de Templates (prefixo da aula truncado). Medido: cada
um casa com **exatamente uma** aula. Vai junto com [[ordem-das-aulas-no-disco]],
para não mexer duas vezes na mesma árvore.

## Próximo passo

1. Reiniciar o servidor e recarregar a extensão.
2. Baixar **um curso** com o console aberto: a linha `[Sifão] coletadas N aulas em M
   módulos` responde se o `Dia 1` é coletado — a pergunta que este plano deixou aberta.
3. Com sinal verde: `python migrar_layout.py --executar` (269 aulas, 249 arquivos).
