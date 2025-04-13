import sys
import os
import subprocess
import traceback
import random
import time
import shutil
import threading
import select
import io
from pathlib import Path
import ffmpeg_utils
import re

print("Iniciando aplicação...")

try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton,
                                QVBoxLayout, QHBoxLayout, QWidget, QFileDialog,
                                QLineEdit, QSpinBox, QProgressBar, QTextEdit, QGroupBox,
                                QMessageBox, QColorDialog, QDoubleSpinBox, QFrame, QGridLayout,
                                QFormLayout)
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QProcess
    from PyQt5.QtGui import QColor, QIcon
    print("PyQt5 importado com sucesso!")
except Exception as e:
    print(f"Erro ao importar PyQt5: {e}")
    traceback.print_exc()

class VideoCutterWorker(QThread):
    progress_signal = pyqtSignal(float)  # Progresso geral (alterado para float para maior precisão)
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)  # Novo sinal para atualizar o status da codificação
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, input_file, image_file, selo_file, output_prefix, start_index,
                 min_duration, max_duration, output_directory=None,
                 chroma_color="0x00d600", similarity=0.30, blend=0.35):
        super().__init__()
        self.input_file = input_file
        self.image_file = image_file
        self.selo_file = selo_file
        self.output_prefix = output_prefix
        self.start_index = start_index
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.output_directory = output_directory
        self.chroma_color = chroma_color
        self.similarity = similarity
        self.blend = blend
        self.is_running = True
        self.process = None

        # Variáveis para controle de progresso (acessíveis pela interface)
        self.duration = 0  # Duração da parte atual sendo processada
        self.total_duration = 0  # Duração total do vídeo
        self.current_time = 0  # Tempo atual de processamento

    def run(self):
        try:
            # Inicializar o progresso em 0% no início do processamento
            self.progress_signal.emit(0.0)
            print(f"[{time.strftime('%H:%M:%S')}] INICIANDO PROCESSAMENTO - PROGRESSO: 0.0%")

            # Verificar se os arquivos existem
            if not os.path.isfile(self.input_file):
                self.error_signal.emit(f"Arquivo de entrada não encontrado: {self.input_file}")
                return

            if not os.path.isfile(self.image_file):
                self.error_signal.emit(f"Arquivo de imagem não encontrado: {self.image_file}")
                return

            if not os.path.isfile(self.selo_file):
                self.error_signal.emit(f"Arquivo de selo não encontrado: {self.selo_file}")
                return

            # Definir diretório de saída
            if not self.output_directory:
                self.output_directory = os.path.dirname(self.input_file)
                if not self.output_directory:
                    self.output_directory = os.getcwd()

            # Verificar se o diretório de saída existe
            if not os.path.isdir(self.output_directory):
                try:
                    os.makedirs(self.output_directory)
                except Exception as e:
                    self.error_signal.emit(f"Erro ao criar diretório de saída: {str(e)}")
                    return

            # Obter a duração total do vídeo principal
            self.log_signal.emit("Obtendo informações do vídeo principal...")
            total_duration = self.get_video_duration(self.input_file)
            if total_duration <= 0:
                self.error_signal.emit("Não foi possível obter a duração do vídeo principal ou a duração é inválida.")
                return
            # Armazenar a duração total para uso posterior
            self.total_duration = total_duration
            print(f"[{time.strftime('%H:%M:%S')}] DEFININDO TOTAL_DURATION: {total_duration}")
            self.log_signal.emit(f"Duração total do vídeo: {total_duration:.2f} segundos")

            # Obter a resolução do vídeo principal
            input_width, input_height = self.get_video_resolution(self.input_file)
            self.log_signal.emit(f"Resolução do vídeo principal: {input_width}x{input_height}")

            # Obter a resolução da imagem de capa
            cover_width, cover_height = self.get_image_resolution(self.image_file)
            self.log_signal.emit(f"Resolução da imagem de capa: {cover_width}x{cover_height}")

            # Obter a duração e resolução do vídeo do selo
            selo_duration = self.get_video_duration(self.selo_file)
            if selo_duration <= 0:
                self.error_signal.emit("Não foi possível obter a duração do vídeo do selo ou a duração é inválida.")
                return
            self.log_signal.emit(f"Duração do vídeo do selo: {selo_duration:.2f} segundos")

            selo_width, selo_height = self.get_video_resolution(self.selo_file)
            self.log_signal.emit(f"Resolução do vídeo do selo: {selo_width}x{selo_height}")

            # Verificar compatibilidade de resolução e determinar quais arquivos precisam ser redimensionados
            resolution_info = self.check_resolution_compatibility(
                (input_width, input_height),
                (cover_width, cover_height),
                (selo_width, selo_height)
            )

            # Informar ao usuário sobre a orientação do vídeo
            if resolution_info['is_vertical']:
                self.log_signal.emit("Orientação do vídeo: Vertical (retrato)")
            else:
                self.log_signal.emit("Orientação do vídeo: Horizontal (paisagem)")

            # Informar sobre redimensionamentos necessários
            if resolution_info['cover_needs_resize']:
                self.log_signal.emit("A imagem de capa será redimensionada para corresponder à resolução do vídeo.")
            if resolution_info['selo_needs_resize']:
                self.log_signal.emit("O vídeo do selo será redimensionado para corresponder à resolução do vídeo.")

            # Inicializar o tempo atual e o número da parte
            current_time = 0
            part_number = self.start_index
            total_parts = 0

            # Enviar progresso inicial
            self.progress_signal.emit(0.0)
            print(f"[{time.strftime('%H:%M:%S')}] PROGRESSO INICIAL: 0.0%")

            # Calcular o número total estimado de partes para a barra de progresso
            avg_duration = (self.min_duration + self.max_duration) / 2
            estimated_parts = int(total_duration / avg_duration) + 1

            while current_time < total_duration and self.is_running:
                # Gerar duração aleatória entre os limites definidos
                duration = random.randint(self.min_duration, self.max_duration)

                # Se a duração ultrapassar o fim do vídeo, ajusta para terminar no tempo total
                if current_time + duration > total_duration:
                    duration = total_duration - current_time

                # Armazenar a duração da parte atual para uso posterior
                self.duration = duration
                # Armazenar o tempo atual para uso posterior
                self.current_time = current_time
                print(f"[{time.strftime('%H:%M:%S')}] DEFININDO DURATION: {duration}, CURRENT_TIME: {current_time}")

                # Garante que a duração mínima seja respeitada, a menos que seja o último segmento e menor que min_duration
                if duration < self.min_duration and (current_time + duration) < total_duration:
                    duration = self.min_duration
                    # Recalcula caso o ajuste mínimo ultrapasse o total
                    if current_time + duration > total_duration:
                        duration = total_duration - current_time

                # Garante que o clipe tenha pelo menos 10 segundos + duração do selo para a sobreposição ocorrer
                if duration < (10 + selo_duration):
                    self.log_signal.emit(f"Aviso: A duração do clipe ({duration} s) é menor que 10s + duração do selo ({selo_duration} s). O selo pode não ser exibido completamente neste clipe (Parte {part_number}).")

                # Construir o nome do arquivo de saída
                output_file = os.path.join(self.output_directory, f"{self.output_prefix}{part_number}.mp4")

                self.log_signal.emit(f"Processando parte {part_number} (tempo: {current_time:.2f}s, duração: {duration:.2f}s)...")

                # Construir o comando FFmpeg com base nas informações de resolução
                filter_complex = [
                    f"[0:v]trim=start={current_time}:duration={duration},setpts=PTS-STARTPTS[segment];"
                ]

                # Adicionar redimensionamento para o selo se necessário
                if resolution_info['selo_needs_resize']:
                    filter_complex.append(f"[2:v]format=rgba,{resolution_info['resize_filters']['selo']},setpts=PTS-STARTPTS[selo_rgba];")
                else:
                    filter_complex.append(f"[2:v]format=rgba,setpts=PTS-STARTPTS[selo_rgba];")

                # Aplicar chroma key ao selo
                filter_complex.append(f"[selo_rgba]colorkey=color={self.chroma_color}:similarity={self.similarity}:blend={self.blend}[selo_chroma];")
                filter_complex.append(f"[selo_chroma]tpad=start_duration=10:color=black@0.0[selo_padded];")

                # Sobrepor o selo ao segmento de vídeo
                filter_complex.append(f"[segment][selo_padded]overlay=(W-w)/2:(H-h)/2:eof_action=pass[main_with_selo];")

                # Adicionar redimensionamento para a imagem de capa se necessário
                if resolution_info['cover_needs_resize']:
                    # Primeiro redimensionar a imagem de capa
                    filter_complex.append(f"[1:v]{resolution_info['resize_filters']['cover']}[cover_resized];")
                    # Depois sobrepor a imagem redimensionada
                    filter_complex.append(f"[main_with_selo][cover_resized]overlay=(W-w)/2:(H-h)/2:enable='eq(n,0)'[with_image];")
                else:
                    # Usar a imagem original se não precisar de redimensionamento
                    filter_complex.append(f"[main_with_selo][1:v]overlay=(W-w)/2:(H-h)/2:enable='eq(n,0)'[with_image];")

                # Ajustar o tamanho da fonte com base na resolução do vídeo
                input_width, input_height = resolution_info['input_resolution']
                # Calcular um tamanho de fonte proporcional à resolução
                # Para 1080x1920, usamos fonte 150. Para outras resoluções, ajustamos proporcionalmente
                font_size = int(min(input_width, input_height) * 0.14)  # 150 / 1080 ≈ 0.14

                filter_complex.append(f"[with_image]drawtext=text='Parte {part_number}':fontfile='C\:/Windows/Fonts/arial.ttf':fontsize={font_size}:fontcolor=white:borderw={font_size//7}:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2:enable='eq(n,0)'[final_v];")
                filter_complex.append(f"[0:a]atrim=start={current_time}:duration={duration},asetpts=PTS-STARTPTS[final_a]")

                filter_complex_str = "".join(filter_complex)

                # Verificar qual codificador usar (hardware ou software)
                encoder_name, encoder_params = ffmpeg_utils.get_video_encoder()
                if encoder_name == "h264_nvenc":
                    self.log_signal.emit("Usando aceleração de hardware NVIDIA para codificação de vídeo")
                elif encoder_name == "h264_amf":
                    self.log_signal.emit("Usando aceleração de hardware AMD para codificação de vídeo")
                elif encoder_name == "h264_qsv":
                    self.log_signal.emit("Usando aceleração de hardware Intel QuickSync para codificação de vídeo")
                else:
                    self.log_signal.emit(f"Usando codificador de vídeo por software: {encoder_name}")
                # Inicializar a área de status com uma mensagem vazia
                # A área será preenchida com informações reais de codificação quando o processo começar
                self.status_signal.emit("")

                # Configurar parâmetros base do comando
                ffmpeg_cmd = [
                    "ffmpeg"
                ]

                # Adicionar acelerador de hardware apropriado com base no codificador
                # Detectar o fabricante da GPU
                gpu_vendor = ffmpeg_utils.detect_gpu_vendor()

                # Configurar o acelerador de hardware com base no fabricante da GPU e no codificador
                if encoder_name == "h264_nvenc":
                    ffmpeg_cmd.extend(["-hwaccel", "cuda"])
                elif encoder_name == "h264_amf":
                    ffmpeg_cmd.extend(["-hwaccel", "d3d11va"])
                elif encoder_name == "h264_qsv":
                    ffmpeg_cmd.extend(["-hwaccel", "qsv"])
                elif gpu_vendor == "amd":
                    # Fallback para AMD se o codificador não for específico
                    ffmpeg_cmd.extend(["-hwaccel", "d3d11va"])
                elif gpu_vendor == "nvidia":
                    # Fallback para NVIDIA se o codificador não for específico
                    ffmpeg_cmd.extend(["-hwaccel", "cuda"])
                elif gpu_vendor == "intel":
                    # Fallback para Intel se o codificador não for específico
                    ffmpeg_cmd.extend(["-hwaccel", "qsv"])

                # Adicionar o resto dos parâmetros
                ffmpeg_cmd.extend([
                    "-i", self.input_file,
                    "-i", self.image_file,
                    "-i", self.selo_file,
                    "-filter_complex", filter_complex_str,
                    "-map", "[final_v]", "-map", "[final_a]"
                ])

                # Adicionar parâmetros do codificador de vídeo
                ffmpeg_cmd.extend(encoder_params)

                # Adicionar parâmetros de áudio e finalização
                ffmpeg_cmd.extend([
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                    output_file
                ])

                # Executar o comando FFmpeg
                try:
                    # Os parâmetros de progresso agora são adicionados no ffmpeg_utils.py
                    # para garantir que sejam aplicados a todos os comandos FFmpeg

                    # Iniciar o processo FFmpeg
                    self.process = ffmpeg_utils.run_ffmpeg_command(ffmpeg_cmd)

                    # Criar uma thread para ler a saída do FFmpeg e mostrar no log
                    def read_output():
                        # Variável para controlar a exibição de informações de progresso
                        show_progress = True
                        # Contador para limitar a quantidade de linhas exibidas (para não sobrecarregar o log)
                        frame_counter = 0
                        # Variável para armazenar a última linha de progresso exibida
                        last_progress_line = ""
                        # Lista para armazenar as últimas linhas de progresso (para exibição na área de status)
                        progress_lines = []

                        while self.process.poll() is None and self.is_running:
                            try:
                                # Ler uma linha da saída de erro (onde o FFmpeg escreve o progresso)
                                # Usar read(1) para ler byte a byte e garantir que a saída seja em tempo real
                                line_bytes = b''
                                # Adicionar um timeout para não ficarmos presos em uma linha
                                start_time = time.time()
                                while True:
                                    # Verificar se temos dados disponíveis para leitura
                                    # Agora lemos de stdout em vez de stderr porque redirecionamos stderr para stdout
                                    if self.process.stdout.readable():
                                        try:
                                            byte = self.process.stdout.read(1)
                                            if not byte or byte == b'\n':
                                                break
                                            line_bytes += byte
                                        except Exception as e:
                                            print(f"[{time.strftime('%H:%M:%S')}] Erro ao ler byte: {str(e)}")
                                            break

                                    # Verificar se passamos do timeout (100ms)
                                    if time.time() - start_time > 0.1:
                                        print(f"[{time.strftime('%H:%M:%S')}] Timeout ao ler linha")
                                        break

                                line = line_bytes.strip().decode('utf-8', errors='ignore')
                                # Imprimir a linha para debug com timestamp para verificar se está sendo capturada em tempo real
                                print(f"[{time.strftime('%H:%M:%S')}] Linha lida: {line}")
                                if line:
                                    # Capturar qualquer linha que contenha informações de progresso
                                    # Verificar se a linha contém informações de frame ou outras informações relevantes
                                    if (line.startswith("frame=") or
                                        "fps=" in line or
                                        "time=" in line or
                                        "bitrate=" in line or
                                        "speed=" in line or
                                        "size=" in line):
                                        frame_counter += 1
                                        last_progress_line = line

                                        # Adicionar a linha à lista de linhas de progresso (máximo 6 linhas)
                                        progress_lines.append(line)
                                        if len(progress_lines) > 6:
                                            progress_lines.pop(0)  # Remover a linha mais antiga

                                        # Atualizar a área de status com as últimas linhas de progresso
                                        status_text = "\n".join(progress_lines)
                                        self.status_signal.emit(status_text)
                                        print(f"[{time.strftime('%H:%M:%S')}] ENVIANDO PARA STATUS: {line}")  # Debug com timestamp

                                        # Forçar a atualização da interface para garantir que as informações sejam exibidas em tempo real
                                        QApplication.processEvents()

                                        # Extrair informações de tempo para atualizar a barra de progresso
                                        # Verificar se a linha contém informações de tempo (out_time ou time=)
                                        if "out_time=" in line or "time=" in line:
                                            try:
                                                # Primeiro tentar extrair out_time (formato mais confiável)
                                                out_time_match = re.search(r'out_time=(\d+:\d+:\d+\.\d+)', line)
                                                time_match = re.search(r'time=(\d+:\d+:\d+\.\d+)', line)

                                                # Usar out_time se disponível, caso contrário usar time
                                                if out_time_match:
                                                    time_str = out_time_match.group(1)
                                                    print(f"[{time.strftime('%H:%M:%S')}] Encontrado out_time: {time_str}")
                                                elif time_match:
                                                    time_str = time_match.group(1)
                                                    print(f"[{time.strftime('%H:%M:%S')}] Encontrado time: {time_str}")
                                                else:
                                                    # Se não encontrar nenhum dos dois, continuar para a próxima linha
                                                    continue

                                                # Converter o tempo no formato HH:MM:SS.MS para segundos
                                                h, m, s = time_str.split(':')  # Separa horas, minutos e segundos
                                                s, ms = s.split('.')  # Separa segundos e milissegundos
                                                current_seconds = int(h) * 3600 + int(m) * 60 + int(s) + float(f"0.{ms}")

                                                # Verificar se temos valores válidos para duration e total_duration
                                                if self.duration > 0 and self.total_duration > 0:
                                                    # Calcular o progresso atual dentro da parte sendo processada
                                                    part_progress = (current_seconds / self.duration) * 100
                                                    print(f"[{time.strftime('%H:%M:%S')}] PROGRESSO DA PARTE: {part_progress:.1f}%")

                                                    # Calcular o progresso geral considerando as partes já processadas
                                                    # e a parte atual que está sendo processada
                                                    # Corrigir o cálculo para garantir que o progresso comece do zero
                                                    # e avance corretamente durante todo o processamento
                                                    overall_progress = (self.current_time / self.total_duration) * 100
                                                    overall_progress += (current_seconds / self.total_duration) * 100

                                                    # Limitar o progresso a 99.9% para evitar que chegue a 100% antes de terminar
                                                    if overall_progress > 99.9:
                                                        overall_progress = 99.9

                                                    # Enviar o progresso atualizado
                                                    self.progress_signal.emit(overall_progress)
                                                    print(f"[{time.strftime('%H:%M:%S')}] PROGRESSO GERAL: {overall_progress:.1f}%")
                                                else:
                                                    # Se não temos valores válidos, usar uma abordagem mais simples
                                                    # Usar apenas o tempo atual como uma porcentagem da duração estimada do vídeo
                                                    # Assumir que o vídeo tem duração de 2 minutos (120 segundos) se não soubermos
                                                    estimated_duration = 120
                                                    simple_progress = (current_seconds / estimated_duration) * 100
                                                    if simple_progress > 99.9:
                                                        simple_progress = 99.9
                                                    self.progress_signal.emit(simple_progress)
                                                    print(f"[{time.strftime('%H:%M:%S')}] PROGRESSO SIMPLES: {simple_progress:.1f}%")
                                            except Exception as e:
                                                print(f"[{time.strftime('%H:%M:%S')}] Erro ao extrair tempo: {str(e)}")
                                                traceback.print_exc()

                                        # Não exibir as linhas de progresso no log, apenas no status
                                        # Isso mantém o log limpo com apenas informações importantes para o usuário
                                        # Forçar a atualização da interface
                                        QApplication.processEvents()
                                    # Filtrar mensagens técnicas e de sincronização para não sobrecarregar o log
                                    elif "encoder" in line or "Stream mapping" in line or "Press" in line or "Parsed_overlay" in line or "framesync" in line or "Sync level" in line:
                                        # Apenas imprimir para debug, não adicionar ao log do usuário
                                        print(f"[{time.strftime('%H:%M:%S')}] INFO TÉCNICA: {line}")

                                        # Forçar a atualização da interface
                                        QApplication.processEvents()

                                        # Se for uma mensagem de sincronização, não deixar que ela afete a área de status
                                        if "Parsed_overlay" in line or "framesync" in line or "Sync level" in line:
                                            print(f"[{time.strftime('%H:%M:%S')}] IGNORANDO MENSAGEM DE SINCRONIZAÇÃO: {line}")

                                            # Garantir que a área de status continue mostrando as informações de progresso
                                            if progress_lines:  # Se houver linhas de progresso anteriores
                                                status_text = "\n".join(progress_lines)
                                                self.status_signal.emit(status_text)
                                                print(f"[{time.strftime('%H:%M:%S')}] RESTAURANDO STATUS IMEDIATAMENTE: {status_text[:50]}...")

                                                # Forçar a atualização da interface
                                                QApplication.processEvents()
                            except Exception as e:
                                # Erro ao ler a saída, aguardar um pouco
                                print(f"Erro ao ler saída: {str(e)}")
                                time.sleep(0.1)

                        # Exibir a última linha de progresso se não foi exibida ainda
                        if last_progress_line and frame_counter % 10 != 0:
                            self.log_signal.emit(last_progress_line)
                            QApplication.processEvents()

                    # Iniciar a thread de leitura
                    read_thread = threading.Thread(target=read_output)
                    read_thread.daemon = True
                    read_thread.start()

                    # Criar uma thread separada para monitorar o status e garantir que ele continue sendo atualizado
                    def monitor_status():
                        last_update_time = time.time()
                        while self.process.poll() is None and self.is_running:
                            current_time = time.time()
                            # Se passaram mais de 0.5 segundos desde a última atualização de status e temos linhas de progresso
                            # Atualizar com mais frequência para garantir que as informações sejam exibidas em tempo real
                            if current_time - last_update_time > 0.5 and progress_lines:
                                # Restaurar o status anterior
                                status_text = "\n".join(progress_lines)
                                self.status_signal.emit(status_text)
                                print(f"[{time.strftime('%H:%M:%S')}] RESTAURANDO STATUS PERIODICAMENTE: {status_text[:50]}...")
                                last_update_time = current_time
                            time.sleep(0.1)  # Verificar com mais frequência para garantir atualizações em tempo real

                    # Iniciar a thread de monitoramento
                    monitor_thread = threading.Thread(target=monitor_status)
                    monitor_thread.daemon = True
                    monitor_thread.start()

                    # Aguardar a conclusão do processo, mas verificando periodicamente
                    # para garantir que a interface seja atualizada
                    while self.process.poll() is None and self.is_running:
                        # Aguardar um curto período
                        time.sleep(0.1)
                        # Forçar a atualização da interface
                        QApplication.processEvents()

                    # Aguardar um pouco para garantir que todas as mensagens de progresso sejam exibidas
                    time.sleep(0.5)
                    QApplication.processEvents()

                    # Capturar qualquer saída restante
                    # Agora só precisamos ler de stdout porque redirecionamos stderr para stdout
                    try:
                        if self.process.stdout and self.process.stdout.readable():
                            stdout = self.process.stdout.read()
                        else:
                            stdout = b""
                    except Exception as e:
                        print(f"[{time.strftime('%H:%M:%S')}] Erro ao ler saída restante: {str(e)}")
                        stdout = b""

                    # Verificar o resultado
                    if self.process.returncode != 0:
                        self.log_signal.emit(f"Erro ao processar parte {part_number}. Verifique o vídeo de entrada e tente novamente.")
                    else:
                        self.log_signal.emit(f"Parte {part_number} processada e salva com sucesso!")
                except Exception as e:
                    self.log_signal.emit(f"Erro ao executar FFmpeg: {str(e)}")
                    if not self.is_running:
                        break

                # Atualizar o tempo atual e o número da parte
                current_time += duration
                part_number += 1
                total_parts += 1

                # Atualizar o progresso com maior precisão (usando float em vez de int)
                progress = (current_time / total_duration) * 100
                self.progress_signal.emit(progress)

                # Verificar se o processo foi cancelado
                if not self.is_running:
                    self.log_signal.emit("Processo cancelado pelo usuário.")
                    break

            if self.is_running:
                self.log_signal.emit(f"Processamento concluído com sucesso! {total_parts} vídeos foram gerados.")
                self.progress_signal.emit(100)
                self.finished_signal.emit()

        except Exception as e:
            self.error_signal.emit(f"Erro durante o processamento: {str(e)}")
            traceback.print_exc()

    def get_video_duration(self, video_file):
        """Obtém a duração de um arquivo de vídeo usando FFmpeg"""
        try:
            cmd = ["ffprobe", "-i", video_file, "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"]
            result = ffmpeg_utils.run_ffprobe_command(cmd)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
            return -1
        except Exception as e:
            self.log_signal.emit(f"Erro ao obter duração do vídeo: {str(e)}")
            return -1

    def get_video_resolution(self, video_file):
        """Obtém a resolução de um arquivo de vídeo usando FFmpeg"""
        try:
            cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", video_file]
            result = ffmpeg_utils.run_ffprobe_command(cmd)
            if result.returncode == 0 and result.stdout.strip():
                # O formato da saída é "width x height", por exemplo "1920x1080"
                dimensions = result.stdout.strip().split('x')
                if len(dimensions) == 2:
                    width = int(dimensions[0])
                    height = int(dimensions[1])
                    return width, height
            self.log_signal.emit(f"Aviso: Não foi possível obter a resolução do vídeo {os.path.basename(video_file)}. Usando resolução padrão.")
            return 1080, 1920  # Resolução padrão (vertical)
        except Exception as e:
            self.log_signal.emit(f"Erro ao obter resolução do vídeo: {str(e)}")
            return 1080, 1920  # Resolução padrão em caso de erro

    def get_image_resolution(self, image_file):
        """Obtém a resolução de uma imagem usando FFmpeg"""
        try:
            cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", image_file]
            result = ffmpeg_utils.run_ffprobe_command(cmd)
            if result.returncode == 0 and result.stdout.strip():
                dimensions = result.stdout.strip().split('x')
                if len(dimensions) == 2:
                    width = int(dimensions[0])
                    height = int(dimensions[1])
                    return width, height
            self.log_signal.emit(f"Aviso: Não foi possível obter a resolução da imagem {os.path.basename(image_file)}. Usando resolução padrão.")
            return 1080, 1920  # Resolução padrão (vertical)
        except Exception as e:
            self.log_signal.emit(f"Erro ao obter resolução da imagem: {str(e)}")
            return 1080, 1920  # Resolução padrão em caso de erro

    def check_resolution_compatibility(self, input_res, cover_res, selo_res):
        """Verifica a compatibilidade entre as resoluções e determina quais arquivos precisam ser redimensionados"""
        input_width, input_height = input_res
        cover_width, cover_height = cover_res
        selo_width, selo_height = selo_res

        # Calcular a proporção (aspect ratio) do vídeo de entrada
        input_aspect_ratio = input_width / input_height

        # Inicializar o dicionário de resultado
        result = {
            'input_resolution': input_res,
            'cover_needs_resize': False,
            'selo_needs_resize': False,
            'aspect_ratio': input_aspect_ratio,
            'is_vertical': input_height > input_width,
            'resize_filters': {}
        }

        # Verificar se a imagem de capa precisa ser redimensionada
        if cover_width != input_width or cover_height != input_height:
            result['cover_needs_resize'] = True
            result['resize_filters']['cover'] = f"scale={input_width}:{input_height}"

        # Verificar se o vídeo do selo precisa ser redimensionado
        if selo_width != input_width or selo_height != input_height:
            result['selo_needs_resize'] = True
            result['resize_filters']['selo'] = f"scale={input_width}:{input_height}"

        return result

    def stop(self):
        """Para o processamento"""
        self.is_running = False
        if self.process:
            try:
                self.process.terminate()
            except:
                pass

class VideoCutterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        # Verificar se o FFmpeg está disponível
        self.check_ffmpeg()
        self.initUI()

    def check_ffmpeg(self):
        """Verifica se o FFmpeg está disponível"""
        if not ffmpeg_utils.check_ffmpeg():
            QMessageBox.critical(self, "Erro", "FFmpeg não encontrado no sistema ou no pacote da aplicação.\n\n"
                                "A aplicação não poderá funcionar corretamente.")
            print("FFmpeg não encontrado!")
            return

        # Detectar o fabricante da GPU
        gpu_vendor = ffmpeg_utils.detect_gpu_vendor()
        print(f"Fabricante da GPU detectado: {gpu_vendor}")

        # Verificar quais aceleradores de hardware estão disponíveis
        has_nvenc = ffmpeg_utils.has_nvenc()
        has_amf = ffmpeg_utils.has_amf()
        has_qsv = ffmpeg_utils.has_qsv()

        # Obter o codificador com base no hardware detectado
        encoder_name, _ = ffmpeg_utils.get_video_encoder()

        # Exibir informações sobre o hardware e codificador
        print(f"Codificadores disponíveis - NVIDIA: {has_nvenc}, AMD: {has_amf}, Intel: {has_qsv}")
        print(f"Codificador selecionado: {encoder_name}")

        if gpu_vendor == "amd" and has_amf:
            print("GPU AMD detectada! Usando aceleração de hardware AMD.")
        elif gpu_vendor == "nvidia" and has_nvenc:
            print("GPU NVIDIA detectada! Usando aceleração de hardware NVIDIA.")
        elif gpu_vendor == "intel" and has_qsv:
            print("GPU Intel detectada! Usando aceleração de hardware Intel.")
        elif has_amf:
            print("AMF detectado! Usando aceleração de hardware AMD.")
        elif has_nvenc:
            print("NVENC detectado! Usando aceleração de hardware NVIDIA.")
        elif has_qsv:
            print("QuickSync detectado! Usando aceleração de hardware Intel.")
        else:
            print(f"Nenhum acelerador de hardware detectado. Usando codificador de software: {encoder_name}")

    def initUI(self):
        # Configurar a janela principal
        self.setWindowTitle("Video Cutter")
        self.setGeometry(100, 100, 530, 630)
        # Definir tamanho fixo
        self.setFixedSize(530, 630)
        # Impedir maximização
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)

        # Definir o ícone da janela
        icon_path = "video-cutter-icone.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Widget central e layout principal
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        # Grupo de arquivos
        file_group = QGroupBox("Arquivos")
        file_layout = QVBoxLayout()

        # Input video
        input_layout = QHBoxLayout()
        input_label = QLabel("Vídeo de entrada:")
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("input.mp4")
        input_button = QPushButton("Procurar...")
        input_button.clicked.connect(lambda: self.browse_file(self.input_path, "Vídeos (*.mp4 *.avi *.mkv)"))
        input_layout.addWidget(input_label)
        input_layout.addWidget(self.input_path)
        input_layout.addWidget(input_button)
        file_layout.addLayout(input_layout)

        # Image file
        image_layout = QHBoxLayout()
        image_label = QLabel("Imagem de capa:")
        self.image_path = QLineEdit()
        self.image_path.setPlaceholderText("image.png")
        image_button = QPushButton("Procurar...")
        image_button.clicked.connect(lambda: self.browse_file(self.image_path, "Imagens (*.png *.jpg *.jpeg)"))
        image_layout.addWidget(image_label)
        image_layout.addWidget(self.image_path)
        image_layout.addWidget(image_button)
        file_layout.addLayout(image_layout)

        # Selo video
        selo_layout = QHBoxLayout()
        selo_label = QLabel("Vídeo do selo:")
        self.selo_path = QLineEdit()
        self.selo_path.setPlaceholderText("selo.mp4")
        selo_button = QPushButton("Procurar...")
        selo_button.clicked.connect(lambda: self.browse_file(self.selo_path, "Vídeos (*.mp4 *.avi *.mkv)"))
        selo_layout.addWidget(selo_label)
        selo_layout.addWidget(self.selo_path)
        selo_layout.addWidget(selo_button)
        file_layout.addLayout(selo_layout)

        # Output directory
        output_dir_layout = QHBoxLayout()
        output_dir_label = QLabel("Pasta de saída:")
        self.output_dir = QLineEdit()
        self.output_dir.setPlaceholderText("Mesma pasta do vídeo de entrada")
        output_dir_button = QPushButton("Procurar...")
        output_dir_button.clicked.connect(self.browse_output_dir)
        output_dir_layout.addWidget(output_dir_label)
        output_dir_layout.addWidget(self.output_dir)
        output_dir_layout.addWidget(output_dir_button)
        file_layout.addLayout(output_dir_layout)

        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)

        # Grupo de configurações
        config_group = QGroupBox("Configurações")
        config_layout = QVBoxLayout()

        # Definir tamanho mínimo para o grupo de configurações
        config_group.setMinimumWidth(500)  # Largura mínima para o grupo

        # Output prefix
        prefix_layout = QHBoxLayout()
        prefix_label = QLabel("Prefixo de saída:")
        self.output_prefix = QLineEdit()
        self.output_prefix.setPlaceholderText("Prefixo do Arquivo")
        prefix_layout.addWidget(prefix_label)
        prefix_layout.addWidget(self.output_prefix)
        config_layout.addLayout(prefix_layout)

        # Start index
        index_layout = QHBoxLayout()
        index_label = QLabel("Índice inicial:")
        self.start_index = QSpinBox()
        self.start_index.setRange(1, 999)
        self.start_index.setValue(1)
        index_layout.addWidget(index_label)
        index_layout.addWidget(self.start_index)
        config_layout.addLayout(index_layout)

        # Duration settings
        duration_layout = QHBoxLayout()
        min_label = QLabel("Duração mínima (s):")
        self.min_duration = QSpinBox()
        self.min_duration.setRange(10, 300)
        self.min_duration.setValue(90)
        max_label = QLabel("Duração máxima (s):")
        self.max_duration = QSpinBox()
        self.max_duration.setRange(10, 600)
        self.max_duration.setValue(130)
        duration_layout.addWidget(min_label)
        duration_layout.addWidget(self.min_duration)
        duration_layout.addWidget(max_label)
        duration_layout.addWidget(self.max_duration)
        config_layout.addLayout(duration_layout)

        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # Grupo de configurações de Chroma Key (separado do grupo de configurações principal)
        chroma_group = QGroupBox("Configurações de Chroma Key")
        chroma_layout = QGridLayout()

        # Definir larguras mínimas para as colunas
        chroma_layout.setColumnMinimumWidth(0, 150)  # Coluna dos rótulos
        chroma_layout.setColumnMinimumWidth(1, 200)  # Coluna dos campos

        # Definir o espaçamento entre os elementos
        chroma_layout.setHorizontalSpacing(10)  # Espaçamento horizontal
        chroma_layout.setVerticalSpacing(10)     # Espaçamento vertical

        # Cor do Chroma Key (linha 0)
        chroma_color_label = QLabel("Cor do Chroma Key:")
        self.chroma_color = QLineEdit("0x00d600")
        self.chroma_color.setFixedWidth(200)  # Largura fixa para o campo de texto
        self.chroma_color.setToolTip("Código hexadecimal da cor a ser removida (ex: 0x00d600 para verde)")
        chroma_color_button = QPushButton("Escolher Cor")
        chroma_color_button.setFixedWidth(100)  # Largura fixa para o botão
        chroma_color_button.clicked.connect(self.choose_chroma_color)

        # Adicionar ao grid layout (linha 0)
        chroma_layout.addWidget(chroma_color_label, 0, 0)
        chroma_layout.addWidget(self.chroma_color, 0, 1)
        chroma_layout.addWidget(chroma_color_button, 0, 2)

        # Similaridade (linha 1)
        similarity_label = QLabel("Similaridade:")
        self.similarity = QDoubleSpinBox()
        self.similarity.setFixedWidth(200)  # Largura fixa para o campo
        self.similarity.setRange(0.01, 1.0)
        self.similarity.setSingleStep(0.01)
        self.similarity.setValue(0.30)
        self.similarity.setToolTip("Quanto maior o valor, mais tons da cor serão removidos (0.01-1.0)")

        # Adicionar ao grid layout (linha 1)
        chroma_layout.addWidget(similarity_label, 1, 0)
        chroma_layout.addWidget(self.similarity, 1, 1)

        # Suavidade de borda (linha 2)
        blend_label = QLabel("Suavidade de borda:")
        self.blend = QDoubleSpinBox()
        self.blend.setFixedWidth(200)  # Largura fixa para o campo
        self.blend.setRange(0.0, 1.0)
        self.blend.setSingleStep(0.05)
        self.blend.setValue(0.35)  # Valor aumentado para melhorar a suavidade
        self.blend.setToolTip("Quanto maior o valor, mais suaves serão as bordas (0.0-1.0)")

        # Adicionar ao grid layout (linha 2)
        chroma_layout.addWidget(blend_label, 2, 0)
        chroma_layout.addWidget(self.blend, 2, 1)

        # Definir o layout do grupo de Chroma Key
        chroma_group.setLayout(chroma_layout)
        main_layout.addWidget(chroma_group)

        # Área de log
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        log_layout.addWidget(self.log_area)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        # Status da codificação
        status_group = QGroupBox("Status da Codificação")
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(5, 5, 5, 5)  # Reduzir margens (esquerda, topo, direita, base)
        status_layout.setSpacing(2)  # Reduzir espaçamento entre widgets
        self.status_area = QTextEdit()
        self.status_area.setReadOnly(True)
        self.status_area.setMinimumHeight(30)  # Altura mínima reduzida
        self.status_area.setMaximumHeight(30)  # Altura máxima reduzida
        self.status_area.setStyleSheet("background-color: #f0f0f0; font-family: monospace; padding: 2px;")  # Estilo para destacar com padding reduzido
        status_layout.addWidget(self.status_area)
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)

        # Barra de progresso
        progress_group = QGroupBox("Progresso")
        progress_layout = QVBoxLayout()

        # Layout horizontal para a barra de progresso e o rótulo de porcentagem
        progress_bar_layout = QHBoxLayout()

        # Barra de progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        # Desativar o texto padrão da barra de progresso para evitar números estranhos
        self.progress_bar.setTextVisible(False)
        progress_bar_layout.addWidget(self.progress_bar, 9)  # Peso 9 para ocupar mais espaço

        # Rótulo de porcentagem
        self.progress_percent_label = QLabel("0%")
        self.progress_percent_label.setAlignment(Qt.AlignCenter)
        self.progress_percent_label.setMinimumWidth(40)  # Largura mínima para garantir espaço suficiente
        progress_bar_layout.addWidget(self.progress_percent_label, 1)  # Peso 1 para ocupar menos espaço

        progress_layout.addLayout(progress_bar_layout)

        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)

        # Botões de ação
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Iniciar Corte")
        self.start_button.clicked.connect(self.start_cutting)
        button_layout.addWidget(self.start_button)

        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.cancel_button)

        # Botão para abrir a pasta de saída
        self.open_folder_button = QPushButton("Abrir Pasta")
        self.open_folder_button.clicked.connect(self.open_output_folder)
        button_layout.addWidget(self.open_folder_button)

        main_layout.addLayout(button_layout)

        # Definir o widget central
        self.setCentralWidget(central_widget)

        # Adicionar mensagem inicial ao log
        self.log("Aplicativo iniciado. Configure os parâmetros e clique em 'Iniciar Corte'.")

    def browse_file(self, line_edit, file_filter):
        """Abre um diálogo para selecionar um arquivo"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecionar arquivo", "", file_filter)
        if file_path:
            line_edit.setText(file_path)

    def browse_output_dir(self):
        """Abre um diálogo para selecionar a pasta de saída"""
        dir_path = QFileDialog.getExistingDirectory(self, "Selecionar pasta de saída")
        if dir_path:
            self.output_dir.setText(dir_path)

    def choose_chroma_color(self):
        """Abre um seletor de cor para o chroma key"""
        # Converter o valor hexadecimal atual para QColor
        current_hex = self.chroma_color.text().strip()
        current_color = QColor()

        # Verificar se o formato é 0xRRGGBB e converter para #RRGGBB
        if current_hex.startswith("0x") and len(current_hex) == 8:
            rgb_hex = current_hex[2:]
            current_color.setNamedColor(f"#{rgb_hex}")
        else:
            # Cor padrão (verde)
            current_color.setNamedColor("#00d600")

        # Abrir o diálogo de seleção de cor
        color = QColorDialog.getColor(current_color, self, "Selecionar Cor do Chroma Key")

        # Se uma cor válida foi selecionada
        if color.isValid():
            # Converter para o formato 0xRRGGBB
            hex_color = color.name().replace("#", "0x")
            self.chroma_color.setText(hex_color)

    def log(self, message):
        """Adiciona uma mensagem à área de log"""
        self.log_area.append(message)
        # Rola para o final
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def update_status(self, message):
        """Atualiza a área de status da codificação"""
        print(f"[{time.strftime('%H:%M:%S')}] STATUS ATUALIZADO: {message[:100]}...")  # Debug com timestamp
        if message.strip():  # Só atualiza se a mensagem não estiver vazia
            # Extrair apenas as informações mais importantes
            fps_match = re.search(r'fps=\s*([\d\.]+)', message)
            time_match = re.search(r'time=\s*(\d+:\d+:\d+\.\d+)', message)
            speed_match = re.search(r'speed=\s*([\d\.]+)x', message)

            # Construir uma mensagem simplificada
            simplified_message = ""
            if fps_match:
                simplified_message += f"FPS: {fps_match.group(1)} "
            if time_match:
                simplified_message += f"Tempo: {time_match.group(1)} "
            if speed_match:
                simplified_message += f"Velocidade: {speed_match.group(1)}x"

            # Se não conseguimos extrair nenhuma informação, usar a mensagem original filtrada
            if not simplified_message:
                # Filtrar informações de frame, total_size e bitrate
                filtered_message = re.sub(r'frame=\s*\d+\s+', '', message)
                filtered_message = re.sub(r'total_size=\s*\d+\s+', '', filtered_message)
                filtered_message = re.sub(r'bitrate=\s*[\d\.]+kbits\/s\s*', '', filtered_message)
                filtered_message = re.sub(r'size=\s*[\d\.]+[kKmMgG][bB]\s+', '', filtered_message)

                # Remover espaços extras que podem ter sido criados pela remoção
                simplified_message = re.sub(r'\s+', ' ', filtered_message).strip()

            self.status_area.setText(simplified_message)  # Define o texto simplificado
            # Rola para o final
            self.status_area.verticalScrollBar().setValue(self.status_area.verticalScrollBar().maximum())

            # Tentar extrair informações de tempo para atualizar a barra de progresso
            try:
                # Verificar se a mensagem contém informações de out_time
                out_time_match = re.search(r'out_time=(\d+:\d+:\d+\.\d+)', message)
                if out_time_match:
                    time_str = out_time_match.group(1)
                    print(f"[{time.strftime('%H:%M:%S')}] ENCONTRADO OUT_TIME NO STATUS: {time_str}")

                    # Converter o tempo no formato HH:MM:SS.MS para segundos
                    h, m, s = time_str.split(':')  # Separa horas, minutos e segundos
                    s, ms = s.split('.')  # Separa segundos e milissegundos
                    current_seconds = int(h) * 3600 + int(m) * 60 + int(s) + float(f"0.{ms}")

                    # Obter a duração total do vídeo atual sendo processado
                    if hasattr(self, 'worker') and hasattr(self.worker, 'duration') and hasattr(self.worker, 'total_duration'):
                        duration = self.worker.duration
                        total_duration = self.worker.total_duration
                        current_time = self.worker.current_time

                        print(f"[{time.strftime('%H:%M:%S')}] DADOS DO WORKER: duration={duration}, total_duration={total_duration}, current_time={current_time}")

                        # Verificar se os valores são válidos
                        if duration > 0 and total_duration > 0:
                            # Calcular o progresso atual dentro da parte sendo processada
                            part_progress = (current_seconds / duration) * 100

                            # Calcular o progresso geral considerando as partes já processadas
                            # e a parte atual que está sendo processada
                            # Corrigir o cálculo para garantir que o progresso comece do zero
                            # e avance corretamente durante todo o processamento
                            overall_progress = (current_time / total_duration) * 100
                            overall_progress += (current_seconds / total_duration) * 100

                            # Limitar o progresso a 99.9% para evitar que chegue a 100% antes de terminar
                            if overall_progress > 99.9:
                                overall_progress = 99.9

                            # Atualizar a barra de progresso
                            self.update_progress(overall_progress)
                            print(f"[{time.strftime('%H:%M:%S')}] PROGRESSO (do status): {overall_progress:.1f}%")
                        else:
                            # Se não temos valores válidos, usar uma abordagem mais simples
                            # Usar apenas o tempo atual como uma porcentagem da duração estimada do vídeo
                            # Assumir que o vídeo tem duração de 2 minutos (120 segundos) se não soubermos
                            estimated_duration = 120
                            simple_progress = (current_seconds / estimated_duration) * 100
                            if simple_progress > 99.9:
                                simple_progress = 99.9
                            self.update_progress(simple_progress)
                            print(f"[{time.strftime('%H:%M:%S')}] PROGRESSO SIMPLES: {simple_progress:.1f}%")
                    else:
                        # Se não temos acesso ao worker ou suas propriedades, usar uma abordagem mais simples
                        # Usar apenas o tempo atual como uma porcentagem da duração estimada do vídeo
                        # Assumir que o vídeo tem duração de 2 minutos (120 segundos) se não soubermos
                        estimated_duration = 120
                        simple_progress = (current_seconds / estimated_duration) * 100
                        if simple_progress > 99.9:
                            simple_progress = 99.9
                        self.update_progress(simple_progress)
                        print(f"[{time.strftime('%H:%M:%S')}] PROGRESSO SIMPLES (sem worker): {simple_progress:.1f}%")
            except Exception as e:
                # Ignorar erros ao extrair tempo do status, mas imprimir para debug
                print(f"[{time.strftime('%H:%M:%S')}] Erro ao extrair tempo do status: {str(e)}")
                traceback.print_exc()

            # Força a atualização da interface
            QApplication.processEvents()

    def start_cutting(self):
        """Inicia o processo de corte de vídeo"""
        # Obter os valores dos campos
        input_file = self.input_path.text()
        image_file = self.image_path.text()
        selo_file = self.selo_path.text()

        # Garantir que o prefixo termine com espaço
        output_prefix = self.output_prefix.text()
        if output_prefix and not output_prefix.endswith(" "):
            output_prefix += " "
        elif not output_prefix:
            output_prefix = "Prefixo Parte "

        start_index = self.start_index.value()
        min_duration = self.min_duration.value()
        max_duration = self.max_duration.value()
        output_directory = self.output_dir.text()

        # Validar os campos
        if not input_file:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione o vídeo de entrada.")
            return

        if not image_file:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione a imagem de capa.")
            return

        if not selo_file:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione o vídeo do selo.")
            return

        if min_duration >= max_duration:
            QMessageBox.warning(self, "Aviso", "A duração mínima deve ser menor que a duração máxima.")
            return

        # Limpar o log, a área de status e resetar a barra de progresso
        self.log_area.clear()
        self.status_area.clear()
        # Usar o método update_progress para garantir consistência
        self.update_progress(0.0)

        # Desabilitar o botão de iniciar e habilitar o botão de cancelar
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        # Mostrar mensagens claras e informativas para o usuário
        self.log("Iniciando processamento de vídeo...")
        self.log(f"Arquivo de entrada: {os.path.basename(input_file)}")

        # Informar onde os arquivos serão salvos
        if output_directory:
            output_path = output_directory
        else:
            output_path = os.path.dirname(input_file)
        self.log(f"Os vídeos processados serão salvos em: {output_path}")

        # Informar o formato de saída
        self.log(f"Formato de saída: {output_prefix}1.mp4, {output_prefix}2.mp4, etc.")

        # Informar a duração dos vídeos
        self.log(f"Duração dos vídeos: entre {min_duration} e {max_duration} segundos")

        # Detectar o fabricante da GPU
        gpu_vendor = ffmpeg_utils.detect_gpu_vendor()

        # Mostrar informações sobre o codificador
        encoder_name, _ = ffmpeg_utils.get_video_encoder()

        # Exibir informações sobre o hardware e codificador
        if gpu_vendor == "amd" and encoder_name == "h264_amf":
            self.log("- Codificador: AMD AMF (aceleração de hardware AMD)")
        elif gpu_vendor == "nvidia" and encoder_name == "h264_nvenc":
            self.log("- Codificador: NVIDIA NVENC (aceleração de hardware NVIDIA)")
        elif gpu_vendor == "intel" and encoder_name == "h264_qsv":
            self.log("- Codificador: Intel QuickSync (aceleração de hardware Intel)")
        elif encoder_name == "h264_amf":
            self.log("- Codificador: AMD AMF (aceleração de hardware)")
        elif encoder_name == "h264_nvenc":
            self.log("- Codificador: NVIDIA NVENC (aceleração de hardware)")
        elif encoder_name == "h264_qsv":
            self.log("- Codificador: Intel QuickSync (aceleração de hardware)")
        else:
            self.log(f"- Codificador: {encoder_name} (codificação por software)")

        # Mostrar informações sobre os parâmetros de chroma key
        self.log(f"- Chroma Key: Cor={self.chroma_color.text()}, Similaridade={self.similarity.value()}, Suavidade={self.blend.value()}")

        # Obter os parâmetros de chroma key
        chroma_color = self.chroma_color.text()
        similarity = self.similarity.value()
        blend = self.blend.value()

        # Validar a cor do chroma key
        if not re.match(r'^0x[0-9A-Fa-f]{6}$', chroma_color):
            QMessageBox.warning(self, "Aviso", "Formato de cor inválido. Use o formato 0xRRGGBB (ex: 0x00d600).")
            return

        # Criar e iniciar a thread de processamento
        self.worker = VideoCutterWorker(
            input_file, image_file, selo_file, output_prefix,
            start_index, min_duration, max_duration, output_directory,
            chroma_color, similarity, blend
        )

        # Conectar os sinais
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.log_signal.connect(self.log)
        self.worker.status_signal.connect(self.update_status)  # Conectar o sinal de status
        self.worker.finished_signal.connect(self.process_finished)
        self.worker.error_signal.connect(self.process_error)

        # Conectar o botão de cancelar
        self.cancel_button.clicked.connect(self.cancel_process)

        # Iniciar a thread
        self.worker.start()

    def update_progress(self, value):
        """Atualiza a barra de progresso e o rótulo de porcentagem"""
        # Garantir que o valor esteja entre 0 e 100
        if value < 0:
            value = 0
        elif value > 100:
            value = 100

        # Atualizar a barra de progresso com o valor inteiro
        self.progress_bar.setValue(int(value))

        # Atualizar o rótulo de porcentagem com uma casa decimal para maior precisão
        self.progress_percent_label.setText(f"{value:.1f}%")

        # Imprimir para debug
        print(f"[{time.strftime('%H:%M:%S')}] Atualizando progresso: {value:.1f}%")

        # Forçar a atualização da interface
        QApplication.processEvents()

    def process_finished(self):
        """Chamado quando o processo é concluído"""
        self.log("Processo concluído com sucesso!")
        self.status_area.clear()  # Limpar a área de status

        # Garantir que a barra de progresso e o rótulo mostrem 100%
        # Usar o método update_progress para garantir consistência
        self.update_progress(100.0)

        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def process_error(self, error_message):
        """Chamado quando ocorre um erro no processo"""
        QMessageBox.critical(self, "Erro", error_message)
        self.log(f"ERRO: {error_message}")
        self.status_area.clear()  # Limpar a área de status
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def cancel_process(self):
        """Cancela o processo em execução"""
        if hasattr(self, 'worker') and self.worker.isRunning():
            reply = QMessageBox.question(self, 'Confirmação',
                                       'Tem certeza que deseja cancelar o processo?',
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.log("Cancelando processo...")
                self.status_area.clear()  # Limpar a área de status
                self.worker.stop()
                self.start_button.setEnabled(True)
                self.cancel_button.setEnabled(False)

    def open_output_folder(self):
        """Abre a pasta de saída no explorador de arquivos"""
        # Determinar a pasta de saída
        output_directory = self.output_dir.text()
        if output_directory:
            output_path = output_directory
        else:
            # Se nenhuma pasta de saída foi especificada, usar a pasta do vídeo de entrada
            input_file = self.input_path.text()
            if input_file:
                output_path = os.path.dirname(input_file)
            else:
                # Se nenhum arquivo de entrada foi especificado, mostrar uma mensagem
                QMessageBox.information(self, "Informação", "Por favor, selecione um vídeo de entrada ou especifique uma pasta de saída.")
                return

        # Verificar se a pasta existe
        if not os.path.exists(output_path):
            QMessageBox.warning(self, "Aviso", f"A pasta {output_path} não existe.")
            return

        # Abrir a pasta no explorador de arquivos
        try:
            # No Windows, usar o comando 'explorer'
            if os.name == 'nt':
                os.startfile(output_path)
            # No macOS, usar o comando 'open'
            elif os.name == 'posix' and sys.platform == 'darwin':
                subprocess.call(['open', output_path])
            # No Linux, usar o comando 'xdg-open'
            elif os.name == 'posix':
                subprocess.call(['xdg-open', output_path])
            else:
                QMessageBox.warning(self, "Aviso", "Não foi possível abrir a pasta no explorador de arquivos.")
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Erro ao abrir a pasta: {str(e)}")

def main():
    print("Função main() iniciada")
    try:
        app = QApplication(sys.argv)
        print("QApplication criada")
        window = VideoCutterApp()
        print("Janela criada")
        window.show()
        print("Janela exibida")
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Erro na função main(): {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
