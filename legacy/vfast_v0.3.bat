@echo off
title Vfast Video Tool
color 0A

:: ================================
:: TOOL PATH SETUP
:: ================================
set "TOOL_DIR=%~dp0"
set "FFMPEG=%TOOL_DIR%bin\ffmpeg.exe"
set "FFPROBE=%TOOL_DIR%bin\ffprobe.exe"

:: ================================
:: SELECT PROJECT FOLDER (MANUAL)
:: ================================
cls
echo ================================
echo        Vfast Video Tool
echo ================================
echo.
echo Paste PROJECT FOLDER path
echo Example: D:\Projects\Wedding_Edit
echo.
set /p PROJECT_DIR=Project folder:

if not exist "%PROJECT_DIR%\" (
    echo.
    echo Folder not found!
    pause
    exit
)

pushd "%PROJECT_DIR%"

:: ================================
:: MAIN MENU
:: ================================
:menu
cls
echo ================================
echo        Vfast Video Tool
echo ================================
echo Project:
echo %PROJECT_DIR%
echo ================================
echo.
echo 1. Merge videos or audios
echo 2. Change video speed
echo 3. Add audio to video
echo 4. Remove audio
echo 5. Extract audio
echo 6. Trim video or audio
echo 0. Exit
echo.
set /p choice=Select option:

if "%choice%"=="1" goto merge_videos
if "%choice%"=="2" goto change_speed
if "%choice%"=="3" goto merge_video_audio
if "%choice%"=="4" goto remove_audio
if "%choice%"=="5" goto extract_audio
if "%choice%"=="6" goto trim_media
if "%choice%"=="0" goto exit_tool
goto menu

:: ================================
:: 1. MERGE VIDEOS & AUDIOS
:: ================================
:merge_videos
cls
echo --- Concatenate Media ---
echo.
echo Working folder:
echo %PROJECT_DIR%
echo.
echo 1. Merge VIDEOS
echo 2. Merge AUDIOS
echo.
set /p choice=Select option (1 or 2):

if "%choice%"=="1" goto merge_only_videos
if "%choice%"=="2" goto merge_only_audios

echo Invalid choice.
pause
goto merge_videos

:: =========================
:: MERGE VIDEOS ONLY
:: =========================
:merge_only_videos
cls
echo --- Merge VIDEOS ---
echo.

setlocal EnableDelayedExpansion
set i=0


for %%F in (*.mp4 *.mkv *.mov *.avi) do (
    set /a i+=1

    for /f "delims=" %%D in ('
        cmd /c ""%FFPROBE%" -v error -show_entries format^=duration ^
        -of default^=noprint_wrappers^=1:nokey^=1 "%%F""
    ') do set "dur=%%D"

    set "dur=!dur:~0,-4!"
    echo !i!. %%~nxF  [!dur! sec]
    set "media[!i!]=%%~fF"
)

if %i%==0 (
    echo No videos found.
    pause
    endlocal
    goto menu
)

echo.
echo Enter numbers to merge (space-separated, order matters)
set /p picks=Selection:

del filelist.txt 2>nul

for %%N in (%picks%) do (
    set "p=!media[%%N]!"
    echo file '!p!'>> filelist.txt
)

"%FFMPEG%" -f concat -safe 0 -i filelist.txt -c copy merged_video.mp4

endlocal
echo.
echo Done!
echo Output: %PROJECT_DIR%\merged_video.mp4
pause
goto menu

:: =========================
:: MERGE AUDIOS ONLY
:: =========================
:merge_only_audios
cls
echo --- Merge AUDIOS ---
echo.

setlocal EnableDelayedExpansion
set i=0


for %%A in (*.mp3 *.wav *.aac *.m4a *.flac) do (
    set /a i+=1

    for /f "delims=" %%D in ('
        cmd /c ""%FFPROBE%" -v error -show_entries format^=duration ^
        -of default^=noprint_wrappers^=1:nokey^=1 "%%A""
    ') do set "dur=%%D"

    set "dur=!dur:~0,-4!"
    echo !i!. %%A  [!dur! sec]
    set "media[!i!]=%%A"
)

if %i%==0 (
    echo No audios found.
    pause
    endlocal
    goto menu
)

echo.
echo Enter numbers to merge (space-separated, order matters)
set /p picks=Selection:

del filelist.txt 2>nul

for %%N in (%picks%) do (
    set "p=!media[%%N]!"
    echo file '!p!'>> filelist.txt
)

"%FFMPEG%" -f concat -safe 0 -i filelist.txt -c:a libmp3lame -b:a 192k merged_audio.mp3

endlocal
echo.
echo Done!
echo Output: %PROJECT_DIR%\merged_audio.mp3
pause
goto menu

:: ================================
:: EXIT
:: ================================
:exit_tool
popd
exit




:: ================================
:: 2. CHANGE VIDEO SPEED
:: ================================
:change_speed
cls
echo --- Change Video Speed ---
echo.
echo Working folder:
echo %cd%
echo.
echo 0. Back
echo.

setlocal EnableDelayedExpansion

echo Available VIDEOS:
set i=0

for %%F in (*.mp4 *.mkv *.mov *.avi) do (
    set /a i+=1

    for /f "delims=" %%D in ('
        cmd /c ""%FFPROBE%" -v error -show_entries format^=duration ^
        -of default^=noprint_wrappers^=1:nokey^=1 "%%F""
    ') do set "dur=%%D"

    set "dur=!dur:~0,-4!"
    echo !i!. %%F  [!dur! sec]
    set "vid[!i!]=%%~fF"
)

if %i%==0 (
    echo No videos found.
    pause
    endlocal
    goto menu
)

echo.
echo Select video number
set /p pick=Selection:

if "%pick%"=="0" (
    endlocal
    goto menu
)

set "input=!vid[%pick%]!"

set /p speed=Speed multiplier (e.g. 0.5 slow, 1 normal, 2 fast):

for %%F in ("%input%") do (
    set "name=%%~nF"
    set "ext=%%~xF"
)

"%FFMPEG%" -i "%input%" ^
-filter_complex "[0:v]setpts=PTS/%speed%[v];[0:a]atempo=%speed%[a]" ^
-map "[v]" -map "[a]" "speed_%speed%_%name%%ext%"

echo.
echo Done! Output: %PROJECT_DIR%\speed_%speed%_%name%%ext%
pause
goto menu

:: ================================
:: 3. MERGE VIDEO AND AUDIO
:: ================================
:merge_video_audio
cls
echo --- Merge Video and Audio ---
echo.

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
        cmd /c ""%FFPROBE%" -v error -show_entries format^=duration ^
        -of default^=noprint_wrappers^=1:nokey^=1 "%%V""
    ') do set "dur=%%D"

    set "dur=!dur:~0,-4!"
    echo !v!. %%V  [!dur! sec]
    set "video[!v!]=%%~fV"
)

if %v%==0 (
    echo No video files found.
    pause
    endlocal
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
        cmd /c ""%FFPROBE%" -v error -show_entries format^=duration ^
        -of default^=noprint_wrappers^=1:nokey^=1 "%%A""
    ') do set "adur=%%D"

    set "adur=!adur:~0,-4!"
    echo !a!. %%A  [!adur! sec]
    set "audio[!a!]=%%~fA"
)

if %a%==0 (
    echo No audio files found.
    pause
    endlocal
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

"%FFMPEG%" -i "%videoFile%" -i "%audioFile%" -c:v copy -c:a aac -shortest "merged_%vname%%vext%"

endlocal

echo.
echo Done! Output: %PROJECT_DIR%\merged_%vname%%vext%
pause
goto menu


:: -------------------------
:: 4. REMOVE AUDIO
:: -------------------------

:remove_audio
cls
echo --- Remove Audio from Video ---
echo.
echo Working folder:
echo %cd%
echo.
echo 0. Back
echo.

setlocal EnableDelayedExpansion
set i=0

for %%F in (*.mp4 *.mkv *.mov *.avi) do (
    set /a i+=1

    for /f "delims=" %%D in ('
        cmd /c ""%FFPROBE%" -v error -show_entries format^=duration ^
        -of default^=noprint_wrappers^=1:nokey^=1 "%%F""
    ') do set "dur=%%D"

    set "dur=!dur:~0,-4!"
    echo !i!. %%F  [!dur! sec]
    set "vid[!i!]=%%~fF"
)

if %i%==0 (
    echo No videos found.
    pause
    endlocal
    goto menu
)

echo.
echo Select video number
set /p pick=Selection:

if "%pick%"=="0" (
    endlocal
    goto menu
)

set "input=!vid[%pick%]!"
if not defined input (
    echo Invalid selection.
    pause
    endlocal
    goto remove_audio
)

"%FFMPEG%" -i "!input!" -c:v copy -an no_audio.mp4

endlocal
echo.
echo Done! Output: %PROJECT_DIR%\no_audio.mp4
pause
goto menu


:: -------------------------
:: 5. EXTRACT AUDIO
:: -------------------------

:extract_audio
cls
echo --- Extract Audio from Video ---
echo.
echo Working folder:
echo %cd%
echo.
echo 0. Back
echo.

setlocal EnableDelayedExpansion
set i=0

for %%F in (*.mp4 *.mkv *.mov *.avi) do (
    set /a i+=1

    for /f "delims=" %%D in ('
        cmd /c ""%FFPROBE%" -v error -show_entries format^=duration ^
        -of default^=noprint_wrappers^=1:nokey^=1 "%%F""
    ') do set "dur=%%D"

    set "dur=!dur:~0,-4!"
    echo !i!. %%F  [!dur! sec]
    set "vid[!i!]=%%~fF"
)

if %i%==0 (
    echo No videos found.
    pause
    endlocal
    goto menu
)

echo.
echo Select video number
set /p pick=Selection:

if "%pick%"=="0" (
    endlocal
    goto menu
)

set "input=!vid[%pick%]!"
if not defined input (
    echo Invalid selection.
    pause
    endlocal
    goto extract_audio
)

"%FFMPEG%" -i "!input!" -vn -c:a copy extracted_audio.m4a

endlocal
echo.
echo Done! Output: %PROJECT_DIR%\extracted_audio.m4a
pause
goto menu


:: -------------------------
:: 6. TRIM VIDEO/AUDIO
:: -------------------------
:trim_media
cls
echo --- Trim Media ---
echo.
echo Working folder:
echo %cd%
echo.
echo 1. Trim VIDEO
echo 2. Trim AUDIO
echo 0. Back
echo.
set /p choice=Select option:

if "%choice%"=="1" goto trim_video_only
if "%choice%"=="2" goto trim_audio_only
if "%choice%"=="0" goto menu

echo Invalid choice.
pause
goto trim_media

:trim_video_only
cls
echo --- Trim VIDEO ---
echo.
echo Working folder:
echo %cd%
echo.
echo 0. Back
echo.

setlocal EnableDelayedExpansion
set i=0

for %%F in (*.mp4 *.mkv *.mov *.avi) do (
    set /a i+=1

    for /f "delims=" %%D in ('
        cmd /c ""%FFPROBE%" -v error -show_entries format^=duration ^
        -of default^=noprint_wrappers^=1:nokey^=1 "%%F""
    ') do set "dur=%%D"

    set "dur=!dur:~0,-4!"
    echo !i!. %%F  [!dur! sec]
    set "media[!i!]=%%~fF"
)

if %i%==0 (
    echo No videos found.
    pause
    endlocal
    goto menu
)

echo.
echo Select video number (0 to cancel)
set /p pick=Selection:

if "%pick%"=="0" (
    endlocal
    goto trim_media
)

set "input=!media[%pick%]!"
if not defined input (
    echo Invalid selection.
    pause
    endlocal
    goto trim_video_only
)

echo.
echo Enter START time (seconds or hh:mm:ss)
set /p start=Start:

echo Enter END time (seconds or hh:mm:ss)
set /p end=End:

if "%start%"=="" if "%end%"=="" (
    echo Invalid time range.
    pause
    endlocal
    goto trim_video_only
)

"%FFMPEG%" -ss %start% -to %end% -i "!input!" -c copy trimmed_video.mp4

endlocal
echo.
echo Done! Output: %PROJECT_DIR%\trimmed_video.mp4
pause
goto menu

:trim_audio_only
cls
echo --- Trim AUDIO ---
echo.
echo Working folder:
echo %cd%
echo.
echo 0. Back
echo.

setlocal EnableDelayedExpansion
set i=0

for %%A in (*.mp3 *.wav *.aac *.m4a *.flac) do (
    set /a i+=1

    for /f "delims=" %%D in ('
        cmd /c ""%FFPROBE%" -v error -show_entries format^=duration ^
        -of default^=noprint_wrappers^=1:nokey^=1 "%%A""
    ') do set "dur=%%D"

    set "dur=!dur:~0,-4!"
    echo !i!. %%A  [!dur! sec]
    set "media[!i!]=%%~fA"
)

if %i%==0 (
    echo No audios found.
    pause
    endlocal
    goto menu
)

echo.
echo Enter audio selection.
set /p pick=Selection:

if "%pick%"=="0" (
    endlocal
    goto trim_media
)

set "input=!media[%pick%]!"
if not defined input (
    echo Invalid selection.
    pause
    endlocal
    goto trim_audio_only
)

echo.
echo Enter START time (seconds or hh:mm:ss)
set /p start=Start:

echo Enter END time (seconds or hh:mm:ss)
set /p end=End:

if "%start%"=="" if "%end%"=="" (
    echo Invalid time range.
    pause
    endlocal
    goto trim_audio_only
)
echo.
echo Choose output format:
echo 1. MP3
echo 2. M4A
echo.
set /p fmt=Select format:

if "%fmt%"=="1" (
    set "outfile=trimmed_audio.mp3"
    "%FFMPEG%" -ss %start% -to %end% -i "!input!" -vn ^
    -c:a libmp3lame -b:a 192k "!outfile!"
    echo Done! Output: %PROJECT_DIR%\trimmed_audio.mp3
) else if "%fmt%"=="2" (
    set "outfile=trimmed_audio.m4a"
    "%FFMPEG%" -ss %start% -to %end% -i "!input!" -vn ^
    -c:a aac -b:a 192k "!outfile!"
    echo Done! Output: %PROJECT_DIR%\trimmed_audio.m4a
) else (
    echo Invalid format selection.
    pause
    endlocal
    goto trim_audio_only
)

endlocal
echo.
pause
goto menu

