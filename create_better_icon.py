from PIL import Image
import os
import sys

def create_ico(png_file, ico_file):
    """
    Cria um arquivo .ico a partir de um arquivo .png com múltiplas resoluções
    """
    try:
        # Abrir a imagem PNG
        img = Image.open(png_file)
        
        # Verificar se a imagem tem canal alfa (transparência)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Criar versões em diferentes tamanhos
        sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        icons = []
        
        for size in sizes:
            # Redimensionar a imagem mantendo a proporção
            resized_img = img.resize(size, Image.LANCZOS)
            icons.append(resized_img)
        
        # Salvar como ICO com todas as resoluções
        icons[0].save(ico_file, format='ICO', sizes=sizes, append_images=icons[1:])
        
        print(f"Arquivo ICO criado com sucesso: {ico_file}")
        return True
    except Exception as e:
        print(f"Erro ao criar o arquivo ICO: {e}")
        return False

if __name__ == "__main__":
    # Usar o arquivo PNG fornecido
    png_file = "video-cutter-icone.png"
    ico_file = "video-cutter-icone.ico"
    
    if not os.path.exists(png_file):
        print(f"Erro: O arquivo {png_file} não foi encontrado.")
        sys.exit(1)
    
    success = create_ico(png_file, ico_file)
    if not success:
        sys.exit(1)
