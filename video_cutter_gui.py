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
                                QMessageBox, QColorDialog, QDoubleSpinBox)
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QProcess
    from PyQt5.QtGui import QColor
    print("PyQt5 importado com sucesso!")
except Exception as e:
    print(f"Erro ao importar PyQt5: {e}")
    traceback.print_exc()

class VideoCutterWorker(QThread):
    progress_signal = pyqtSignal(int)  # Progresso geral
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

    def run(self):
        try:
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
            self.log_signal.emit("Obtendo duração do vídeo principal...")
            total_duration = self.get_video_duration(self.input_file)
            if total_duration <= 0:
                self.error_signal.emit("Não foi possível obter a duração do vídeo principal ou a duração é inválida.")
                return
            self.log_signal.emit(f"Duração total do vídeo: {total_duration:.2f} segundos")

            # Obter a duração do vídeo do selo
            selo_duration = self.get_video_duration(self.selo_file)
            if selo_duration <= 0:
                self.error_signal.emit("Não foi possível obter a duração do vídeo do selo ou a duração é inválida.")
                return
            self.log_signal.emit(f"Duração do vídeo do selo: {selo_duration:.2f} segundos")

            # Inicializar o tempo atual e o número da parte
            current_time = 0
            part_number = self.start_index
            total_parts = 0

            # Calcular o número total estimado de partes para a barra de progresso
            avg_duration = (self.min_duration + self.max_duration) / 2
            estimated_parts = int(total_duration / avg_duration) + 1

            while current_time < total_duration and self.is_running:
                # Gerar duração aleatória entre os limites definidos
                duration = random.randint(self.min_duration, self.max_duration)

                # Se a duração ultrapassar o fim do vídeo, ajusta para terminar no tempo total
                if current_time + duration > total_duration:
                    duration = total_duration - current_time

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

                # Construir o comando FFmpeg
                filter_complex = [
                    f"[0:v]trim=start={current_time}:duration={duration},setpts=PTS-STARTPTS[segment];",
                    f"[2:v]format=rgba,setpts=PTS-STARTPTS[selo_rgba];",
                    f"[selo_rgba]colorkey=color={self.chroma_color}:similarity={self.similarity}:blend={self.blend}[selo_chroma];",
                    f"[selo_chroma]tpad=start_duration=10:color=black@0.0[selo_padded];",
                    f"[segment][selo_padded]overlay=(W-w)/2:(H-h)/2:eof_action=pass[main_with_selo];",
                    f"[main_with_selo][1:v]overlay=(W-w)/2:(H-h)/2:enable='eq(n,0)'[with_image];",
                    f"[with_image]drawtext=text='Parte {part_number}':fontfile='C\:/Windows/Fonts/arial.ttf':fontsize=150:fontcolor=white:borderw=20:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2:enable='eq(n,0)'[final_v];",
                    f"[0:a]atrim=start={current_time}:duration={duration},asetpts=PTS-STARTPTS[final_a]"
                ]

                filter_complex_str = "".join(filter_complex)

                # Verificar qual codificador usar (hardware ou software)
                encoder_name, encoder_params = ffmpeg_utils.get_video_encoder()
                self.log_signal.emit(f"Usando codificador de vídeo: {encoder_name}")
                # Não inicializar a área de status com nenhum exemplo
                # Deixar vazio até que a codificação comece
                self.status_signal.emit("")

                # Configurar parâmetros base do comando
                ffmpeg_cmd = [
                    "ffmpeg"
                ]

                # Adicionar acelerador de hardware apenas se estiver usando NVENC
                if encoder_name == "h264_nvenc":
                    ffmpeg_cmd.extend(["-hwaccel", "cuda"])

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
                    # Adicionar parâmetros para mostrar informações detalhadas como no terminal original
                    # Não adicionamos parâmetros extras para manter a saída original do FFmpeg

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
                                line = self.process.stderr.readline().strip().decode('utf-8', errors='ignore')
                                if line:
                                    # Mostrar todas as linhas que começam com "frame=" (informações de progresso)
                                    if line.startswith("frame="):
                                        frame_counter += 1
                                        last_progress_line = line

                                        # Adicionar a linha à lista de linhas de progresso (máximo 6 linhas)
                                        progress_lines.append(line)
                                        if len(progress_lines) > 6:
                                            progress_lines.pop(0)  # Remover a linha mais antiga

                                        # Atualizar a área de status com as últimas linhas de progresso
                                        status_text = "\n".join(progress_lines)
                                        self.status_signal.emit(status_text)
                                        print(f"Enviando status: {len(progress_lines)} linhas")  # Debug

                                        # Exibir a linha de progresso no log (a cada 10 frames para não sobrecarregar)
                                        if frame_counter % 10 == 0:
                                            self.log_signal.emit(line)
                                            # Forçar a atualização da interface
                                            QApplication.processEvents()
                                    # Mostrar informações do encoder
                                    elif "encoder" in line:
                                        self.log_signal.emit(line)
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
                    if self.process.stdout:
                        stdout = self.process.stdout.read()
                    else:
                        stdout = ""
                    if self.process.stderr:
                        stderr = self.process.stderr.read()
                    else:
                        stderr = ""

                    # Verificar o resultado
                    if self.process.returncode != 0:
                        self.log_signal.emit(f"Erro ao processar parte {part_number}: {stderr}")
                    else:
                        self.log_signal.emit(f"Parte {part_number} concluída com sucesso!")
                except Exception as e:
                    self.log_signal.emit(f"Erro ao executar FFmpeg: {str(e)}")
                    if not self.is_running:
                        break

                # Atualizar o tempo atual e o número da parte
                current_time += duration
                part_number += 1
                total_parts += 1

                # Atualizar o progresso
                progress = int((current_time / total_duration) * 100)
                self.progress_signal.emit(progress)

                # Verificar se o processo foi cancelado
                if not self.is_running:
                    self.log_signal.emit("Processo cancelado pelo usuário.")
                    break

            if self.is_running:
                self.log_signal.emit(f"Processo concluído! {total_parts} partes geradas.")
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

        # Verificar se o NVENC está disponível
        has_nvenc = ffmpeg_utils.has_nvenc()
        encoder_name, _ = ffmpeg_utils.get_video_encoder()

        if has_nvenc:
            print("NVENC detectado! Usando aceleração de hardware.")
        else:
            print(f"NVENC não detectado. Usando codificador de software: {encoder_name}")

    def initUI(self):
        # Configurar a janela principal
        self.setWindowTitle("Video Cutter")
        self.setGeometry(100, 100, 530, 630)
        # Definir tamanho fixo
        self.setFixedSize(530, 630)
        # Impedir maximização
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)

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

        # Grupo de configurações avançadas (Chroma Key)
        advanced_group = QGroupBox("Configurações de Chroma Key")
        advanced_layout = QVBoxLayout()

        # Cor do Chroma Key
        chroma_color_layout = QHBoxLayout()
        chroma_color_label = QLabel("Cor do Chroma Key:")
        self.chroma_color = QLineEdit("0x00d600")
        self.chroma_color.setToolTip("Código hexadecimal da cor a ser removida (ex: 0x00d600 para verde)")
        chroma_color_button = QPushButton("Escolher Cor")
        chroma_color_button.clicked.connect(self.choose_chroma_color)
        chroma_color_layout.addWidget(chroma_color_label)
        chroma_color_layout.addWidget(self.chroma_color)
        chroma_color_layout.addWidget(chroma_color_button)
        advanced_layout.addLayout(chroma_color_layout)

        # Similaridade
        similarity_layout = QHBoxLayout()
        similarity_label = QLabel("Similaridade:")
        self.similarity = QDoubleSpinBox()
        self.similarity.setRange(0.01, 1.0)
        self.similarity.setSingleStep(0.01)
        self.similarity.setValue(0.30)
        self.similarity.setToolTip("Quanto maior o valor, mais tons da cor serão removidos (0.01-1.0)")
        similarity_layout.addWidget(similarity_label)
        similarity_layout.addWidget(self.similarity)
        advanced_layout.addLayout(similarity_layout)

        # Suavidade de borda
        blend_layout = QHBoxLayout()
        blend_label = QLabel("Suavidade de borda:")
        self.blend = QDoubleSpinBox()
        self.blend.setRange(0.0, 1.0)
        self.blend.setSingleStep(0.05)
        self.blend.setValue(0.35)  # Valor aumentado para melhorar a suavidade
        self.blend.setToolTip("Quanto maior o valor, mais suaves serão as bordas (0.0-1.0)")
        blend_layout.addWidget(blend_label)
        blend_layout.addWidget(self.blend)
        advanced_layout.addLayout(blend_layout)

        advanced_group.setLayout(advanced_layout)
        config_layout.addWidget(advanced_group)

        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

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
        self.status_area = QTextEdit()
        self.status_area.setReadOnly(True)
        self.status_area.setMinimumHeight(80)  # Altura mínima
        self.status_area.setMaximumHeight(80)  # Altura máxima
        self.status_area.setStyleSheet("background-color: #f0f0f0; font-family: monospace;")  # Estilo para destacar
        status_layout.addWidget(self.status_area)
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)

        # Barra de progresso
        progress_group = QGroupBox("Progresso")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

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
        print(f"Atualizando status: {message}")  # Debug
        self.status_area.setText(message)  # Define o texto diretamente
        # Rola para o final
        self.status_area.verticalScrollBar().setValue(self.status_area.verticalScrollBar().maximum())
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
        self.progress_bar.setValue(0)

        # Desabilitar o botão de iniciar e habilitar o botão de cancelar
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        # Mostrar os parâmetros configurados
        self.log("Iniciando processo de corte de vídeo...")
        self.log("Parâmetros configurados:")
        self.log(f"- Vídeo de entrada: {input_file}")
        self.log(f"- Imagem de capa: {image_file}")
        self.log(f"- Vídeo do selo: {selo_file}")
        self.log(f"- Prefixo de saída: {output_prefix}")
        self.log(f"- Índice inicial: {start_index}")
        self.log(f"- Duração mínima: {min_duration} segundos")
        self.log(f"- Duração máxima: {max_duration} segundos")
        if output_directory:
            self.log(f"- Pasta de saída: {output_directory}")
        else:
            self.log(f"- Pasta de saída: Mesma pasta do vídeo de entrada")

        # Mostrar informações sobre o codificador
        encoder_name, _ = ffmpeg_utils.get_video_encoder()
        if encoder_name == "h264_nvenc":
            self.log("- Codificador: NVIDIA NVENC (aceleração de hardware)")
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
        """Atualiza a barra de progresso"""
        self.progress_bar.setValue(value)

    def process_finished(self):
        """Chamado quando o processo é concluído"""
        self.log("Processo concluído com sucesso!")
        self.status_area.clear()  # Limpar a área de status
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
