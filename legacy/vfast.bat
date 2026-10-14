@echo off
title Vfast Video Tool
color 0A

:menu
cls
echo ================================
echo        FFmpeg Video Tool
echo ================================
echo.
echo 1. Merge videos
echo 2. Change video speed
echo 3. Merge video and audio
echo 0. Exit
echo.
set /p choice=Select option:

if "%choice%"=="1" goto merge_videos
if "%choice%"=="2" goto change_speed
if "%choice%"=="3" goto merge_video_audio
if "%choice%"=="0" exit
goto menu

:: ================================
:: 1. MERGE VIDEOS
:: ================================
:merge_videos
cls
echo --- Merge Videos ---
echo.
echo Enter FULL paths or filenames
echo One by one. Type DONE when finished. Type 0 to exit.
echo.

del filelist.txt 2>nul

:merge_loop
set /p vid=Video file:
if /I "%vid%"=="DONE" goto do_merge
if /I "%vid%"=="0" goto menu

for %%F in ("%vid%") do (
    echo file '%%~fF'>> filelist.txt
)

goto merge_loop

:do_merge
ffmpeg -f concat -safe 0 -i filelist.txt -c copy merged_video.mp4

echo.
echo Done! Output: merged_video.mp4
pause
goto menu

:: ================================
:: 2. CHANGE VIDEO SPEED
:: ================================
:change_speed
cls
echo --- Change Video Speed ---
echo.
set /p input=Input video (full path or filename):
set /p speed=Speed multiplier (e.g. 0.5 slow, 1 normal, 2 fast):

for %%F in ("%input%") do (
    set "name=%%~nF"
    set "ext=%%~xF"
)

ffmpeg -i "%input%" ^
-filter_complex "[0:v]setpts=PTS/%speed%[v];[0:a]atempo=%speed%[a]" ^
-map "[v]" -map "[a]" "speed_%speed%_%name%%ext%"

echo.
echo Done! Output: speed_%speed%_%name%%ext%
pause
goto menu

:: ================================
:: 3. MERGE VIDEO AND AUDIO
:: ================================
:merge_video_audio
cls
echo --- Merge Video and Audio ---
echo.
set /p video=Video file (full path or filename):
set /p audio=Audio file (full path or filename):

for %%V in ("%video%") do (
    set "vname=%%~nV"
    set "vext=%%~xV"
)

ffmpeg -i "%video%" -i "%audio%" -c:v copy -c:a aac -shortest "merged_%vname%%vext%"

echo.
echo Done! Output: merged_%vname%%vext%
pause
goto menu

