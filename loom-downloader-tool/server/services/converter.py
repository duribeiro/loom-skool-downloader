import os
import subprocess
import shutil
from .utils import limpar_nome_arquivo
from .caminhos import PASTA_OUTPUT  # definição única, compartilhada com downloader.py

def converter_final(nome_arquivo, pasta_relativa_destino, pasta_temp_trabalho):
    """
    Converte os arquivos .ts baixados para um único .mp4.
    Estratégia: Gera o arquivo na pasta temporária (para evitar erros de caminho longo)
    e depois move para a pasta final de destino.
    """
    try:
        # --- 2. PREPARAR DESTINO FINAL ---
        # Remove a barra inicial se existir (ex: "\Curso" -> "Curso")
        if pasta_relativa_destino.startswith(os.sep): 
            pasta_relativa_destino = pasta_relativa_destino[1:]
        
        # Cria o caminho absoluto onde o arquivo final deve morar
        caminho_pasta_final = os.path.join(PASTA_OUTPUT, pasta_relativa_destino)
        os.makedirs(caminho_pasta_final, exist_ok=True) 
        
        nome_mp4_final = f"{limpar_nome_arquivo(nome_arquivo)}.mp4"
        caminho_final_absoluto = os.path.join(caminho_pasta_final, nome_mp4_final)

        # Verificação de redundância (Double Check)
        # O downloader já faz isso, mas é bom garantir antes de processar vídeo pesado
        if os.path.exists(caminho_final_absoluto) and os.path.getsize(caminho_final_absoluto) > 1_000_000:
            print(f"⚠️  Arquivo já existe no destino. Conversão pulada: {nome_mp4_final}")
            return True

        # --- 3. CAMINHO TEMPORÁRIO (O TRUQUE) ---
        # Salvamos com um nome curto dentro da pasta temp para o FFmpeg não reclamar
        nome_temp_curto = "temp_convertido.mp4"
        caminho_mp4_temp = os.path.join(pasta_temp_trabalho, nome_temp_curto)

        # --- 4. EXECUTAR FFMPEG ---
        comando_ffmpeg = [
            "ffmpeg", 
            "-y",                           # Sobrescrever se existir
            "-allowed_extensions", "ALL",   # Permitir todas as extensões na playlist
            "-i", "master.m3u8",            # Arquivo de entrada (playlist principal)
            "-c", "copy",                   # Copiar streams (não re-codificar, é muito mais rápido)
            "-bsf:a", "aac_adtstoasc",      # Filtro de áudio necessário para converter .ts para .mp4
            nome_temp_curto                 # Saída local
        ]
        
        # Tenta rodar silencioso (DEVNULL) para não poluir o terminal
        codigo_retorno = subprocess.call(comando_ffmpeg, cwd=pasta_temp_trabalho, stderr=subprocess.DEVNULL)

        if codigo_retorno != 0:
            print("⚠️  Primeira tentativa falhou, tentando modo verboso para ver o erro...")
            # Se falhar, roda mostrando o erro
            codigo_retorno = subprocess.call(comando_ffmpeg, cwd=pasta_temp_trabalho)

        # --- 5. MOVER PARA O FINAL ---
        if codigo_retorno == 0 and os.path.exists(caminho_mp4_temp):
            try:
                shutil.move(caminho_mp4_temp, caminho_final_absoluto)
                print(f"✅ SUCESSO: Vídeo salvo em '{nome_mp4_final}'")
                return True
            except Exception as erro_move:
                print(f"❌ Erro ao mover arquivo final: {erro_move}")
                return False
        else:
            print(f"❌ Erro: O FFmpeg falhou na conversão.")
            return False

    except Exception as erro_geral:
        print(f"❌ ERRO GERAL no converter: {erro_geral}")
        return False