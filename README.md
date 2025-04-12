# Video Cutter GUI

Uma interface gráfica para cortar vídeos longos em segmentos menores, adicionar imagem de capa, selo e texto.

## Funcionalidades

- Corta um vídeo longo em segmentos menores com duração aleatória
- Adiciona uma imagem de capa no primeiro frame de cada segmento
- Adiciona um selo/marca d'água em cada segmento
- Adiciona texto "Parte X" em cada segmento
- Interface gráfica amigável para configurar todos os parâmetros
- Barra de progresso e log detalhado durante o processamento

## Requisitos

Para usar o executável:

- Windows 10 ou superior
- Não é necessário instalar o FFmpeg, pois ele já está incluído no pacote

Para desenvolvimento:

- Python 3.11 ou superior
- PyQt5
- FFmpeg-python

## Como usar

### Versão Executável

1. Baixe a pasta `dist` completa (contém o executável e o FFmpeg)
2. Execute o arquivo `instalar.bat` para criar um atalho na área de trabalho (opcional)
3. Execute o arquivo `Video Cutter.exe`
4. Configure os parâmetros na interface:
   - Selecione o vídeo de entrada
   - Selecione a imagem de capa
   - Selecione o vídeo do selo
   - Configure o prefixo de saída, índice inicial e durações
   - Opcionalmente, selecione uma pasta de saída diferente
5. Clique em "Iniciar Corte" para começar o processamento

**Importante**: Não remova a pasta `ffmpeg` que está junto com o executável, pois ela contém os componentes necessários para o funcionamento do programa.

### Versão de Desenvolvimento

1. Clone o repositório
2. Crie um ambiente virtual: `python -m venv venv`
3. Ative o ambiente virtual: `.\venv\Scripts\activate`
4. Instale as dependências: `pip install PyQt5 ffmpeg-python`
5. Execute o script: `python video_cutter_gui.py`

## Arquivos de Entrada

- **Vídeo de entrada**: O vídeo longo que será cortado em segmentos
- **Imagem de capa**: Uma imagem para ser exibida no primeiro frame de cada segmento
- **Vídeo do selo**: Um vídeo curto para ser usado como marca d'água/selo

## Arquivos de Saída

Os arquivos de saída serão salvos na pasta especificada (ou na mesma pasta do vídeo de entrada, se nenhuma for especificada) com o nome no formato:

`[Prefixo][Número].mp4`

Por exemplo: `Assassins Creed Shadows Parte 101.mp4`

## Baseado no Script Original

Esta interface gráfica é baseada no script PowerShell original `cortar_videos.ps1` que realiza as mesmas funções via linha de comando.

## Licença

Este projeto está licenciado sob a licença MIT.
