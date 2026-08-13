# Ordem das aulas no disco

**Aberto em:** 12/08/2026
**Branch:** `Dev`
**Motivo:** as pastas ordenam alfabeticamente, não na ordem da biblioteca. O curso
foi montado numa sequência pedagógica e o disco a destrói.

---

## O que foi MEDIDO (12/08/2026, no Skool ao vivo)

Medido com automação do navegador, na sessão logada do dono do projeto, lendo o
`__NEXT_DATA__` de `ai-makers`. Nada aqui é suposição.

### A ordem existe, e é a posição no array `children`

```
pageProps.course
├── course      <- a unit do curso
└── children[]  <- ARRAY ORDENADO de módulos
    └── children[]  <- ARRAY ORDENADO de aulas
```

**Não há campo de ordem.** Campos da unit:

```
id, name, metadata, createdAt, updatedAt, unitType, rootId, userId, groupId, state, public
```

Campos da `metadata`: `coverImage, coverImageFile, desc, hasAccess, numModules, privacy, title`.

Nenhum `order`, `position`, `rank` ou `index`. **A posição no array é a única fonte
de verdade** — se ela se perder, a ordem não é recuperável de lugar nenhum.

`allCourses` (na listagem da comunidade) também é um array ordenado: dá a ordem dos
CURSOS na barra lateral, se um dia quisermos numerá-los.

### A ordem do array bate com a tela

Bootcamp: Mês 1 (`slug 1d46e489`, 30 módulos, 69 aulas):

```
ordemArray      : Dia 1:, Dia 2:, ..., Dia 9:, Dia 10:, ..., Dia 30:
ordemAlfabetica : Dia 10:, Dia 11:, ..., Dia 19:, Dia 1:, Dia 20:, ..., Dia 3:, ...
```

### O caso que prova que o problema é grave

Dentro do **Dia 1**, a ordem verdadeira é:

```
0: Wins do Mês 1
1: Escolha 1 nicho
2: Monte seu perfil de prospecção
3: Monte uma lista de prospecção
```

No disco, "Wins do Mês 1" cai em ÚLTIMO. É a primeira aula do dia. O disco não está
só fora de ordem: está trocando a abertura do módulo pelo fim dele.

### Onde a ordem se perde hoje

`coletarUnits` (`extension/content.js:184`) faz varredura genérica e guarda tudo num
dicionário por `id`. **A estrutura de array é descartada aí.** A hierarquia é
remontada depois por `parentId` (`caminhoDaAula`), que devolve o CAMINHO mas não a
POSIÇÃO.

---

## Desenho

Prefixo `NN - ` em módulo e aula, com padding por nível (`String(total).length`,
mínimo 2):

```
Bootcamp Mês 1/
├── 01 - Dia 1/
│   ├── 01 - Wins do Mês 1/
│   ├── 02 - Escolha 1 nicho/
│   ├── 03 - Monte seu perfil de prospecção/
│   └── 04 - Monte uma lista de prospecção/
├── 02 - Dia 2/
...
└── 30 - Dia 30/
```

**Por que prefixo e não índice em arquivo:** funciona em Explorer, VLC, celular, TV,
HD plugado noutro PC. A ordem vira propriedade do disco, não do nosso programa.

**Padding:** Bootcamp tem 30 módulos, Office Hours 85 — 2 dígitos cobrem. Calcular
por nível evita o mesmo bug de "Dia 10 antes de Dia 2" reaparecer com 3 dígitos.

## O RISCO que decide tudo

Renomear muda o caminho, e o "já baixei?" é baseado em caminho. Do jeito atual,
pôr `01 - ` na frente faria o servidor não achar nada e **rebaixar 522 aulas / 62 GB**.

> **A trava:** no "já baixei?", ignorar o prefixo numérico — procurar a pasta cujo
> nome TERMINA com o nome da aula, em vez de exigir igualdade exata.

Com isso, renumerar vira rename local e barato. E ganha uma propriedade que hoje não
existe: se o curso for **reordenado no Skool**, a renumeração não custa download
nenhum. Sem a trava, cada reordenação lá custaria dezenas de GB aqui.

**A Fase 1 é essa trava, sozinha e sem renomear nada.** Ela é o que torna as demais
reversíveis.

---

## Fase 1 — Trava do dedup (não muda nada visível)

### Tarefa 1.1 — Achar a pasta da aula ignorando o prefixo

**Objetivo:** `Modulo/07 - Aula X/` tem que ser reconhecida como a pasta de "Aula X".
**Arquivo/Local Alvo:** `server/routes.py` (perto de `_adotar_arquivos_soltos`)
**O quê:** `_pasta_existente_da_aula(pasta_pai_abs, nome_limpo)` — devolve o nome real
da pasta se existir uma que seja `nome_limpo` ou termine com ` - nome_limpo` tendo
prefixo só de dígitos. Sem match, devolve `None`.
**Como Validar:** testes com `Aula X`, `07 - Aula X`, `007 - Aula X`, e o negativo
`Outra - Aula X` (que NÃO pode casar).
**Rollback:** `git checkout server/routes.py`
**Risco:** Baixo (só amplia o que já é aceito).

Status:
- [x] feito
- [ ] bloqueado

### Tarefa 1.2 — `worker_download` usa a pasta existente

**Objetivo:** com pasta numerada em disco, gravar DENTRO dela em vez de criar
uma segunda sem número.
**Arquivo/Local Alvo:** `server/routes.py`, no bloco "pasta sempre"
**Risco:** Médio (mexe no caminho de gravação).

Status:
- [x] feito
- [ ] bloqueado

---

## Fase 2 — Extensão: capturar a ordem

### Tarefa 2.1 — Travessia por `children` com índices

**Objetivo:** obter `ordemModulo` e `ordemAula` sem perder a resiliência atual.
**Arquivo/Local Alvo:** `extension/content.js`
**O quê:** `ordemDasUnits(raiz)` anda por `children` e devolve `{id: {ordem, total}}`.
**CUIDADO:** a varredura genérica de hoje é resistente a o Skool mudar o aninhamento.
Ler `children` nos acopla ao formato. Manter as duas: usa `children` quando existir,
cai na genérica (sem ordem) quando não — e **avisa no console** ao cair, porque o
padrão de falha deste projeto é a coisa sumir calada.
**Risco:** Médio.

Status:
- [x] feito
- [ ] bloqueado

### Tarefa 2.2 — `pacoteDaAula` carrega a ordem

**Objetivo:** os três botões mandam a ordem, pela fonte única já existente.
**Arquivo/Local Alvo:** `extension/content.js` (`pacoteDaAula`, `corpoDoPedido`)
**Risco:** Baixo.

Status:
- [x] feito
- [ ] bloqueado

---

## Fase 3 — Servidor: aplicar o prefixo

### Tarefa 3.1 — Prefixar módulo e aula

**Objetivo:** `folder` e nome da pasta da aula nascem numerados.
**Arquivo/Local Alvo:** `server/routes.py` + `server/services/utils.py`
**O quê:** `prefixo_de_ordem(indice, total)` num lugar só. Pedido SEM ordem (link
colado, Loom avulso) grava sem prefixo — nunca inventa número.
**Risco:** Médio.

Status:
- [x] feito
- [ ] bloqueado

---

## Fase 4 — Migração

### Tarefa 4.1 — Renumerar + religar os 8 anexos órfãos

**Objetivo:** trazer o que já está em disco para o layout novo, numa passada só.
**Arquivo/Local Alvo:** `migrar_layout.py`
**O quê:** renumeração precisa da ordem VINDA DO SKOOL — o disco não a tem. Ou o
script recebe um mapa exportado pela extensão, ou a renumeração acontece
naturalmente no próximo download (a Fase 1 garante que nada seja rebaixado).
**Religamento:** anexo órfão casa por prefixo truncado; move só com **exatamente 1**
candidato. Com 0 ou 2+, deixa e reporta.
**Como Validar:** simulação; contagem de arquivos e bytes idêntica antes/depois.
**Rollback:** mapa da simulação salvo antes (como em 12/08).
**Risco:** ALTO — move arquivo em HD externo, sem Lixeira.

Status:
- [x] feito (religamento; a RENUMERAÇÃO migrou para o servidor — ver abaixo)
- [ ] bloqueado  (NÃO EXECUTAR SEM SINAL VERDE)

---

## Fase 5 — Verificação

- [ ] `python -m pytest` verde
- [ ] `node --check extension/content.js`
- [ ] servidor sobe; baixar uma aula já baixada **não** rebaixa (a prova da Fase 1)
- [ ] `/code-review high`
- [ ] README atualizado
- [ ] commit em `Dev` (**nunca** direto na `main`)

---

## O que a execução revelou (não estava previsto)

### 1. O plano tinha um buraco: as 522 pastas atuais nunca ganhariam número

A Fase 1 diz "pasta existente vence". Consequência que só apareceu ao escrever o
código: a numeração valeria **só para download novo**, e a biblioteca inteira
ficaria sem número para sempre.

**Solução, melhor que a migração prevista:** quando o servidor vê a ordem e acha uma
pasta com nome diferente do desejado, ele **renomeia** (`_renomear_pasta_da_aula`).
Assim um "baixar tudo" — que pula tudo o que já existe — vira uma **renumeração
completa sem baixar um byte**. E quando o curso for reordenado no Skool, o mesmo
caminho reordena o disco de graça.

Isso **elimina a necessidade** de um passo de renumeração no `migrar_layout.py`
(a Tarefa 4.1 original), que dependeria de exportar um mapa de ordem para o disco.

### 2. Bug que a simulação pegou antes de eu executar

Rodando o `migrar_layout.py` em simulação, ele propôs criar:

```
Bem-vindo/Bem-vindo./Bem-vindo..md
```

O Windows normaliza ponto final em nome de PASTA, então isso viraria
`Bem-vindo/Bem-vindo/` — o aninhamento `Aula X/Aula X/` que `_eh_pasta_de_aula`
existe justamente para impedir. Seriam **6 pastas aninhadas** (`Bem-vindo`,
`O tipo de agente que criamos aqui` em duas comunidades, e dois Founders Talk).

Causa: título de aula terminado em ponto ("por Luis F."). O Windows tira o ponto da
pasta e mantém no arquivo, então `pasta == basename` falhava. Corrigido comparando
com `rstrip('.')` dos dois lados.

**Se eu tivesse rodado `--executar` sem simular antes, teria estragado 6 pastas.**

### 3. Os 8 "anexos órfãos" não eram órfãos

Medido por SHA-256: **os 8 são idênticos** a arquivos que já estão dentro da pasta
da aula correta. Não precisam de religamento — são sobras, mesma classe dos 20
conflitos de 12/08. O código de religamento se recusou a sobrescrever (correto) e os
reportou como "já existe".

O religamento fica no script mesmo assim: a situação que ele resolve é real e vai
reaparecer em qualquer biblioteca migrada do layout antigo.

## O que a revisão (`/code-review high`) pegou

Nenhum achado aceito de palavra: cada um reproduzido antes de virar correção.

| # | Achado | Verificado? | Correção |
|---|---|---|---|
| 1 | **A trava cobria só a AULA, não o MÓDULO.** A extensão é quem numera o módulo, então o pedido chega `Com/Curso/01 - Dia 1`. Com `Dia 1` em disco, o caminho resolvia para `01 - Dia 1/01 - Aula 1` — inexistente. **A árvore numerada inteira nasceria ao lado da antiga e as 522 aulas seriam rebaixadas.** | **Sim**, reproduzido: `folder final: Com/Curso/01 - Dia 1\01 - Aula 1` com só `Dia 1` no disco | `_resolver_caminho` aplica a trava a CADA nível |
| 2 | `migrar_layout._eh_pasta_de_aula` não conhecia o prefixo → tratava pasta já migrada como solta e propunha `01 - Aula X/Aula X/` | **Sim**: devolvia `False` | usa `_sem_prefixo_de_ordem` nos dois lados |
| 3 | **`reparar_pastas_canal.py` classificaria toda pasta numerada como "intrusa"**, esvaziaria e faria `os.rmdir` — em HD externo, sem Lixeira | Sim, por leitura + fixture | `sem_prefixo_de_ordem` em `limpar` e `eh_pasta_de_aula`; intrusa real ("Gabriel Morais") continua sendo pega |
| 4 | Pill do Skool pode ficar preso entre aulas (SPA) e postar o vídeo da aula anterior | Não reproduzido | **EM ABERTO** — ver abaixo |
| 5 | **A faixa da conversão (85→99) nunca valeu no caminho do Loom**: `max(300 segmentos, 85 por cento)` congelava a barra em 100% | **Sim**, reproduzido nos 5 pontos da conversão | zera na troca de unidade + teste |
| 6 | Anexo adotado mantinha `<Aula> - ` e era rebaixado na execução seguinte | Sim, por leitura | prefixo cai na adoção + teste |

**O achado 1 é o mais importante desta rodada:** a Fase 1 existia exatamente para
evitar o rebaixe de 62 GB, e olhava um nível abaixo de onde o problema estava. Se eu
tivesse mandado testar sem a revisão, o dono do projeto teria visto a biblioteca
inteira rebaixando.

**O achado 5 desmente uma afirmação minha:** eu tinha fechado `barra-de-progresso.md`
dizendo que o progresso real do ffmpeg estava valendo. Valia só no yt-dlp. O
documento foi corrigido com a medição.

### Achado 4 — não corrigido, e por quê

O pill `sf-skool` guarda `_skoolVideoTentado = md` antes dos `await` e nunca reseta;
quando o player não é achado, ele é anexado ao `document.body`, que sobrevive à
navegação SPA. Navegando de A para B, o pill antigo pode continuar lá resolvendo o
vídeo de A com o nome de B.

**Não reproduzi**, e mexer no ciclo de vida do pill sem reproduzir é como se
introduzem regressões neste projeto. Fica registrado para um plano próprio, com o
caminho de reprodução: abrir uma aula do Skool sem player detectável, navegar para
outra sem F5, e conferir se o pill antigo continua no DOM.

## Estado atual

Fases 1, 2 e 3 **feitas**; **156 testes verdes**, `node --check` OK.
Fase 4 reduzida ao religamento de anexos (a renumeração migrou para o servidor).
Falta a validação de ponta a ponta na máquina do dono do projeto.

## Próximo passo

1. Reiniciar o servidor e recarregar a extensão.
2. Mandar **baixar tudo**: nada deve ser baixado, e as pastas devem sair numeradas
   na ordem do Skool. É a validação de ponta a ponta das três fases.
3. Decidir o destino dos 8 duplicados (a quarentena `_DUPLICADOS/` é o precedente).
