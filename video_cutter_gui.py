import sys
import os
import subprocess
import traceback
import random
import time
import shutil
from pathlib import Path

print("Iniciando aplicação...")

try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton,
                                QVBoxLayout, QHBoxLayout, QWidget, QFileDialog,
                                QLineEdit, QSpinBox, QProgressBar, QTextEdit, QGroupBox,
                                QMessageBox)
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QProcess
    print("PyQt5 importado com sucesso!")
except Exception as e:
    print(f"Erro ao importar PyQt5: {e}")
    traceback.print_exc()

class VideoCutterWorker(QThread):
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, input_file, image_file, selo_file, output_prefix, start_index,
                 min_duration, max_duration, output_directory=None):
        super().__init__()
        self.input_file = input_file
        self.image_file = image_file
        self.selo_file = selo_file
        self.output_prefix = output_prefix
        self.start_index = start_index
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.output_directory = output_directory
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
                    f"[selo_rgba]colorkey=color=0x00d600:similarity=0.15:blend=0.0[selo_chroma];",
                    f"[selo_chroma]tpad=start_duration=10:color=black@0.0[selo_padded];",
                    f"[segment][selo_padded]overlay=(W-w)/2:(H-h)/2:eof_action=pass[main_with_selo];",
                    f"[main_with_selo][1:v]overlay=(W-w)/2:(H-h)/2:enable='eq(n,0)'[with_image];",
                    f"[with_image]drawtext=text='Parte {part_number}':fontfile='C\:/Windows/Fonts/arial.ttf':fontsize=150:fontcolor=white:borderw=20:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2:enable='eq(n,0)'[final_v];",
                    f"[0:a]atrim=start={current_time}:duration={duration},asetpts=PTS-STARTPTS[final_a]"
                ]

                filter_complex_str = "".join(filter_complex)

                ffmpeg_cmd = [
                    "ffmpeg", "-hwaccel", "cuda",
                    "-i", self.input_file,
                    "-i", self.image_file,
                    "-i", self.selo_file,
                    "-filter_complex", filter_complex_str,
                    "-map", "[final_v]", "-map", "[final_a]",
                    "-c:v", "h264_nvenc", "-preset", "p7", "-rc:v", "vbr", "-cq", "18",
                    "-b:v", "15M", "-profile:v", "high", "-level:v", "4.2",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                    output_file
                ]

                # Executar o comando FFmpeg
                try:
                    self.process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                    stdout, stderr = self.process.communicate()

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
            result = subprocess.run(cmd, capture_output=True, text=True)
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
        self.initUI()

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
        self.output_prefix.setPlaceholderText("Assassins Creed Shadows Parte ")
        prefix_layout.addWidget(prefix_label)
        prefix_layout.addWidget(self.output_prefix)
        config_layout.addLayout(prefix_layout)

        # Start index
        index_layout = QHBoxLayout()
        index_label = QLabel("Índice inicial:")
        self.start_index = QSpinBox()
        self.start_index.setRange(1, 999)
        self.start_index.setValue(101)
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

        # Área de log
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        log_layout.addWidget(self.log_area)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        # Barra de progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

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

    def log(self, message):
        """Adiciona uma mensagem à área de log"""
        self.log_area.append(message)
        # Rola para o final
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def start_cutting(self):
        """Inicia o processo de corte de vídeo"""
        # Obter os valores dos campos
        input_file = self.input_path.text()
        image_file = self.image_path.text()
        selo_file = self.selo_path.text()
        output_prefix = self.output_prefix.text() or "Assassins Creed Shadows Parte "
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

        # Limpar o log e resetar a barra de progresso
        self.log_area.clear()
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

        # Criar e iniciar a thread de processamento
        self.worker = VideoCutterWorker(
            input_file, image_file, selo_file, output_prefix,
            start_index, min_duration, max_duration, output_directory
        )

        # Conectar os sinais
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.log_signal.connect(self.log)
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
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def process_error(self, error_message):
        """Chamado quando ocorre um erro no processo"""
        QMessageBox.critical(self, "Erro", error_message)
        self.log(f"ERRO: {error_message}")
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
