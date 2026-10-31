# Builds Sift.exe (one file, no console) into PhotoWork\sift-build\dist.
# Needs the venv from "Start Sift.bat" plus:  .venv-sift\Scripts\python -m pip install pyinstaller
$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$py = "$HOME\PhotoWork\.venv-sift\Scripts"
$b = "$HOME\PhotoWork\sift-build"   # outside OneDrive so the build doesn't sync

if (-not (Test-Path "$py\pyinstaller.exe")) { & "$py\python.exe" -m pip install -q pyinstaller }
& "$py\python.exe" "$src\make_icon.py"
& "$py\python.exe" "$src\make_website.py"
& "$py\pyinstaller.exe" --noconfirm --onefile --windowed --name Sift --icon "$src\sift.ico" `
  --distpath "$b\dist" --workpath "$b\work" --specpath "$b" `
  --add-data "$src\web;web" --add-data "$src\models;models" --add-data "$src\travel_places.csv;." `
  --add-data "$src\LICENSE;." --add-data "$src\THIRD_PARTY_NOTICES.md;." `
  --collect-data reverse_geocoder --collect-data cv2 `
  --exclude-module tkinter --exclude-module matplotlib --exclude-module IPython --exclude-module pytest `
  --paths "$src" "$src\app.py"
if ($LASTEXITCODE) { throw "PyInstaller failed" }
$mb = [math]::Round((Get-Item "$b\dist\Sift.exe").Length / 1MB)
Write-Host "Built $b\dist\Sift.exe ($mb MB)"
