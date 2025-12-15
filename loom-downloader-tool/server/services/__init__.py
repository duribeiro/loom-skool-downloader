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

# Define uma constante global para o projeto todo usar
PASTA_TEMP_RAIZ = "hls-temp"