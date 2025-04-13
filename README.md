# Video Cutter GUI

Uma interface gráfica para cortar vídeos longos em segmentos menores, adicionar imagem de capa, selo e texto.

## Funcionalidades

- Corta um vídeo longo em segmentos menores com duração aleatória
- Adiciona uma imagem de capa no primeiro frame de cada segmento
- Adiciona um selo/marca d'água em cada segmento com efeito de chroma key personalizável
- Adiciona texto "Parte X" em cada segmento
- Suporte a vídeos de qualquer resolução (horizontal, vertical ou quadrado)
- Redimensionamento automático da imagem de capa e vídeo do selo quando necessário
- Interface gráfica amigável para configurar todos os parâmetros
- Barra de progresso e log detalhado durante o processamento
- Botão para abrir diretamente a pasta onde os vídeos processados são salvos

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
2. Execute o arquivo `Video Cutter.exe` diretamente da pasta
3. Configure os parâmetros na interface:
   - Selecione o vídeo de entrada
   - Selecione a imagem de capa
   - Selecione o vídeo do selo
   - Configure o prefixo de saída, índice inicial e durações
   - Opcionalmente, selecione uma pasta de saída diferente
4. Configure as opções de Chroma Key para o selo (cor, similaridade e suavidade)
5. Clique em "Iniciar Corte" para começar o processamento
6. Use o botão "Abrir Pasta" para acessar diretamente a pasta onde os vídeos processados foram salvos

**Importante**: Não remova a pasta `ffmpeg` que está junto com o executável, pois ela contém os componentes necessários para o funcionamento do programa.

### Recomendações para melhor desempenho

- **Resolução dos arquivos**: Para obter os melhores resultados, use imagem de capa e vídeo de selo com a mesma resolução do vídeo que será cortado. Isso evita redimensionamento e mantém a qualidade original.

- **Vídeos verticais**: Este programa é especialmente recomendado para cortes de vídeos verticais (formato 9:16, como 1080x1920), ideal para conteúdo de redes sociais como TikTok, Instagram Reels e YouTube Shorts.

- **Chroma Key**: Para melhores resultados com o selo, use um fundo verde sólido (ou outra cor sólida) e ajuste os parâmetros de similaridade e suavidade para obter bordas limpas.

### Configurações de Chroma Key

O aplicativo permite personalizar o efeito de chroma key aplicado ao vídeo do selo:

- **Cor do Chroma Key**: A cor que será tornada transparente (padrão: verde - 0x00d600)
- **Similaridade**: Quanto maior o valor, mais tons da cor serão removidos (0.01-1.0)
- **Suavidade de borda**: Quanto maior o valor, mais suaves serão as bordas (0.0-1.0)

### Versão de Desenvolvimento

1. Clone o repositório
2. Crie um ambiente virtual: `python -m venv venv`
3. Ative o ambiente virtual: `.\venv\Scripts\activate`
4. Instale as dependências: `pip install PyQt5 ffmpeg-python`
5. Execute o script: `python video_cutter_gui.py`

## Arquivos de Entrada

- **Vídeo de entrada**: O vídeo longo que será cortado em segmentos (qualquer resolução)
- **Imagem de capa**: Uma imagem para ser exibida no primeiro frame de cada segmento (será redimensionada automaticamente se necessário)
- **Vídeo do selo**: Um vídeo curto para ser usado como marca d'água/selo (será redimensionado automaticamente se necessário)

O aplicativo detecta automaticamente a resolução de todos os arquivos e realiza os ajustes necessários para garantir a compatibilidade.

## Arquivos de Saída

Os arquivos de saída serão salvos na pasta especificada (ou na mesma pasta do vídeo de entrada, se nenhuma for especificada) com o nome no formato:

`[Prefixo] [Número].mp4`

Por exemplo: `Video Vertical Parte 101.mp4`

## Baseado no Script Original

Esta interface gráfica é baseada no script PowerShell original `cortar_videos.ps1` que realiza as mesmas funções via linha de comando.

## Licença

Este projeto está licenciado sob a licença MIT.
