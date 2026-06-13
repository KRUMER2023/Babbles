# build_exe.ps1
# ─────────────
# Babbles Speech-to-Text Executable Build Script.
# This script automates packaging the project into a portable Windows software.
# Run from PowerShell in the project root directory.

$ErrorActionPreference = "Stop"

# ── 1. Resolve Script Directory ──────────────────────────────────────────────
$scriptDir = $PSScriptRoot
if (-not $scriptDir) {
    $scriptDir = $pwd.Path
}
Write-Host "===================================================" -ForegroundColor Green
Write-Host "         BABBLES EXE BUILD AUTOMATION SCRIPT         " -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
Write-Host "[*] Working directory resolved to: $scriptDir" -ForegroundColor Cyan

# ── 2. Activate Virtual Environment ──────────────────────────────────────────
$activationScript = Join-Path $scriptDir ".venv\Scripts\Activate.ps1"
if (Test-Path $activationScript) {
    Write-Host "[*] Activating virtual environment..." -ForegroundColor Cyan
    . $activationScript
} else {
    Write-Error "Virtual environment (.venv) was not found in $scriptDir! Please create it and run requirements setup first."
    exit 1
}

# ── 2B. Resolve Tcl/Tk Environment Variables ──────────────────────────────────
# This is a critical workaround for PyInstaller in virtual environments on Windows.
# If these environment variables are not set during build time, PyInstaller's internal
# script fails to initialize Tcl/Tk, flags the installation as broken, and excludes Tkinter.
$pyvenvCfg = Join-Path $scriptDir ".venv\pyvenv.cfg"
if (Test-Path $pyvenvCfg) {
    $cfgLines = Get-Content $pyvenvCfg
    $homeLine = $cfgLines | Where-Object { $_ -match "^home\s*=" }
    if ($homeLine) {
        $sysPythonHome = ($homeLine -split "=")[1].Trim()
        $tclPath = Join-Path $sysPythonHome "tcl\tcl8.6"
        $tkPath = Join-Path $sysPythonHome "tcl\tk8.6"
        if (Test-Path $tclPath) {
            $env:TCL_LIBRARY = $tclPath
            $env:TK_LIBRARY = $tkPath
            Write-Host "[*] Dynamic Tcl/Tk paths resolved for build environment:" -ForegroundColor Green
            Write-Host "    TCL_LIBRARY = $env:TCL_LIBRARY" -ForegroundColor Gray
            Write-Host "    TK_LIBRARY  = $env:TK_LIBRARY" -ForegroundColor Gray
        }
    }
}

# ── 3. Pre-Bundle Whisper Models from System Cache ───────────────────────────
$localModelsDir = Join-Path $scriptDir "models"
if (-not (Test-Path $localModelsDir)) {
    New-Item -ItemType Directory -Path $localModelsDir -Force | Out-Null
    Write-Host "[+] Created local models directory at: $localModelsDir" -ForegroundColor Green
}

$hfCacheDir = Join-Path $env:USERPROFILE ".cache\huggingface\hub"
if (Test-Path $hfCacheDir) {
    Write-Host "[*] Located system Hugging Face cache folder at: $hfCacheDir" -ForegroundColor Cyan
    
    # Models to bundle by default for instant offline availability
    $modelsToCopy = @(
        "models--Systran--faster-whisper-base",
        "models--Systran--faster-whisper-small"
    )
    
    foreach ($model in $modelsToCopy) {
        $sourcePath = Join-Path $hfCacheDir $model
        $destPath = Join-Path $localModelsDir $model
        
        if (Test-Path $sourcePath) {
            if (-not (Test-Path $destPath)) {
                Write-Host "[*] Copying pre-downloaded model '$model' to local models folder (this may take a few seconds)..." -ForegroundColor Yellow
                # Copy with subfolders recursively
                Copy-Item -Path $sourcePath -Destination $destPath -Recurse -Force
                Write-Host "[+] Successfully copied '$model' to local models." -ForegroundColor Green
            } else {
                Write-Host "[*] Model '$model' is already cached in local models. Skipping copy." -ForegroundColor Gray
            }
        } else {
            Write-Host "[-] Model '$model' not found in system cache ($sourcePath). It will be dynamically downloaded on first run." -ForegroundColor DarkYellow
        }
    }
} else {
    Write-Host "[-] System Hugging Face cache directory not found at $hfCacheDir. Models will be downloaded on first run." -ForegroundColor DarkYellow
}

# ── 4. Execute PyInstaller Compilation ────────────────────────────────────────
Write-Host "[*] Compiling Babbles executable using custom Babbles.spec..." -ForegroundColor Cyan
Write-Host "[*] Cleaning old build and dist directories..." -ForegroundColor Gray

$buildDir = Join-Path $scriptDir "build"
$distDir = Join-Path $scriptDir "dist"

if (Test-Path $buildDir) {
    Remove-Item -Path $buildDir -Recurse -Force -ErrorAction SilentlyContinue | Out-Null
}
if (Test-Path $distDir) {
    try {
        Remove-Item -Path (Join-Path $distDir "Babbles") -Recurse -Force -ErrorAction SilentlyContinue | Out-Null
        Remove-Item -Path (Join-Path $distDir "Babbles_Standalone.exe") -Force -ErrorAction SilentlyContinue | Out-Null
        Remove-Item -Path (Join-Path $distDir "config.json") -Force -ErrorAction SilentlyContinue | Out-Null
        Remove-Item -Path (Join-Path $distDir "models") -Recurse -Force -ErrorAction SilentlyContinue | Out-Null
    } catch {
        Write-Host "[!] Warning: Some files in dist could not be cleaned." -ForegroundColor Yellow
    }
}

# Run PyInstaller with clean flag
pyinstaller --clean Babbles.spec

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller compilation failed!"
    exit 1
}
Write-Host "[+] PyInstaller compilation completed successfully." -ForegroundColor Green

# ── 5. Prepare Distribution Folders ──────────────────────────────────────────
Write-Host "[*] Preparing files inside distribution folders..." -ForegroundColor Cyan

$configSrc = Join-Path $scriptDir "config.json"

# A. Set up Standalone distribution folder (dist/)
$distStandaloneDir = Join-Path $scriptDir "dist"
if (Test-Path $distStandaloneDir) {
    # Copy default config.json for convenience
    if (Test-Path $configSrc) {
        Copy-Item -Path $configSrc -Destination (Join-Path $distStandaloneDir "config.json") -Force
    }
    # Copy local models folder next to standalone EXE
    if (Test-Path $localModelsDir) {
        $modelsDestStandalone = Join-Path $distStandaloneDir "models"
        if (-not (Test-Path $modelsDestStandalone)) {
            Write-Host "[*] Copying cached models to standalone dist directory..." -ForegroundColor Yellow
            Copy-Item -Path $localModelsDir -Destination $modelsDestStandalone -Recurse -Force
        } else {
            Write-Host "[*] Standalone models directory already up-to-date." -ForegroundColor Gray
        }
    }
}

# B. Set up Folder-Based distribution folder (dist/Babbles/)
$distFolderDir = Join-Path $scriptDir "dist\Babbles"
if (Test-Path $distFolderDir) {
    # Copy default config.json inside the app folder
    if (Test-Path $configSrc) {
        Copy-Item -Path $configSrc -Destination (Join-Path $distFolderDir "config.json") -Force
    }
    # Copy local models folder inside the app folder
    if (Test-Path $localModelsDir) {
        $modelsDestFolder = Join-Path $distFolderDir "models"
        if (-not (Test-Path $modelsDestFolder)) {
            Write-Host "[*] Copying cached models to folder-based dist directory..." -ForegroundColor Yellow
            Copy-Item -Path $localModelsDir -Destination $modelsDestFolder -Recurse -Force
        } else {
            Write-Host "[*] Folder-based models directory already up-to-date." -ForegroundColor Gray
        }
    }
}

Write-Host "===================================================" -ForegroundColor Green
Write-Host "         BUILD COMPLETED SUCCESSFULLY!              " -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
Write-Host "[+] Single-file executable ready in:  dist\Babbles_Standalone.exe" -ForegroundColor Green
Write-Host "[+] Folder-based software ready in:  dist\Babbles\" -ForegroundColor Green
Write-Host "[*] You can share either target. The models are pre-packaged for instant offline execution." -ForegroundColor Cyan
