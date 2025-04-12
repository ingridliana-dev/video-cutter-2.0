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
        # Configurar startupinfo para esconder a janela do console
        startupinfo = None
        if os.name == 'nt':  # Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        # Teste mais rigoroso: tenta codificar um frame usando NVENC
        test_cmd = [
            ffmpeg_path,
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
            "-c:v", "h264_nvenc", "-f", "null", "-"
        ]
        result = subprocess.run(test_cmd, capture_output=True, text=True, startupinfo=startupinfo)

        # Se o comando for bem-sucedido, NVENC está disponível
        if result.returncode == 0:
            return True

        # Verificar mensagens de erro específicas
        error_output = result.stderr.lower()
        if "cannot load nvencodeapi64.dll" in error_output or "driver" in error_output:
            return False

        # Verificar se h264_nvenc está listado nos codificadores
        encoders_result = subprocess.run([ffmpeg_path, "-encoders"], capture_output=True, text=True, startupinfo=startupinfo)
        encoders_output = encoders_result.stdout + encoders_result.stderr

        # Mesmo que esteja listado, só retorna True se o teste acima não falhou com erro de driver
        return "h264_nvenc" in encoders_output and "nvenc" in encoders_output
    except Exception as e:
        print(f"Erro ao verificar NVENC: {str(e)}")
        return False

def get_video_encoder():
    """Retorna o melhor codificador de vídeo disponível"""
    # Verificar se o NVENC está realmente disponível
    nvenc_available = has_nvenc()

    # Verificar se o libx264 está disponível
    ffmpeg_path = get_ffmpeg_path()
    libx264_available = False

    if ffmpeg_path:
        try:
            # Configurar startupinfo para esconder a janela do console
            startupinfo = None
            if os.name == 'nt':  # Windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            # Teste rápido para verificar se libx264 está disponível
            test_cmd = [
                ffmpeg_path,
                "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
                "-c:v", "libx264", "-f", "null", "-"
            ]
            result = subprocess.run(test_cmd, capture_output=True, text=True, startupinfo=startupinfo)
            libx264_available = (result.returncode == 0)
        except Exception:
            libx264_available = False

    # Prioridade: NVENC > libx264 > cópia
    if nvenc_available:
        print("Usando codificador NVENC (hardware)")
        return "h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p7", "-rc:v", "vbr", "-cq", "18",
                "-b:v", "15M", "-profile:v", "high", "-level:v", "4.2"]
    elif libx264_available:
        print("Usando codificador libx264 (software)")
        return "libx264", ["-c:v", "libx264", "-preset", "medium", "-crf", "23",
                 "-profile:v", "high", "-level:v", "4.1"]
    else:
        # Fallback para cópia (sem recodificação)
        print("Nenhum codificador disponível, usando cópia direta")
        return "copy", ["-c:v", "copy"]

def run_ffmpeg_command(cmd):
    """Executa um comando FFmpeg, substituindo 'ffmpeg' pelo caminho correto"""
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        raise FileNotFoundError("FFmpeg não encontrado no sistema ou no pacote da aplicação")

    # Substitui 'ffmpeg' pelo caminho completo
    if cmd[0] == "ffmpeg":
        cmd[0] = ffmpeg_path

    # Usar startupinfo para esconder a janela do console no Windows
    startupinfo = None
    if os.name == 'nt':  # Windows
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        startupinfo=startupinfo
    )

def run_ffprobe_command(cmd):
    """Executa um comando FFprobe, substituindo 'ffprobe' pelo caminho correto"""
    ffprobe_path = get_ffprobe_path()
    if not ffprobe_path:
        raise FileNotFoundError("FFprobe não encontrado no sistema ou no pacote da aplicação")

    # Substitui 'ffprobe' pelo caminho completo
    if cmd[0] == "ffprobe":
        cmd[0] = ffprobe_path

    # Usar startupinfo para esconder a janela do console no Windows
    startupinfo = None
    if os.name == 'nt':  # Windows
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        startupinfo=startupinfo
    )
