import os
import sys
import subprocess
import shutil
import tempfile
import re
import platform

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

def detect_gpu_vendor():
    """Detecta o fabricante da GPU principal do sistema"""
    if platform.system() != 'Windows':
        return "unknown"

    try:
        # Usar o comando WMIC para obter informações sobre a GPU
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        # Executar o comando WMIC para obter informações sobre a GPU
        result = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "name"],
            capture_output=True,
            text=True,
            startupinfo=startupinfo
        )

        if result.returncode == 0:
            output = result.stdout.lower()

            # Verificar o fabricante com base no nome da GPU
            if "nvidia" in output:
                return "nvidia"
            elif "amd" in output or "radeon" in output or "ati" in output:
                return "amd"
            elif "intel" in output:
                return "intel"
    except Exception as e:
        print(f"Erro ao detectar GPU: {str(e)}")

    return "unknown"

def has_nvenc():
    """Verifica se o sistema tem suporte a NVENC (NVIDIA)"""
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

def has_amf():
    """Verifica se o sistema tem suporte a AMF (AMD)"""
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

        # Teste: tenta codificar um frame usando AMF
        test_cmd = [
            ffmpeg_path,
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
            "-c:v", "h264_amf", "-f", "null", "-"
        ]
        result = subprocess.run(test_cmd, capture_output=True, text=True, startupinfo=startupinfo)

        # Se o comando for bem-sucedido, AMF está disponível
        if result.returncode == 0:
            return True

        # Verificar se h264_amf está listado nos codificadores
        encoders_result = subprocess.run([ffmpeg_path, "-encoders"], capture_output=True, text=True, startupinfo=startupinfo)
        encoders_output = encoders_result.stdout + encoders_result.stderr

        return "h264_amf" in encoders_output
    except Exception as e:
        print(f"Erro ao verificar AMF: {str(e)}")
        return False

def has_qsv():
    """Verifica se o sistema tem suporte a QuickSync (Intel)"""
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

        # Teste: tenta codificar um frame usando QSV
        test_cmd = [
            ffmpeg_path,
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
            "-c:v", "h264_qsv", "-f", "null", "-"
        ]
        result = subprocess.run(test_cmd, capture_output=True, text=True, startupinfo=startupinfo)

        # Se o comando for bem-sucedido, QSV está disponível
        if result.returncode == 0:
            return True

        # Verificar se h264_qsv está listado nos codificadores
        encoders_result = subprocess.run([ffmpeg_path, "-encoders"], capture_output=True, text=True, startupinfo=startupinfo)
        encoders_output = encoders_result.stdout + encoders_result.stderr

        return "h264_qsv" in encoders_output
    except Exception as e:
        print(f"Erro ao verificar QSV: {str(e)}")
        return False

def test_nvenc_preset(preset):
    """Testa se um preset específico do NVENC é suportado"""
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

        # Teste rápido para verificar se o preset é suportado
        test_cmd = [
            ffmpeg_path,
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
            "-c:v", "h264_nvenc", "-preset", preset, "-f", "null", "-"
        ]
        result = subprocess.run(test_cmd, capture_output=True, text=True, startupinfo=startupinfo)
        return result.returncode == 0
    except Exception:
        return False

def get_encoder_params(encoder_name, speed_profile="balanced"):
    """Retorna os parâmetros de codificação com base no codificador e no perfil de velocidade

    Perfis disponíveis:
    - 'fast': Prioriza velocidade sobre qualidade
    - 'balanced': Equilíbrio entre velocidade e qualidade
    - 'quality': Prioriza qualidade sobre velocidade
    """
    # Definir parâmetros para cada codificador e perfil de velocidade
    if encoder_name == "h264_nvenc":  # NVIDIA
        if speed_profile == "fast":
            # Testar diferentes presets em ordem de preferência
            preset = "p2"  # Primeira opção
            if not test_nvenc_preset("p2"):
                # Se p2 não for suportado, tentar p3
                if test_nvenc_preset("p3"):
                    preset = "p3"
                # Se nenhum preset p* for suportado, usar preset nomeado
                elif test_nvenc_preset("fast"):
                    preset = "fast"
                else:
                    # Fallback para o preset mais compatível
                    preset = "default"

            print(f"Usando preset NVENC: {preset} para perfil rápido")
            # Otimizado para máxima velocidade
            return ["-c:v", "h264_nvenc", "-preset", preset, "-rc:v", "vbr", "-cq", "32",
                    "-b:v", "6M", "-profile:v", "high", "-level:v", "4.2",
                    "-spatial-aq", "0", "-temporal-aq", "0", "-refs", "1", "-b_ref_mode", "0"]
        elif speed_profile == "balanced":
            # Testar diferentes presets em ordem de preferência
            preset = "p4"  # Primeira opção
            if not test_nvenc_preset("p4"):
                # Se p4 não for suportado, tentar p3
                if test_nvenc_preset("p3"):
                    preset = "p3"
                # Se nenhum preset p* for suportado, usar preset nomeado
                elif test_nvenc_preset("medium"):
                    preset = "medium"
                else:
                    # Fallback para o preset mais compatível
                    preset = "default"

            print(f"Usando preset NVENC: {preset} para perfil balanceado")
            # Otimizado para equilíbrio entre velocidade e qualidade, mas priorizando velocidade
            return ["-c:v", "h264_nvenc", "-preset", preset, "-rc:v", "vbr", "-cq", "26",
                    "-b:v", "8M", "-profile:v", "high", "-level:v", "4.2",
                    "-spatial-aq", "0", "-temporal-aq", "0", "-refs", "2", "-b_ref_mode", "0"]
        else:  # quality
            # Testar diferentes presets em ordem de preferência
            preset = "p7"  # Primeira opção
            if not test_nvenc_preset("p7"):
                # Se p7 não for suportado, tentar p6
                if test_nvenc_preset("p6"):
                    preset = "p6"
                # Se nenhum preset p* for suportado, usar preset nomeado
                elif test_nvenc_preset("slow"):
                    preset = "slow"
                else:
                    # Fallback para o preset mais compatível
                    preset = "default"

            print(f"Usando preset NVENC: {preset} para perfil de alta qualidade")
            # Otimizado para alta qualidade, mas ainda mantendo boa velocidade
            return ["-c:v", "h264_nvenc", "-preset", preset, "-rc:v", "vbr", "-cq", "20",
                    "-b:v", "12M", "-profile:v", "high", "-level:v", "4.2",
                    "-spatial-aq", "1", "-temporal-aq", "1", "-refs", "3", "-b_ref_mode", "1"]

    elif encoder_name == "h264_amf":  # AMD
        if speed_profile == "fast":
            return ["-c:v", "h264_amf", "-quality", "speed", "-rc", "vbr_peak", "-qp_i", "26", "-qp_p", "28",
                    "-b:v", "8M", "-profile:v", "high"]
        elif speed_profile == "balanced":
            return ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "vbr_peak", "-qp_i", "22", "-qp_p", "24",
                    "-b:v", "10M", "-profile:v", "high"]
        else:  # quality
            return ["-c:v", "h264_amf", "-quality", "quality", "-rc", "vbr_peak", "-qp_i", "18", "-qp_p", "20",
                    "-b:v", "15M", "-profile:v", "high"]

    elif encoder_name == "h264_qsv":  # Intel
        if speed_profile == "fast":
            return ["-c:v", "h264_qsv", "-preset", "faster", "-b:v", "8M", "-profile:v", "high"]
        elif speed_profile == "balanced":
            return ["-c:v", "h264_qsv", "-preset", "medium", "-b:v", "10M", "-profile:v", "high"]
        else:  # quality
            return ["-c:v", "h264_qsv", "-preset", "slower", "-b:v", "15M", "-profile:v", "high"]

    elif encoder_name == "libx264":  # Software
        if speed_profile == "fast":
            return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                    "-profile:v", "high", "-level:v", "4.1"]
        elif speed_profile == "balanced":
            return ["-c:v", "libx264", "-preset", "medium", "-crf", "23",
                    "-profile:v", "high", "-level:v", "4.1"]
        else:  # quality
            return ["-c:v", "libx264", "-preset", "slow", "-crf", "18",
                    "-profile:v", "high", "-level:v", "4.1"]

    else:  # copy
        return ["-c:v", "copy"]

def get_video_encoder(speed_profile="balanced"):
    """Retorna o melhor codificador de vídeo disponível

    Args:
        speed_profile (str): Perfil de velocidade ('fast', 'balanced', 'quality')
    """
    # Detectar o fabricante da GPU
    gpu_vendor = detect_gpu_vendor()
    print(f"Fabricante da GPU detectado: {gpu_vendor}")

    # Verificar quais aceleradores de hardware estão disponíveis
    nvenc_available = has_nvenc()  # NVIDIA
    amf_available = has_amf()      # AMD
    qsv_available = has_qsv()      # Intel

    print(f"Codificadores disponíveis - NVIDIA: {nvenc_available}, AMD: {amf_available}, Intel: {qsv_available}")

    # Verificar se o libx264 está disponível (codificador por software)
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

    # Priorizar o codificador com base no fabricante da GPU
    if gpu_vendor == "amd" and amf_available:
        print("Usando codificador AMD AMF (hardware)")
        encoder_name = "h264_amf"
    elif gpu_vendor == "nvidia" and nvenc_available:
        print("Usando codificador NVIDIA NVENC (hardware)")
        encoder_name = "h264_nvenc"
    elif gpu_vendor == "intel" and qsv_available:
        print("Usando codificador Intel QuickSync (hardware)")
        encoder_name = "h264_qsv"
    # Fallback para qualquer acelerador disponível se o fabricante não for detectado
    elif amf_available:
        print("Usando codificador AMD AMF (hardware)")
        encoder_name = "h264_amf"
    elif nvenc_available:
        print("Usando codificador NVIDIA NVENC (hardware)")
        encoder_name = "h264_nvenc"
    elif qsv_available:
        print("Usando codificador Intel QuickSync (hardware)")
        encoder_name = "h264_qsv"
    elif libx264_available:
        print("Usando codificador libx264 (software)")
        encoder_name = "libx264"
    else:
        # Fallback para cópia (sem recodificação)
        print("Nenhum codificador disponível, usando cópia direta")
        encoder_name = "copy"

    # Obter os parâmetros de codificação com base no perfil de velocidade
    encoder_params = get_encoder_params(encoder_name, speed_profile)

    return encoder_name, encoder_params

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

    # Configurar o processo para capturar a saída em tempo real
    # Redirecionar stderr para stdout para garantir que todas as mensagens sejam capturadas
    # e que as mensagens de sincronização não interfiram com as mensagens de progresso
    # Usar -stats para garantir que as informações de progresso sejam exibidas em tempo real
    # Usar -loglevel verbose para garantir que todas as informações sejam exibidas
    cmd.extend(["-loglevel", "verbose", "-stats", "-progress", "pipe:1"])

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Redirecionar stderr para stdout
        universal_newlines=False,  # Usar bytes para evitar problemas de codificação
        startupinfo=startupinfo,
        bufsize=0  # Sem buffering para garantir saída em tempo real
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
