# Pastas de canal nas outras comunidades

> **STATUS: ABERTO.** Depende de informação que só o dono do projeto tem.

## O problema

Até a v4.0 o servidor criava uma subpasta com o nome do canal do YouTube para
QUALQUER vídeo de lá — inclusive aula do Skool cujo `videoLink` aponta para o
YouTube. Isso inseriu um nível que não existe no Skool e tirou aulas da sequência
do módulo.

O bug está corrigido (`routes.py`: a subpasta de canal só vale para link colado).
O passado foi reparado **só na AI Makers Club**, com `reparar_pastas_canal.py`:
5 pastas intrusas eliminadas, 2,4 GB movidos para `output/_DUPLICADOS/`, nada
apagado.

## O que falta

Estas comunidades nunca foram medidas:

- BACKROOM.EXE
- Vibe Coding Base
- Vibe Coding School +
- Z4 CLIENTS

Há candidatas visíveis no disco (`Upwork Tutorials`, `Vibe Coding Tutorials`),
mas **candidata não é prova**: nomes assim podem ser módulos legítimos do curso.

## Por que não dá para adivinhar

Uma primeira tentativa usou heurística de nome e acusou 70+ pastas, incluindo
módulos legítimos como "Dia 1" e "Money Skills". Um validador que grita lobo é
pior que nenhum.

O `reparar_pastas_canal.py` foi então reescrito para comparar com a estrutura
REAL do curso, medida na API do Skool — o dicionário `ESTRUTURA` no topo do
script. Sem essa medição, o script não tem contra o que comparar.

## O que é preciso

Os links dessas comunidades no Skool. Com eles dá para:

1. medir a estrutura real de cada curso (módulos de verdade);
2. preencher `ESTRUTURA` no script;
3. rodar em SIMULAÇÃO e conferir a lista antes de mover qualquer coisa.

O script move para quarentena em vez de apagar — em disco externo o delete não
passa pela Lixeira.

## Pendência relacionada

`output/_DUPLICADOS/` guarda 2,4 GB da reparação da AI Makers Club, conferidos
por SHA-256. Podem ser apagados quando o dono do projeto conferir.
