from PIL import Image, ImageDraw
import os

# Criar uma imagem quadrada com fundo transparente
size = 256
image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)

# Definir cores
handle_color = (50, 50, 50, 255)  # Cinza escuro
blade_color = (200, 200, 200, 255)  # Cinza claro
highlight_color = (240, 240, 240, 255)  # Branco acinzentado

# Desenhar as lâminas da tesoura
# Primeira lâmina (superior)
blade_points = [
    (size * 0.3, size * 0.2),  # Ponta superior
    (size * 0.7, size * 0.4),  # Ponta inferior direita
    (size * 0.65, size * 0.45),  # Curva interna
    (size * 0.25, size * 0.25)   # Curva interna superior
]
draw.polygon(blade_points, fill=blade_color)

# Segunda lâmina (inferior)
blade_points = [
    (size * 0.3, size * 0.8),  # Ponta inferior
    (size * 0.7, size * 0.6),  # Ponta superior direita
    (size * 0.65, size * 0.55),  # Curva interna
    (size * 0.25, size * 0.75)   # Curva interna inferior
]
draw.polygon(blade_points, fill=blade_color)

# Desenhar os cabos da tesoura
# Primeiro cabo (superior)
handle_points = [
    (size * 0.25, size * 0.25),  # Conexão com a lâmina
    (size * 0.15, size * 0.35),  # Curva externa
    (size * 0.1, size * 0.3),    # Ponta do cabo
    (size * 0.2, size * 0.2)     # Curva interna
]
draw.polygon(handle_points, fill=handle_color)

# Segundo cabo (inferior)
handle_points = [
    (size * 0.25, size * 0.75),  # Conexão com a lâmina
    (size * 0.15, size * 0.65),  # Curva externa
    (size * 0.1, size * 0.7),    # Ponta do cabo
    (size * 0.2, size * 0.8)     # Curva interna
]
draw.polygon(handle_points, fill=handle_color)

# Desenhar o parafuso central
draw.ellipse([(size * 0.28, size * 0.48), (size * 0.32, size * 0.52)], fill=(100, 100, 100))

# Adicionar alguns destaques para dar profundidade
# Destaque na primeira lâmina
highlight_points = [
    (size * 0.35, size * 0.25),
    (size * 0.65, size * 0.4),
    (size * 0.63, size * 0.42),
    (size * 0.33, size * 0.27)
]
draw.polygon(highlight_points, fill=highlight_color)

# Destaque na segunda lâmina
highlight_points = [
    (size * 0.35, size * 0.75),
    (size * 0.65, size * 0.6),
    (size * 0.63, size * 0.58),
    (size * 0.33, size * 0.73)
]
draw.polygon(highlight_points, fill=highlight_color)

# Salvar a imagem em vários tamanhos para o arquivo .ico
sizes = [16, 32, 48, 64, 128, 256]
icon_images = []

for s in sizes:
    resized_img = image.resize((s, s), Image.LANCZOS)
    icon_images.append(resized_img)

# Salvar como PNG para visualização
image.save('scissors_icon.png')

# Salvar como ICO para o aplicativo
image.save('scissors_icon.ico', sizes=[(s, s) for s in sizes])

print(f"Ícones criados: scissors_icon.png e scissors_icon.ico")
