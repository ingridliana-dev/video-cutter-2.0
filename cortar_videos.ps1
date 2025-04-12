# Sempre coloque junto desse arquivo, o arquivo do vídeo com o nome input.mp4
# Sempre coloque junto desse arquivo, o arquivo de imágem de capa com o nome image.png
# Sempre coloque junto desse arquivo, o arquivo de vídeo do selo com o nome selo.mp4

$input = "input.mp4"   # Nome do arquivo de entrada
$outputPrefix = "Assassins Creed Shadows Parte "  # <---- Coloque aqui o nome do jogo / nome do arquivo de saida de vídeo
$startIndex = 101       # <--- Coloque aqui o Número inicial dos cortes
$image = "image.png"   # Nome da imagem a ser sobreposta
$selo = "selo.mp4"     # Nome do vídeo do selo a ser sobreposto

# Definindo os valores mínimo e máximo de duração
$minDuration = 90
$maxDuration = 130

# Obtém a duração total do vídeo principal
$totalDuration = [math]::Floor((ffprobe -i $input -show_entries format=duration -v quiet -of csv="p=0") -as [double])

# Obtém a duração do vídeo do selo
$seloDuration = (ffprobe -i $selo -show_entries format=duration -v quiet -of csv="p=0") -as [double]
if ($seloDuration -is [System.DBNull] -or $seloDuration -le 0) {
    Write-Error "Não foi possível obter a duração do selo.mp4 ou a duração é inválida."
    exit 1
}

# Inicializa o tempo atual e o número da parte
$currentTime = 0
$partNumber = $startIndex

while ($currentTime -lt $totalDuration) {
    # Gera duração aleatória entre os limites definidos
    $duration = Get-Random -Minimum $minDuration -Maximum ($maxDuration + 1)

    # Se a duração ultrapassar o fim do vídeo, ajusta para terminar no tempo total
    if ($currentTime + $duration -gt $totalDuration) {
        $duration = $totalDuration - $currentTime
    }
    # Garante que a duração mínima seja respeitada, a menos que seja o último segmento e menor que minDuration
    if ($duration -lt $minDuration -and ($currentTime + $duration) -lt $totalDuration) {
         $duration = $minDuration
         # Recalcula caso o ajuste mínimo ultrapasse o total
         if ($currentTime + $duration -gt $totalDuration) {
             $duration = $totalDuration - $currentTime
         }
    }

    # Garante que o clipe tenha pelo menos 10 segundos + duração do selo para a sobreposição ocorrer
    if ($duration -lt (10 + $seloDuration)) {
       Write-Warning "A duração do clipe ($duration s) é menor que 10s + duração do selo ($seloDuration s). O selo pode não ser exibido completamente neste clipe (Parte $partNumber)."
    }


    $outputFile = "$outputPrefix$partNumber.mp4"

    # Comando FFmpeg usando trim/atrim, tpad com cor transparente e overlay com eof_action=pass
    ffmpeg -hwaccel cuda -i $input -i $image -i $selo `
    -filter_complex `
    "[0:v]trim=start=${currentTime}:duration=${duration},setpts=PTS-STARTPTS[segment]; `
     [2:v]format=rgba,setpts=PTS-STARTPTS[selo_rgba]; `
     [selo_rgba]colorkey=color=0x00d600:similarity=0.15:blend=0.0[selo_chroma]; `
     [selo_chroma]tpad=start_duration=10:color=black@0.0[selo_padded]; `
     [segment][selo_padded]overlay=(W-w)/2:(H-h)/2:eof_action=pass[main_with_selo]; `
     [main_with_selo][1:v]overlay=(W-w)/2:(H-h)/2:enable='eq(n,0)'[with_image]; `
     [with_image]drawtext=text='Parte ${partNumber}':fontfile='C\:/Windows/Fonts/arial.ttf':fontsize=150:fontcolor=white:borderw=20:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2:enable='eq(n,0)'[final_v]; `
     [0:a]atrim=start=${currentTime}:duration=${duration},asetpts=PTS-STARTPTS[final_a]" `
    -map "[final_v]" -map "[final_a]" `
    -c:v h264_nvenc -preset p7 -rc:v vbr -cq 18 -b:v 15M -profile:v high -level:v 4.2 `
    -c:a aac -b:a 192k -movflags +faststart $outputFile

    $currentTime += $duration
    $partNumber++
}

Write-Host "Processo concluído!"
