# Diagnóstico e conserto — 2026-07-23

**Estado: RESOLVIDO.** O projeto voltou a funcionar. Uma linha era a causa raiz.

## Causa raiz

`server/services/utils.py:60` — regex de extração do `.m3u8`.

O Loom renomeou o arquivo da playlist. O regex exigia o nome **literal**
`playlist.m3u8`, mas o Loom hoje serve `playlist-multibitrate.m3u8`:

```
"__typename":"CloudfrontSignedUrlPayload",
"url":"https://luna.loom.com/id/<ID>/rev/<REV>/resource/hls/playlist-multibitrate.m3u8?Policy=..."
```

Regex antigo: `"url":"(https://[^"]+playlist\.m3u8[^"]+)"`  → **não casa**.

### Por que isso ficou invisível

`extrair_metadados` tem um `except Exception: return None, None` (utils.py:69) e,
mesmo sem exceção, retorna `url_m3u8 = None` quando o regex não casa. O título
continuava sendo extraído normalmente, então **a página era acessada com sucesso,
o nome do arquivo saía certo, e o download simplesmente nunca acontecia** — sem
nenhuma mensagem de erro. É exatamente a classe de falha silenciosa documentada
no `CLAUDE.md`.

## Conserto aplicado

`utils.py:60` — remover a exigência do nome literal:

```python
match_url = re.search(r'"url":"(https://[^"]+\.m3u8[^"]*)"', conteudo_html)
```

**Trade-off:** o anchor `playlist` foi removido em vez de virar
`playlist[^"]*\.m3u8`. Isso sobrevive a um novo rename pelo Loom, mas casaria com
outro `.m3u8` caso a página passe a conter mais de um. Hoje o HTML contém
**exatamente uma** ocorrência de `m3u8` (medido), então é seguro.

## Medições (saída literal)

Alvo: `https://www.loom.com/embed/7a0abb7d8ae14ab480f963cc2f49ec67`

| Verificação | Resultado |
|---|---|
| Regex antigo casa? | `False` |
| Regex novo casa? | `True` |
| `extrair_metadados` no código do repo | `OK` — título + m3u8 |
| Streams de vídeo no master | 2 — `BANDWIDTH` 1500000 / 3200000 |
| Stream de áudio | `mediaplaylist-audio.m3u8` — presente |
| Segmentos baixados | **75/75**, zero arquivos de 0 byte |
| `processar_download` | `True` — 37,1 s |
| `converter_final` | `True` — 1,5 s |

`ffprobe` do `.mp4` final (17,54 MB):

```
codec_name=h264
codec_type=video
width=1910
height=1080
codec_name=aac
codec_type=audio
duration=164.632000
size=18391414
```

Vídeo **e** áudio presentes, 1080p, duração coerente. Pipeline saudável de ponta a
ponta: master → seleção de bitrate → playlists separadas → segmentos paralelos →
FFmpeg `-c copy` → `.mp4`.

## Método

O E2E rodou com `PASTA_OUTPUT` redirecionado para o scratchpad
(`downloader.PASTA_OUTPUT` e `converter.PASTA_OUTPUT` sobrescritos em memória).
A pasta `output/` real do usuário não foi tocada.

O conserto foi validado por monkeypatch **antes** de editar o repo; só depois de
o `.mp4` existir e passar no `ffprobe` é que a linha foi alterada em disco.

## Não verificado

- **Camada 3 (extensão Chrome).** Depende de login no Skool. `content.js` e
  `manifest.json` não foram revisados nesta rodada.
- O regex de `content.js:14` que parseia o `document.title` do Skool pelo ponto
  médio `·` — se o Skool mudou o formato do título, a organização em pastas quebra
  sem quebrar o download.

## Pendências levantadas (NÃO consertadas — decisão do usuário)

1. **Falha silenciosa em `extrair_metadados`.** Foi o que fez este bug custar caro.
   Um `print`/log quando o regex não casa teria apontado a causa em segundos.
2. **Sem retry em `_baixar_segmento`** (`downloader.py:40-42`). Nesta medição os
   75/75 vieram, mas uma falha de rede vira buraco silencioso no vídeo.
3. **Limiar de 1 MB** (`downloader.py:63`) — aceita `.mp4` truncado como completo.
4. **Duplicação de `PASTA_OUTPUT`** em `downloader.py:11-14` e `converter.py:8-11`.
5. **Testes automatizados** — inexistentes. Uma fixture do HTML do Loom travaria
   esta regressão específica.
