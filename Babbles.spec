# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

block_cipher = None

# ── Dynamic Path Resolution ──────────────────────────────────────────────────
# Resolve virtual environment paths for bundling assets and dynamic libraries
venv_site_packages = Path(".venv/Lib/site-packages")
if not venv_site_packages.exists():
    # Fallback/heuristic search for site-packages in active env
    for p in sys.path:
        if "site-packages" in p and ".venv" in p:
            venv_site_packages = Path(p)
            break

print(f"[*] PyInstaller spec: resolved virtual env site-packages at: {venv_site_packages}")

# ── Bundled Data Files (datas) ────────────────────────────────────────────────
datas = [
    ('config.json', '.'),  # Bundle default config file as a fallback
]

# Robust CustomTkinter Asset Bundling
try:
    import customtkinter
    ctk_path = os.path.dirname(customtkinter.__file__)
    datas.append((ctk_path, 'customtkinter'))
    print(f"[*] CustomTkinter assets found and added from: {ctk_path}")
except ImportError:
    print("[!] Warning: customtkinter is not installed or importable! Theme/fonts might fail.")

# Robust Faster Whisper ONNX VAD Assets Bundling
try:
    import faster_whisper
    fw_path = os.path.dirname(faster_whisper.__file__)
    fw_assets = os.path.join(fw_path, 'assets')
    if os.path.exists(fw_assets):
        datas.append((fw_assets, 'faster_whisper/assets'))
        print(f"[*] Faster-whisper VAD assets found and added from: {fw_assets}")
except ImportError:
    print("[!] Warning: faster-whisper is not installed or importable! VAD model will fail.")

# ── Bundled Dynamic Link Libraries (binaries) ─────────────────────────────────
binaries = []

# Dynamically search and bundle all NVIDIA CUDA/cuBLAS DLLs
# This is crucial for GPU acceleration (CTranslate2 float16) to work out-of-the-box
if venv_site_packages.exists():
    nvidia_dir = venv_site_packages / "nvidia"
    if nvidia_dir.exists():
        dll_count = 0
        for dll_path in nvidia_dir.rglob("*.dll"):
            # Package all NVIDIA runtime DLLs in the root folder of the executable
            binaries.append((str(dll_path), '.'))
            dll_count += 1
        print(f"[*] NVIDIA CUDA packages located: bundled {dll_count} dynamic libraries (.dll) for GPU acceleration.")
    else:
        print("[!] Warning: 'nvidia' folder not found in site-packages. GPU acceleration DLLs will not be bundled.")
else:
    print("[!] Warning: Virtual environment site-packages folder not found! Unable to bundle CUDA DLLs.")

# ── Hidden Imports ────────────────────────────────────────────────────────────
hiddenimports = [
    'customtkinter',
    'sounddevice',
    'numpy',
    'keyboard',
    'pyperclip',
    'pystray',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'faster_whisper',
    'ctranslate2',
    'logging',
    'logging.handlers',
    'queue',
    'win32ctypes',
]

# ── Analysis Phase ────────────────────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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

# ── Target 1: Standalone Single-File Executable ──────────────────────────────
# Ideal for single-file sharing. Self-extracting at startup.
exe_standalone = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='Babbles_Standalone',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keeps standard console so we can programmatically show/hide it based on config
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,  # Requests Windows Administrator privilege prompt at double-click
)

# ── Target 2: Folder-Based Distribution ───────────────────────────────────────
# Ideal for sharing as a folder/zip. Launches instantly without self-extraction.
exe_folder = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='Babbles',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Programmatic console show/hide
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,  # Requests Administrator elevation
)

coll = COLLECT(
    exe_folder,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Babbles',
)
