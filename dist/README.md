# Video Cutter - Instruções de Uso

Este é um aplicativo para cortar vídeos longos em segmentos menores, adicionar imagem de capa, selo e texto.

## Como usar o programa

1. Execute o arquivo `Video Cutter.exe` diretamente desta pasta
2. Configure os parâmetros na interface:
   - Selecione o vídeo de entrada (qualquer resolução)
   - Selecione a imagem de capa
   - Selecione o vídeo do selo
   - Configure o prefixo de saída, índice inicial e durações
   - Opcionalmente, selecione uma pasta de saída diferente
3. Configure as opções de Chroma Key para o selo (cor, similaridade e suavidade)
4. Clique em "Iniciar Corte" para começar o processamento
5. Use o botão "Abrir Pasta" para acessar diretamente a pasta onde os vídeos processados foram salvos

## Recomendações para melhor desempenho

- **Resolução dos arquivos**: Para obter os melhores resultados, use imagem de capa e vídeo de selo com a mesma resolução do vídeo que será cortado. Isso evita redimensionamento e mantém a qualidade original.

- **Vídeos verticais**: Este programa é especialmente recomendado para cortes de vídeos verticais (formato 9:16, como 1080x1920), ideal para conteúdo de redes sociais como TikTok, Instagram Reels e YouTube Shorts.

- **Chroma Key**: Para melhores resultados com o selo, use um fundo verde sólido (ou outra cor sólida) e ajuste os parâmetros de similaridade e suavidade para obter bordas limpas.

## Importante

- **Não remova a pasta `ffmpeg`**: Esta pasta contém os componentes necessários para o funcionamento do programa.

- **Requisitos do sistema**: Windows 10 ou superior.

- **Problemas comuns**: Se o programa não iniciar, verifique se todos os arquivos estão presentes, incluindo a pasta `ffmpeg` e seus executáveis.

## Dicas de uso

- Para vídeos muito longos, o processamento pode demorar. Seja paciente e observe o progresso na barra e no log.

- O tamanho do texto "Parte X" é ajustado automaticamente com base na resolução do vídeo.

- Se você precisar cancelar o processamento, use o botão "Cancelar" e confirme a ação.

- Após o processamento, você pode usar o botão "Abrir Pasta" para acessar rapidamente os vídeos gerados.
