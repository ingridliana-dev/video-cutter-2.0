import os
import sys
import subprocess
import shutil
import tempfile

def get_base_dir():
    """Retorna o diretório base da aplicação, considerando se estamos em um executável PyInstaller ou não"""
    if getattr(sys, 'frozen', False):
        # Estamos em um executável PyInstaller
        return os.path.dirname(sys.executable)
    else:
        # Estamos em um script Python normal
        return os.path.dirname(os.path.abspath(__file__))

def get_ffmpeg_path():
    """Retorna o caminho para o executável do FFmpeg"""
    # Primeiro, verifica se o FFmpeg está no PATH do sistema
    ffmpeg_system = shutil.which("ffmpeg")
    if ffmpeg_system:
        return ffmpeg_system
    
    # Se não estiver no PATH, verifica se temos uma versão incluída
    base_dir = get_base_dir()
    ffmpeg_bundled = os.path.join(base_dir, "ffmpeg", "bin", "ffmpeg.exe")
    
    if os.path.exists(ffmpeg_bundled):
        return ffmpeg_bundled
    
    # Se não encontrar em nenhum lugar, retorna None
    return None

def get_ffprobe_path():
    """Retorna o caminho para o executável do FFprobe"""
    # Primeiro, verifica se o FFprobe está no PATH do sistema
    ffprobe_system = shutil.which("ffprobe")
    if ffprobe_system:
        return ffprobe_system
    
    # Se não estiver no PATH, verifica se temos uma versão incluída
    base_dir = get_base_dir()
    ffprobe_bundled = os.path.join(base_dir, "ffmpeg", "bin", "ffprobe.exe")
    
    if os.path.exists(ffprobe_bundled):
        return ffprobe_bundled
    
    # Se não encontrar em nenhum lugar, retorna None
    return None

def check_ffmpeg():
    """Verifica se o FFmpeg está disponível e retorna True/False"""
    ffmpeg_path = get_ffmpeg_path()
    ffprobe_path = get_ffprobe_path()
    
    return ffmpeg_path is not None and ffprobe_path is not None

def run_ffmpeg_command(cmd):
    """Executa um comando FFmpeg, substituindo 'ffmpeg' pelo caminho correto"""
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        raise FileNotFoundError("FFmpeg não encontrado no sistema ou no pacote da aplicação")
    
    # Substitui 'ffmpeg' pelo caminho completo
    if cmd[0] == "ffmpeg":
        cmd[0] = ffmpeg_path
    
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

def run_ffprobe_command(cmd):
    """Executa um comando FFprobe, substituindo 'ffprobe' pelo caminho correto"""
    ffprobe_path = get_ffprobe_path()
    if not ffprobe_path:
        raise FileNotFoundError("FFprobe não encontrado no sistema ou no pacote da aplicação")
    
    # Substitui 'ffprobe' pelo caminho completo
    if cmd[0] == "ffprobe":
        cmd[0] = ffprobe_path
    
    return subprocess.run(cmd, capture_output=True, text=True)
