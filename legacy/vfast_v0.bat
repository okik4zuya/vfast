@echo off
title Vfast Video Tool
color 0A

:menu
cls
echo ================================
echo        Vfast Video Tool
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
echo Reading videos from current folder:
echo %cd%
echo.

setlocal EnableDelayedExpansion
set i=0
for %%F in (*.mp4 *.mkv *.mov *.avi) do (
    set /a i+=1
    echo !i!. %%F
    set "vid[!i!]=%%~fF"
)

if %i%==0 (
    echo No videos found.
    pause
    endlocal
    goto menu
)

echo.
echo Enter numbers to merge (space-separated, order matters)
echo Example: 1 3 4
set /p picks=Selection:

del filelist.txt 2>nul

for %%N in (%picks%) do (
    set "p=!vid[%%N]!"
    echo file '!p!'>> filelist.txt
)

bin\ffmpeg -f concat -safe 0 -i filelist.txt -c copy merged_video.mp4

endlocal
echo.
echo Done! Output: merged_video.mp4
pause
goto menu


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

echo Enter working directory (contains media files and bin\ffmpeg.exe):
set /p workdir=Folder path:

if not exist "%workdir%\bin\ffmpeg.exe" (
    echo ERROR: ffmpeg.exe not found in "%workdir%\bin"
    pause
    goto menu
)

if not exist "%workdir%\bin\ffprobe.exe" (
    echo ERROR: ffprobe.exe not found in "%workdir%\bin"
    pause
    goto menu
)

pushd "%workdir%"
setlocal EnableDelayedExpansion

:: -------------------------
:: LIST VIDEOS WITH DURATION
:: -------------------------
echo.
echo Available VIDEOS:
set v=0
for %%V in (*.mp4 *.mkv *.mov *.avi) do (
    set /a v+=1
    for /f "delims=" %%D in ('
        bin\ffprobe.exe -v error -show_entries format^=duration ^
        -of default^=noprint_wrappers^=1:nokey^=1 "%%V"
    ') do set "dur=%%D"

    set "dur=!dur:~0,-4!"
    echo !v!. %%V  [!dur! sec]
    set "video[!v!]=%%~fV"
)

if %v%==0 (
    echo No video files found.
    pause
    endlocal
    popd
    goto menu
)


:: -------------------------
:: LIST AUDIOS WITH DURATION
:: -------------------------
echo.
echo Available AUDIOS:
set a=0
for %%A in (*.mp3 *.wav *.aac *.m4a *.flac) do (
    set /a a+=1
    for /f "delims=" %%D in ('
        bin\ffprobe.exe -v error -show_entries format^=duration ^
        -of default^=noprint_wrappers^=1:nokey^=1 "%%A"
    ') do set "adur=%%D"

    set "adur=!adur:~0,-4!"
    echo !a!. %%A  [!adur! sec]
    set "audio[!a!]=%%~fA"
)

if %a%==0 (
    echo No audio files found.
    pause
    endlocal
    popd
    goto menu
)

echo.
set /p vpick=Select video number:
set "videoFile=!video[%vpick%]!"
echo.
set /p apick=Select audio number:
set "audioFile=!audio[%apick%]!"

:: -------------------------
:: OUTPUT NAME FROM VIDEO
:: -------------------------
for %%F in ("%videoFile%") do (
    set "vname=%%~nF"
    set "vext=%%~xF"
)

bin\ffmpeg.exe -i "%videoFile%" -i "%audioFile%" -c:v copy -c:a aac -shortest "merged_%vname%%vext%"

endlocal
popd

echo.
echo Done! Output: %workdir%\merged_%vname%%vext%
pause
goto menu
