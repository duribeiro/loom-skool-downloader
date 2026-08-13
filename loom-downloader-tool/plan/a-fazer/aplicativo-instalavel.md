# Sifão como aplicativo instalável (.exe + interface)

> **STATUS: VISÃO DEFINIDA, NADA IMPLEMENTADO.** Próximo grande passo do projeto,
> decidido pelo dono em 13/08/2026, depois de o layout de pastas estabilizar.

Substitui a nota antiga `extensao-standalone.md`, que tratava as duas opções como
abertas. **A decisão está tomada: caminho B — empacotar, não reescrever no
navegador.** O motor Python + FFmpeg funciona e é o que dá qualidade e organização;
o que incomoda é a operação.

## O que o dono do projeto pediu

> "Compilar para gerar um instalador único, um `.exe`, sem precisar rodar ou subir o
> servidor no terminal. Precisaremos apenas de uma interface estilo IDM para
> monitorar os downloads, escolher a pasta de saída (que atualmente não conseguimos
> escolher) e outras funcionalidades futuras."

Quatro requisitos, em ordem de importância:

1. **Instalador único `.exe`** — sem Python, sem `pip install`, sem PATH.
2. **Sem terminal** — o servidor sobe sozinho, em segundo plano.
3. **Interface estilo IDM** para acompanhar a fila (hoje isso é o dashboard `rich`,
   preso a um terminal aberto).
4. **Escolher a pasta de saída** — hoje é impossível.

## Por que isto importa (medido, não achismo)

A maior parte dos problemas relatados nas sessões de 11–13/08/2026 foi de **operação
do servidor**, não de download: servidor que subiu escondido em background, que ficou
com código velho depois de uma edição, que precisou ser reiniciado a cada mudança,
porta ocupada por instância antiga. Nenhum desses existiria com um serviço instalado.

## O bloqueio real: a pasta de saída

`PASTA_OUTPUT` (`services/caminhos.py:18`) é **calculada a partir da localização do
arquivo `.py`** e é constante de módulo. Medido em 13/08/2026:

- **16 usos** espalhados por 6 arquivos (`routes.py`, `converter.py`, `downloader.py`,
  `skool.py`, `texto.py`, `ytdlp.py`), todos importando o valor direto;
- `PASTA_TEMP_RAIZ` é pior: **`"hls-temp"`, relativo ao diretório de trabalho** — por
  isso o servidor tem que ser iniciado de `loom-downloader-tool/`. Um `.exe` que sobe
  com o Windows **não tem esse cwd**, então isto quebra antes de qualquer interface.

Não é "trocar uma constante". É trocar a forma como o destino chega em cada camada.
Os testes já monkeypatcham `PASTA_OUTPUT` em vários pontos, o que confirma que a
constante global é o acoplamento a desfazer.

**Este é o primeiro trabalho técnico da fase**, e ele tem valor sozinho: pasta de
saída configurável é útil hoje, mesmo antes de existir instalador.

## Ordem proposta

### Fase 1 — Configuração (útil por si só, sem interface)

- Um objeto/módulo de configuração com `pasta_output` e `pasta_temp`, lido de um
  arquivo (`sifao.json`) ao subir, com o padrão de hoje como fallback.
- `PASTA_TEMP_RAIZ` vira **absoluta**, derivada da configuração. Enquanto for
  relativa ao cwd, nenhum empacotamento funciona.
- As 16 chamadas passam a ler da configuração.
- **Como validar:** subir o servidor de um diretório qualquer (`cd C:\` e rodar) e
  baixar uma aula. Hoje isso quebra.

### Fase 2 — Empacotamento

- PyInstaller (ou similar) com FFmpeg embutido; `verificar_ffmpeg` (`app.py:26`)
  passa a procurar primeiro o binário embarcado.
- Instalador (Inno Setup / NSIS) que registra o serviço e cria atalho.
- **Cuidado medido:** `porta_ocupada()` (`app.py:39`) recusa subir um segundo
  servidor. Com início automático, isso vira funcionalidade — não pode virar erro
  na cara do usuário.

### Fase 3 — Interface

- O dashboard `rich` já modela tudo que a tela precisa: fila, ativos, progresso por
  faixa, ETA, erro **com motivo**. A interface é uma view nova sobre o mesmo
  `DASHBOARD_DATA`, não um sistema novo.
- **Restrição herdada:** `DASHBOARD_DATA` (`dashboard.py:15`) é lista global mutada
  por threads **sem lock**. O contrato atual — só anexar itens e mutar campos, nunca
  reordenar nem remover — precisa continuar valendo, ou virar um lock de verdade.
- Escolha da pasta de saída na tela, gravando na configuração da Fase 1.

### Fase 4 — Funcionalidades que a interface destrava

Ideias, não compromissos:

- Cancelar download (hoje só matando o processo — limitação conhecida do README).
- Escolher qualidade antes de baixar.
- Refazer só as aulas que deram erro, lendo `logs/erros.log`.

## O que NÃO fazer

**Reescrever o motor no navegador.** A opção A do plano antigo (extensão pura, sem
Python) esbarra na fusão vídeo+áudio: sem FFmpeg, ou se usa `ffmpeg.wasm` — pesado e
lento — ou se aceita entregar faixas separadas. O projeto irmão
`../loom-dl-extension` já explora esse caminho e continua válido como experimento,
mas **não é o caminho deste repo**.

## Pré-requisito

Não começar antes do merge da `main` e da validação final do layout numerado. Fase de
empacotamento com o motor ainda mudando é retrabalho garantido.
