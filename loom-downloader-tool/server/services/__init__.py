# Este arquivo transforma a pasta em um pacote Python
# e facilita as importações externas.

from .utils import (
    extrair_metadados,
    limpar_nome_arquivo,
    cortar_preservando_extensao,
    prefixo_de_ordem,
    limite_do_nome,
    PISO_NOME,
    MAX_CAMINHO,
    limpar_pasta,
    HEADERS
)

from .downloader import processar_download
from .converter import converter_final
from .texto import (montar_markdown, salvar_aula_md, imagens_do_desc,
                    nome_local_da_imagem)
from .youtube import baixar_youtube, eh_url_youtube, titulo_do_youtube, canal_do_youtube
from .vimeo import baixar_vimeo, eh_url_vimeo, titulo_do_vimeo, url_player_vimeo
from .skool import baixar_skool, eh_url_skool_video, url_stream_skool, baixar_anexos
from .loom import baixar_loom, eh_url_loom, titulo_do_loom

from .registro import registrar_erro, limpar_erro

# Caminhos do projeto, definidos num lugar só (services/caminhos.py) e
# reexportados aqui para manter a API pública: `from services import PASTA_...`
from .caminhos import PASTA_OUTPUT, PASTA_TEMP_RAIZ, ARQUIVO_ERROS