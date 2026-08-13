# Extensão standalone (tirar o servidor Python do caminho)

> **STATUS: SUPERSEDIDO em 13/08/2026.** A decisão foi tomada e é o **caminho B**
> (empacotar o que existe), detalhado em [[aplicativo-instalavel]].
>
> Este documento fica pelo levantamento da **opção A** (extensão pura, sem Python),
> que segue válido caso alguém queira reabrir a discussão — e pelo motivo de ela ter
> sido descartada: a fusão vídeo+áudio sem FFmpeg custa `ffmpeg.wasm` (pesado e
> lento) ou entregar faixas separadas.

## Por que

Hoje o uso exige: Python instalado, dependências, FFmpeg no PATH e um servidor
rodando num terminal. Para quem só quer baixar as aulas, é barreira demais — e
a maior parte dos problemas relatados nesta sessão foi de OPERAÇÃO do servidor
(morreu sozinho, subiu escondido, precisou reiniciar), não de download.

## Dois caminhos

**A. Extensão pura, sem servidor.** Já existe um projeto irmão em
`../loom-dl-extension` que resolve o mesmo problema sem Python e sem FFmpeg.
Ponto de partida óbvio: medir o que ele já faz e o que perderia.

O que este repo tem a mais e precisaria ser resolvido no navegador:

| Recurso | Onde vive hoje |
|---|---|
| Fusão vídeo+áudio | FFmpeg (`converter.py`) |
| Escolha da maior qualidade | `_parsear_master` por BANDWIDTH |
| Organização em pastas | `routes.py` + API de download do Chrome |
| Anexos do Skool | `skool.py` |
| Fila com concorrência 4 | `ThreadPoolExecutor` |

A fusão é o nó: sem FFmpeg, ou se usa WebAssembly (ffmpeg.wasm, pesado e lento)
ou se aceita baixar faixas separadas.

**B. Instalador estilo IDM.** Empacota servidor + FFmpeg num instalador único
que sobe sozinho com o Windows. Mantém tudo que funciona hoje e elimina só a
fricção de instalar e manter rodando.

## Antes de decidir

Medir quanto do acervo realmente precisa de fusão. Se boa parte das aulas já vem
em faixa única, o caminho A fica bem mais viável do que parece.

Nada disso deve começar antes de as pendências de correção estarem fechadas —
principalmente `worker-que-morre.md`, que ainda esconde uma causa desconhecida.
