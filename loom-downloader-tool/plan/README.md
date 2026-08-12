# Registro durável do projeto

Onde ficam as medições, as decisões e o que ainda falta. A regra é simples:
**afirmação sem medição não entra aqui.** Quando algo for suposição, tem que
estar escrito que é suposição.

## Estrutura

| Pasta | O que guarda |
|---|---|
| [`a-fazer/`](a-fazer/) | Trabalho aberto. Cada arquivo diz o problema, o que já se sabe e o que falta medir. |
| [`feito/`](feito/) | Trabalho concluído. Fica como registro — inclusive dos erros de percurso. |

Um documento sai de `a-fazer/` para `feito/` quando a mudança **está no código e
foi verificada**. Escrito e não testado continua em `a-fazer/`, com a pendência
explícita.

## Aberto

| Documento | Assunto |
|---|---|
| [barra-de-progresso.md](a-fazer/barra-de-progresso.md) | Barra parada em 100% enquanto ainda há trabalho; progresso real do ffmpeg |
| [worker-que-morre.md](a-fazer/worker-que-morre.md) | Duas aulas cujo worker estoura — a blindagem já existe, falta a causa |
| [limpeza-orfaos-ytdlp.md](a-fazer/limpeza-orfaos-ytdlp.md) | ~1 GB de `._yt_*` órfãos de reinícios de servidor |
| [outras-comunidades.md](a-fazer/outras-comunidades.md) | Pastas de canal do YouTube nas 4 comunidades não medidas |
| [extensao-standalone.md](a-fazer/extensao-standalone.md) | Tirar a dependência do servidor Python |

## Concluído

| Documento | Assunto |
|---|---|
| [video-em-post-fixado.md](feito/video-em-post-fixado.md) | 52 de 280 aulas com vídeo em post fixado, perdidas em silêncio |
| [benchmark-concorrencia.md](feito/benchmark-concorrencia.md) | Concorrência 4, medida; o ruído da máquina era 11% |
| [brechas-anexos-e-video-skool.md](feito/brechas-anexos-e-video-skool.md) | Anexos e vídeo hospedado no Skool |
| [baixar-comunidade-inteira.md](feito/baixar-comunidade-inteira.md) | Enfileirar todos os cursos de uma comunidade |
| [limpeza-md-placeholder-office-hours.md](feito/limpeza-md-placeholder-office-hours.md) | 20 `.md` placeholder removidos |

## Por que os erros ficam registrados

Vários documentos aqui têm uma seção contando o que se concluiu errado antes de
medir direito. Isso é de propósito. Nesta base já aconteceu de:

- um detector reportar **0 ocorrências** num curso onde uma já estava provada,
  por seguir um redirect que trocava a aula pedida;
- um benchmark declarar vencedor sobre ruído de 11% que ninguém tinha medido;
- a documentação mandar reintroduzir uma duplicação que um refactor havia
  eliminado, porque os números de linha estavam todos errados.

Guardar só a conclusão final faria o próximo leitor repetir o caminho.
