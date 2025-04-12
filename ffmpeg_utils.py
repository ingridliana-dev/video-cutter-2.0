import os
import sys
import subprocess
import shutil
import tempfile
import re

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

def has_nvenc():
    """Verifica se o sistema tem suporte a NVENC"""
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        return False

    try:
        # Executar FFmpeg com -encoders para verificar se h264_nvenc está disponível
        result = subprocess.run([ffmpeg_path, "-encoders"], capture_output=True, text=True)
        output = result.stdout + result.stderr

        # Procurar por h264_nvenc na saída
        return "h264_nvenc" in output and "nvenc" in output
    except Exception:
        return False

def get_video_encoder():
    """Retorna o melhor codificador de vídeo disponível"""
    if has_nvenc():
        return "h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p7", "-rc:v", "vbr", "-cq", "18",
                "-b:v", "15M", "-profile:v", "high", "-level:v", "4.2"]
    else:
        # Usar libx264 (codificador de software) como alternativa
        return "libx264", ["-c:v", "libx264", "-preset", "medium", "-crf", "23",
                 "-profile:v", "high", "-level:v", "4.1"]

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
