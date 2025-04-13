import sys
import traceback

print("Iniciando teste simples...")

try:
    from PyQt5.QtWidgets import QApplication, QLabel
    print("PyQt5 importado com sucesso!")
    
    app = QApplication(sys.argv)
    print("QApplication criada")
    
    label = QLabel("Teste PyQt5")
    print("Label criada")
    
    label.show()
    print("Label exibida")
    
    print("Iniciando loop de eventos...")
    sys.exit(app.exec_())
except Exception as e:
    print(f"Erro: {e}")
    traceback.print_exc()
