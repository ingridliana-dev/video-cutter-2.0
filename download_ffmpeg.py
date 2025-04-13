import os
import sys
import urllib.request
import zipfile
import shutil
import tempfile

def download_ffmpeg():
    """Baixa e extrai o FFmpeg para a pasta ffmpeg"""
    print("Baixando FFmpeg...")
    
    # URL do FFmpeg (versão estática para Windows)
    ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    
    # Criar pasta temporária
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "ffmpeg.zip")
    
    try:
        # Baixar o arquivo
        print(f"Baixando de {ffmpeg_url}...")
        urllib.request.urlretrieve(ffmpeg_url, zip_path)
        
        # Extrair o arquivo
        print("Extraindo arquivo...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Encontrar a pasta extraída (geralmente tem um nome como ffmpeg-master-...)
        extracted_dirs = [d for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d)) and d.startswith("ffmpeg")]
        if not extracted_dirs:
            print("Erro: Não foi possível encontrar a pasta do FFmpeg após a extração")
            return False
        
        extracted_dir = os.path.join(temp_dir, extracted_dirs[0])
        
        # Criar a pasta ffmpeg no diretório atual
        ffmpeg_dir = os.path.join(os.getcwd(), "ffmpeg")
        if os.path.exists(ffmpeg_dir):
            shutil.rmtree(ffmpeg_dir)
        
        # Copiar os arquivos necessários
        print("Copiando arquivos...")
        shutil.copytree(extracted_dir, ffmpeg_dir)
        
        print(f"FFmpeg baixado e extraído com sucesso para {ffmpeg_dir}")
        return True
        
    except Exception as e:
        print(f"Erro ao baixar ou extrair o FFmpeg: {str(e)}")
        return False
    
    finally:
        # Limpar arquivos temporários
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

if __name__ == "__main__":
    download_ffmpeg()
