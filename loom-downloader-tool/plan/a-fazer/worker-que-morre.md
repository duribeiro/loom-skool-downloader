# Worker que morre em silêncio

> **STATUS: SINTOMA CONTIDO, CAUSA DESCONHECIDA.** A falha agora aparece; falta
> descobrir por que ela acontece.

## O sintoma que denunciou

O painel mostrava **6 aulas com status "baixando" e só 4 vagas** no executor.
Matematicamente impossível se todas estivessem em worker. Duas ficavam em 0%
para sempre — entre elas "Enviar 20 mensagens de prospecção", nos módulos
**Dia 19** e **Dia 22** do Bootcamp Mês 1.

Essas duas já tinham ficado para trás em execuções anteriores. Não é acaso: é
reproduzível.

## Causa do SILÊNCIO (corrigida)

`executor.submit(worker_download, ...)` e ninguém lia o `Future`. O
`ThreadPoolExecutor` guarda a exceção ali e só a revela em `.result()`.

Um worker que estourasse fora dos `try` internos morria calado:

- o item ficava em `status='baixando'` com progresso 0 para sempre;
- a vaga era liberada, a fila seguia normalmente;
- o contador de ativos passava a mentir.

Pior que falha barulhenta: a aula não baixa, não acusa erro, e o painel afirma
que está trabalhando nela.

**Corrigido** por `_worker_blindado` (`routes.py`): exceção vira `status='erro'`
e traceback no terminal. Coberto por
`test_worker_que_estoura_vira_erro_e_nao_fica_baixando`, conferido nos dois
sentidos (sem a blindagem o teste falha).

## O que AINDA não se sabe

**Por que aquelas duas aulas estouram.** A blindagem não conserta a causa — ela
faz a causa aparecer.

O que já foi descartado por medição (12/08/2026):

| Hipótese | Resultado |
|---|---|
| Vídeo inacessível / sem permissão | ❌ `hasAccess: 1`, vídeo do Loom normal |
| Extração de metadados falha | ❌ funciona em 1,5s, título e m3u8 corretos |
| Download em si falha | ❌ baixa em 7,3s isolado — 8 segmentos, arquivo íntegro |
| Vídeo corrompido/estranho | ❌ 17 segundos de duração, nada de anormal |

Ou seja: **o vídeo está são e o download funciona.** A falha está em outro ponto
do `worker_download` — antes ou depois do download.

Uma pista não confirmada: numa execução, o `.md` dessa aula foi gravado **solto
no módulo**, não em pasta própria. Isso significa que `_quantos_artefatos`
devolveu 1, ou seja, o pedido chegou **sem URL de vídeo**. Se a extensão está
mandando `url` vazia para essas aulas em alguns casos, o caminho percorrido é
outro — e pode ser ali que estoura.

## Próximo passo

Reiniciar o servidor com a blindagem ativa e reenfileirar o Bootcamp Mês 1. O
terminal vai mostrar:

```
❌ WORKER MORREU em 'Enviar 20 mensagens de prospecção': <Tipo>: <mensagem>
  <traceback>
```

Com o traceback em mãos a causa deixa de ser adivinhação. **Não implementar nada
antes disso** — as quatro hipóteses acima já foram descartadas por medição, e
inventar uma quinta sem dado novo é o caminho para consertar o que não está
quebrado.

## Critério para dar por pronto

As duas aulas baixarem, e nenhum item permanecer em "baixando" com 0% após a fila
esvaziar.
