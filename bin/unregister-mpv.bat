@echo off
echo Removing mpv context menu...

reg delete "HKCU\Software\Classes\*\shell\Play with MPV" /f

echo Done.
pause
