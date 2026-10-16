<#
.SYNOPSIS
  Quick video effect presets for ffmpeg. Thin wrapper over presets\vfx.py, which uses the same engine
  as the vfast Effects panel (gui\core\effects.py + gui\core\render.py): one ffmpeg pass per run.

.EXAMPLE
  .\vfx.ps1 -List
  .\vfx.ps1 cinematic video.mp4
  .\vfx.ps1 cinematic,fade,loudnorm video.mp4 hasil.mp4
  .\vfx.ps1 shorts clip.mp4 -Speed 1.1 -Overlay
  .\vfx.ps1 caption clip.mp4 -Text "Halo dunia" -Duration 5
  .\vfx.ps1 watermark clip.mp4 -Logo logo.png
#>
$root = Split-Path $PSScriptRoot -Parent
$py = Join-Path $root 'venv-gui\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }
# PowerShell reads an unquoted  a,b,c  as an ARRAY, not the string "a,b,c": join such arguments back.
$fixed = foreach ($a in $args) { if ($a -is [array]) { $a -join ',' } else { $a } }
& $py (Join-Path $PSScriptRoot 'vfx.py') @fixed
exit $LASTEXITCODE
