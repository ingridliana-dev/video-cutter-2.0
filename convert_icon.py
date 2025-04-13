from PIL import Image
import os

# Caminho para a imagem PNG
input_file = 'video-cutter-icone.png'
output_file = 'video-cutter-icone.ico'

# Verificar se o arquivo existe
if not os.path.exists(input_file):
    print(f"Erro: O arquivo {input_file} não foi encontrado.")
    exit(1)

# Abrir a imagem
img = Image.open(input_file)

# Tamanhos de ícone para Windows
sizes = [16, 32, 48, 64, 128, 256]
icon_images = []

# Redimensionar a imagem para cada tamanho
for size in sizes:
    resized_img = img.resize((size, size), Image.LANCZOS)
    icon_images.append(resized_img)

# Salvar como ICO
img.save(output_file, sizes=[(s, s) for s in sizes])

print(f"Ícone criado com sucesso: {output_file}")
