# Este arquivo transforma a pasta em um pacote Python
# e facilita as importações externas.

from .utils import (
    extrair_metadados, 
    limpar_nome_arquivo, 
    limpar_pasta, 
    HEADERS
)

from .downloader import processar_download
from .converter import converter_final
from .texto import montar_markdown, salvar_aula_md
from .youtube import baixar_youtube, eh_url_youtube, titulo_do_youtube, canal_do_youtube
from .vimeo import baixar_vimeo, eh_url_vimeo, titulo_do_vimeo, url_player_vimeo

# Caminhos do projeto, definidos num lugar só (services/caminhos.py) e
# reexportados aqui para manter a API pública: `from services import PASTA_...`
from .caminhos import PASTA_OUTPUT, PASTA_TEMP_RAIZ