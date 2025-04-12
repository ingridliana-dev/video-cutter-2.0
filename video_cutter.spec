# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

# Verificar se a pasta ffmpeg existe
ffmpeg_dir = os.path.join(os.getcwd(), 'ffmpeg')
ffmpeg_binaries = []

if os.path.exists(ffmpeg_dir):
    # Adicionar os binários do FFmpeg
    ffmpeg_bin_dir = os.path.join(ffmpeg_dir, 'bin')
    if os.path.exists(ffmpeg_bin_dir):
        for file in os.listdir(ffmpeg_bin_dir):
            if file.endswith('.exe') or file.endswith('.dll'):
                source = os.path.join(ffmpeg_bin_dir, file)
                dest = os.path.join('ffmpeg', 'bin', file)
                ffmpeg_binaries.append((source, dest))

a = Analysis(
    ['video_cutter_gui.py'],
    pathex=[],
    binaries=ffmpeg_binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Video Cutter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='app_icon.ico',  # Descomente esta linha quando tiver um ícone
)
