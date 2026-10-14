@echo off
setlocal

set "MPV_PATH=%~dp0mpv.exe"
if "%MPV_PATH:~-1%"=="\" set "MPV_PATH=%MPV_PATH:~0,-1%"

echo Registering mpv context menu...

:: Create main key
reg add "HKCU\Software\Classes\*\shell\Play with MPV" /ve /d "Play with MPV" /f
reg add "HKCU\Software\Classes\*\shell\Play with MPV" /v "Icon" /d "%MPV_PATH%" /f

:: Restrict to common media extensions (added .webm)
reg add "HKCU\Software\Classes\*\shell\Play with MPV" /v "AppliesTo" /d ^
"System.FileExtension:=\".mp4\" OR ^
System.FileExtension:=\".mkv\" OR ^
System.FileExtension:=\".avi\" OR ^
System.FileExtension:=\".mov\" OR ^
System.FileExtension:=\".wmv\" OR ^
System.FileExtension:=\".flv\" OR ^
System.FileExtension:=\".webm\" OR ^
System.FileExtension:=\".mp3\" OR ^
System.FileExtension:=\".wav\" OR ^
System.FileExtension:=\".flac\" OR ^
System.FileExtension:=\".aac\"" /f

:: Command
reg add "HKCU\Software\Classes\*\shell\Play with MPV\command" /ve /d "\"%MPV_PATH%\" \"%%1\" --osd-level=3 --osd-fractions" /f

echo Done.
pause
