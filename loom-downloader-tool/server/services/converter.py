import os
import subprocess
import shutil # <--- Importante para mover o arquivo
from .utils import limpar_nome_arquivo

# --- CORREÇÃO DO CAMINHO ---
dir_atual = os.path.dirname(os.path.abspath(__file__))
dir_server = os.path.dirname(dir_atual)
dir_raiz = os.path.dirname(dir_server)
PASTA_OUTPUT = os.path.join(dir_raiz, "output")

def converter_final(nome, pasta_rel, pasta_temp):
    try:
        # 1. Preparar Caminhos Finais
        if pasta_rel.startswith(os.sep): pasta_rel = pasta_rel[1:]
        
        dest_dir = os.path.join(PASTA_OUTPUT, pasta_rel)
        os.makedirs(dest_dir, exist_ok=True) # O Python cria a pasta (Isso já funciona)
        
        nome_final_mp4 = f"{limpar_nome_arquivo(nome)}.mp4"
        caminho_final_absoluto = os.path.join(dest_dir, nome_final_mp4)

        # 2. Caminho Temporário SIMPLES
        # Em vez de mandar o FFmpeg salvar lá longe, salvamos aqui perto
        nome_temp_simples = "temp_convertido.mp4"
        caminho_mp4_temp = os.path.join(pasta_temp, nome_temp_simples)

        print(f"\n⚙️  Estratégia de Conversão:")
        print(f"   1. Gerar: {nome_temp_simples} (na pasta temp)")
        print(f"   2. Mover para: {caminho_final_absoluto}")

        # Verifica se já existe no destino
        if os.path.exists(caminho_final_absoluto) and os.path.getsize(caminho_final_absoluto) > 1_000_000:
            print(f"⚠️  Arquivo já existe no destino. Pulando.")
            return True

        # 3. Executa FFmpeg (Salvando localmente com nome simples)
        cmd = [
            "ffmpeg", 
            "-y", 
            "-allowed_extensions", "ALL", 
            "-i", "master.m3u8", 
            "-c", "copy", 
            "-bsf:a", "aac_adtstoasc", 
            nome_temp_simples # <--- Agora é só o nome do arquivo, sem caminho louco
        ]
        
        # print("🎬 Rodando FFmpeg...")
        # stdout=subprocess.DEVNULL esconde o lixo visual se funcionar
        retcode = subprocess.call(cmd, cwd=pasta_temp, stderr=subprocess.DEVNULL)

        if retcode != 0:
            # Se falhar, tentamos de novo mostrando o erro
            print("⚠️ Primeira tentativa falhou, tentando modo verboso...")
            retcode = subprocess.call(cmd, cwd=pasta_temp)

        # 4. O Grande Movimento (Python assume o volante)
        if retcode == 0 and os.path.exists(caminho_mp4_temp):
            try:
                # Move o arquivo da temp para o output final
                shutil.move(caminho_mp4_temp, caminho_final_absoluto)
                
                print(f"✅ SUCESSO: Arquivo movido para {nome_final_mp4}")
                return True
            except Exception as e:
                print(f"❌ Erro ao mover arquivo: {e}")
                return False
        else:
            print(f"❌ Erro: O FFmpeg falhou ou não gerou o arquivo {nome_temp_simples}")
            return False

    except Exception as e:
        print(f"❌ ERRO GERAL: {e}")
        return False

# import os
# import subprocess
# from .utils import limpar_nome_arquivo

# PASTA_OUTPUT = "output"

# def converter_final(nome, pasta_rel, pasta_temp):
#     dest = os.path.join(PASTA_OUTPUT, pasta_rel)
#     os.makedirs(dest, exist_ok=True)
    
#     nome_final = f"{limpar_nome_arquivo(nome)}.mp4"
#     caminho_final = os.path.abspath(os.path.join(dest, nome_final))

#     # Isso vai imprimir o caminho exato no terminal
#     print(f"🔍 [DEBUG] Caminho Final: {caminho_final}")
    
#     # # Proteção contra sobrescrever arquivo bom
#     # if os.path.exists(caminho_final) and os.path.getsize(caminho_final) > 1000000: # Maior que 1MB
#     #     return True # Já existe, finge que converteu

#     cmd = [
#         "ffmpeg", "-y", "-allowed_extensions", "ALL", 
#         "-i", "master.m3u8", "-c", "copy", 
#         "-bsf:a", "aac_adtstoasc", caminho_final
#     ]
    
#     try:
#             # Nota: capture_output=True esconde o output do FFmpeg, a menos que dês print no erro
#             subprocess.run(cmd, cwd=pasta_temp, check=True, capture_output=True)
#             print("✅ Conversão concluída com sucesso.")
#             return True
#     except subprocess.CalledProcessError as e:
#         # Dica de Parceiro: Isso mostra o erro real do FFmpeg se falhar
#         print(f"❌ Erro no FFmpeg: {e.stderr.decode('utf-8')}")
#         return False
#     except Exception as e:
#         print(f"❌ Erro genérico: {e}")
#         return False