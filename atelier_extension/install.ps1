# 3DDesigner の AtelIer 拡張を、拡張の置き場へ入れる
# 置き場: C:\ProgramData\AtelIer\extensions\3DDesigner\（本体の load_dropins が読む）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dst = Join-Path $env:ProgramData "AtelIer\extensions\3DDesigner"
New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item (Join-Path $PSScriptRoot "*") $dst -Recurse -Force
Copy-Item (Join-Path $root "mesh_core.py") $dst -Force
Copy-Item (Join-Path $root "visual_hull.py") $dst -Force
Write-Host "3DDesigner 拡張を $dst に入れました。AtelIer を起動すると「3Dデザイン」のメニューが出ます。"
