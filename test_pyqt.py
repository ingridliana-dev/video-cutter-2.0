import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget

def main():
    # Criar a aplicação
    app = QApplication(sys.argv)
    
    # Criar a janela principal
    window = QMainWindow()
    window.setWindowTitle("Teste PyQt5")
    window.setGeometry(100, 100, 400, 200)
    
    # Criar um widget central e layout
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)
    
    # Adicionar um rótulo
    label = QLabel("PyQt5 está funcionando corretamente!")
    layout.addWidget(label)
    
    # Adicionar um botão
    button = QPushButton("Clique aqui")
    button.clicked.connect(lambda: label.setText("Botão clicado com sucesso!"))
    layout.addWidget(button)
    
    # Definir o widget central
    window.setCentralWidget(central_widget)
    
    # Mostrar a janela
    window.show()
    
    # Executar o loop de eventos
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
