import requests
import re
import os
import html
import subprocess
import shutil  # Importante para apagar pastas
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURAÇÕES ---
PASTA_TEMP = "hls-temp"
PASTA_OUTPUT = "output"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.loom.com/",
    "Origin": "https://www.loom.com"
}

def limpar_nome_arquivo(nome):
    """Remove caracteres inválidos para nomes de arquivos"""
    nome = html.unescape(nome)
    nome_limpo = re.sub(r'[<>:"/\\|?*]', '', nome)
    return nome_limpo.strip()

def limpar_arquivos_temporarios():
    """Apaga a pasta temporária e todo o seu conteúdo"""
    print("🧹 Iniciando limpeza dos arquivos temporários...")
    if os.path.exists(PASTA_TEMP):
        try:
            shutil.rmtree(PASTA_TEMP)
            print(f"✨ Pasta '{PASTA_TEMP}' apagada com sucesso!")
        except Exception as e:
            print(f"⚠️ Aviso: Não foi possível apagar a pasta temporária completamente: {e}")
    else:
        print("⚠️ A pasta temporária já não existia.")

def extrair_metadados(embed_url):
    print(f"🔍 Acessando página: {embed_url}")
    try:
        response = requests.get(embed_url, headers=HEADERS)
        response.raise_for_status()
        conteudo = response.text

        # 1. Extrair Título
        match_title = re.search(r'<title>(.*?)</title>', conteudo)
        if match_title:
            titulo_bruto = match_title.group(1)
            titulo_limpo = limpar_nome_arquivo(titulo_bruto.replace(" | Loom", ""))
        else:
            titulo_limpo = "video_loom_sem_titulo"

        # 2. Extrair URL Mestra
        match_url = re.search(r'"url":"(https://[^"]+playlist\.m3u8[^"]+)"', conteudo)
        
        if match_url:
            url_mestra = match_url.group(1).replace('\\/', '/')
            return titulo_limpo, url_mestra
        else:
            print("❌ Não foi possível encontrar a URL .m3u8 no código da página.")
            return None, None

    except Exception as e:
        print(f"❌ Erro ao acessar a página: {e}")
        return None, None

def baixar_segmento(url, caminho_local):
    if os.path.exists(caminho_local) and os.path.getsize(caminho_local) > 0:
        return 
    try:
        with requests.get(url, headers=HEADERS, stream=True) as r:
            if r.status_code == 200:
                with open(caminho_local, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
    except:
        pass

def processar_download(url_master, titulo):
    print(f"🎬 Título detectado: {titulo}")
    print("🚀 Iniciando download dos segmentos...")
    
    os.makedirs(PASTA_TEMP, exist_ok=True)
    
    # 1. Baixar Master Playlist
    try:
        master_content = requests.get(url_master, headers=HEADERS).text
    except:
        print("❌ Erro ao baixar playlist master.")
        return False

    base_url = url_master.rsplit('/', 1)[0] + '/'
    assinatura = urlparse(url_master).query

    # 2. Identificar Melhor Video e Audio
    videos = re.findall(r'#EXT-X-STREAM-INF:.*BANDWIDTH=(\d+).*\n(.*\.m3u8)', master_content)
    audio_match = re.search(r'TYPE=AUDIO.*URI="(.*?)"', master_content)
    
    if not videos or not audio_match:
        print("❌ Estrutura da playlist não reconhecida.")
        return False

    melhor_video = sorted(videos, key=lambda x: int(x[0]), reverse=True)[0][1]
    arquivo_audio = audio_match.group(1)

    filas_download = []
    
    def processar_sublista(nome_m3u8_remoto):
        url_lista = f"{base_url}{nome_m3u8_remoto}?{assinatura}"
        lista_content = requests.get(url_lista, headers=HEADERS).text
        
        linhas_locais = []
        for linha in lista_content.splitlines():
            linha = linha.strip()
            if ".ts" in linha:
                nome_ts = re.search(r'(.+?\.ts)', linha).group(1).strip()
                nome_ts_base = os.path.basename(nome_ts)
                
                if "Signature=" in linha:
                    url_ts = f"{base_url}{linha}"
                else:
                    url_ts = f"{base_url}{linha}?{assinatura}"
                
                caminho_ts = os.path.join(PASTA_TEMP, nome_ts_base)
                filas_download.append((url_ts, caminho_ts))
                linhas_locais.append(nome_ts_base)
            else:
                linhas_locais.append(linha)
        
        with open(os.path.join(PASTA_TEMP, nome_m3u8_remoto), "w") as f:
            f.write("\n".join(linhas_locais))

    processar_sublista(melhor_video)
    processar_sublista(arquivo_audio)
    
    with open(os.path.join(PASTA_TEMP, "master.m3u8"), "w") as f:
        f.write(master_content)

    print(f"⬇️ Baixando {len(filas_download)} segmentos...")
    with ThreadPoolExecutor(max_workers=10) as ex:
        ex.map(lambda p: baixar_segmento(p[0], p[1]), filas_download)
    
    return True

def converter_final(titulo, caminho_relativo=""):
    """
    Converte para MP4 e salva na pasta especificada pelo usuário (Curso/Modulo)
    """
    # Cria a pasta de saída baseada na estrutura: output / NomeCurso / NomeModulo
    pasta_final_destino = os.path.join(PASTA_OUTPUT, caminho_relativo)
    os.makedirs(pasta_final_destino, exist_ok=True)
    
    # Limpa o nome do arquivo final
    nome_arquivo = f"{limpar_nome_arquivo(titulo)}.mp4"
    caminho_final_absoluto = os.path.abspath(os.path.join(pasta_final_destino, nome_arquivo))
    
    print(f"⚙️ Convertendo para: {caminho_relativo}/{nome_arquivo}")
    
    cmd = [
        "ffmpeg", "-y", "-allowed_extensions", "ALL",
        "-i", "master.m3u8", 
        "-c", "copy", "-bsf:a", "aac_adtstoasc",
        caminho_final_absoluto
    ]
    
    try:
        subprocess.run(cmd, cwd=PASTA_TEMP, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"\n✅ SUCESSO! Salvo em: {caminho_final_absoluto}")
        return True
    except Exception as e:
        print(f"❌ Erro no FFmpeg: {e}")
        return False

# --- EXECUÇÃO ---
# URL do Embed
url_embed = "https://www.loom.com/embed/8db13ddd57974685979d7290c925dcec?autoplay=0&hide_owner=true&hide_share=true&hide_title=true&hideEmbedTopBar=true"

if __name__ == "__main__":
    titulo, url_mestra = extrair_metadados(url_embed)
    
    if titulo and url_mestra:
        # Se baixou com sucesso...
        if processar_download(url_mestra, titulo):
            # E se converteu com sucesso...
            sucesso_conversao = converter_final(titulo)
            
            if sucesso_conversao:
                # Só limpa se tudo correu bem
                limpar_arquivos_temporarios()
            else:
                print("⚠️ A limpeza foi abortada porque houve erro na conversão. Os arquivos temporários foram mantidos para análise.")