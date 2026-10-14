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

rem === If folder passed as argument (from context menu) ===
if not "%~1"=="" (
    set "PROJECT_DIR=%~1"
    echo Using project folder:
    echo %PROJECT_DIR%
    echo.
) else (
    echo Paste PROJECT FOLDER path
    echo Example: D:\Projects\Video_Edit
    echo.
    set /p "PROJECT_DIR=Project folder: "
)

rem === Validate folder ===
if not exist "%PROJECT_DIR%\" (
    echo.
    echo Folder not found!
    pause
    exit /b
)

rem === Enter project directory ===
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
echo 7. Cut video or audio
echo 0. Exit
echo.
set /p choice=Select option:

if "%choice%"=="1" goto merge_videos
if "%choice%"=="2" goto change_speed
if "%choice%"=="3" goto merge_video_audio
if "%choice%"=="4" goto remove_audio
if "%choice%"=="5" goto extract_audio
if "%choice%"=="6" goto trim_media
if "%choice%"=="7" goto cut_media
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
:: #4. REMOVE AUDIO
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
:: #5. EXTRACT AUDIO
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
:: #6. TRIM VIDEO/AUDIO
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
echo 3. Bulk Trim VIDEO
echo 4. Bulk Trim AUDIO
echo 0. Back
echo.
set /p choice=Select option:

if "%choice%"=="1" goto trim_video_only
if "%choice%"=="2" goto trim_audio_only
if "%choice%"=="3" goto bulk_trim_video
if "%choice%"=="4" goto bulk_trim_audio
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

"%FFMPEG%" -ss %start% -i "!input!" -to %end% ^
-c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k ^
 -copyts -avoid_negative_ts make_zero trimmed_video.mp4


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

:bulk_trim_video
cls
echo --- BULK TRIM VIDEO ---
echo.
echo Working folder:
echo %cd%
echo.

setlocal EnableDelayedExpansion
set i=0

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

echo.
echo Before proceeding, create "trim.txt" file with the following content (one segment per line):
echo START END
echo hh:mm:ss hh:mm:ss
echo or
echo hh:mm:ss.mmm hh:mm:ss.mmm
echo 00:02:02.250 00:03:02.770

echo.
echo Example:
echo 00:00:10 00:00:20
echo 00:01:05 00:01:30
echo 00:02:00 00:02:15
echo.

echo.
set /p pick=Select video number:

set "input=!video[%pick%]!"
if not defined input (
    echo Invalid selection.
    pause
    endlocal
    goto trim_media
)

set "segfile=%cd%\trim.txt"

if not exist "%segfile%" (
    echo trim.txt not found in current folder.
    echo Please create trim.txt first.
    pause
    endlocal
    goto trim_media
)

echo.
echo Processing segments...
echo.

set count=0

for /f "usebackq tokens=1,2 delims= " %%A in ("%segfile%") do (
    if not "%%A"=="" if not "%%B"=="" (
        set /a count+=1
        set "start=%%A"
        set "end=%%B"

        echo Creating clip !count! (!start! - !end!)

        "%FFMPEG%" -ss !start! -to !end! -i "!input!" ^
        -c:v libx264 -preset fast -crf 18 ^
        -c:a aac -b:a 192k ^
        -movflags +faststart ^
        "clip_!count!.mp4"
    )
)


echo.
echo Done! Created !count! clips.
pause
endlocal
goto menu


:bulk_trim_audio
cls
echo --- BULK TRIM AUDIO ---
echo.
echo Working folder:
echo %cd%
echo.

setlocal EnableDelayedExpansion
set i=0

echo Available AUDIOS:
set a=0
for %%A in (*.mp3 *.wav *.aac *.m4a *.flac) do (
    set /a a+=1
    for /f "delims=" %%D in ('
        cmd /c ""%FFPROBE%" -v error -show_entries format^=duration ^
        -of default^=noprint_wrappers^=1:nokey^=1 "%%A""
    ') do set "dur=%%D"

    set "dur=!dur:~0,-4!"
    echo !a!. %%A  [!dur! sec]
    set "audio[!a!]=%%~fA"
)

if %a%==0 (
    echo No audio files found.
    pause
    endlocal
    goto menu
)

echo.
echo Before proceeding, create "trim.txt" file with the following content (one segment per line):
echo START END
echo hh:mm:ss hh:mm:ss
echo or
echo hh:mm:ss.mmm hh:mm:ss.mmm
echo 00:02:02.250 00:03:02.770
echo.
echo Example:
echo 00:00:10 00:00:20
echo 00:01:05 00:01:30
echo 00:02:00 00:02:15
echo.

echo.
set /p pick=Select audio number:

set "input=!audio[%pick%]!"
if not defined input (
    echo Invalid selection.
    pause
    endlocal
    goto trim_media
)

set "segfile=%cd%\trim.txt"

if not exist "%segfile%" (
    echo trim.txt not found in current folder.
    echo Please create trim.txt first.
    pause
    endlocal
    goto trim_media
)

echo.
echo Choose output format:
echo 1. MP3
echo 2. M4A
echo.
set /p fmt=Select format:

echo.
echo Processing segments...
echo.

set count=0

for /f "usebackq tokens=1,2 delims= " %%A in ("%segfile%") do (
    if not "%%A"=="" if not "%%B"=="" (

        set /a count+=1
        set "start=%%A"
        set "end=%%B"

        echo Creating clip !count! (!start! - !end!)

        if "%fmt%"=="1" (
            "%FFMPEG%" -hide_banner -loglevel error -y ^
            -i "!input!" -ss !start! -to !end! ^
            -vn -c:a libmp3lame -b:a 192k ^
            "clip_!count!.mp3"
        ) else if "%fmt%"=="2" (
            "%FFMPEG%" -hide_banner -loglevel error -y ^
            -i "!input!" -ss !start! -to !end! ^
            -vn -c:a aac -b:a 192k ^
            "clip_!count!.m4a"
        ) else (
            echo Invalid format selection.
            pause
            endlocal
            goto trim_media
        )

    )
)


echo.
echo Done! Created !count! clips.
pause
endlocal
goto menu


:: -------------------------
:: #7. CUT VIDEO/AUDIO
:: -------------------------
:cut_media
cls
echo --- CUT MEDIA ---
echo.
echo 1. Bulk Cut VIDEO
echo 2. Bulk Cut AUDIO
echo 0. Back
echo.
set /p choice=Select option:

if "%choice%"=="1" goto bulk_cut_video
if "%choice%"=="2" goto bulk_cut_audio
if "%choice%"=="0" goto menu
goto cut_media

if not defined ms set ms=0
set /a total=(hh*3600)+(mm*60)+ss
set "result=%total%.%ms%"
exit /b

:time_to_seconds
set "t=%~1"
for /f "tokens=1-3 delims=:" %%a in ("%t%") do (
    set /a hh=%%a
    set /a mm=%%b
    set /a ss=%%c
)
set /a result=(hh*3600)+(mm*60)+ss
exit /b


:get_duration
for /f "delims=" %%A in ('ffprobe -v error -show_entries format^=duration -of default^=noprint_wrappers^=1:nokey^=1 "%~1"') do (
    set result=%%A
)
exit /b

:bulk_cut_video
cls
echo --- BULK CUT VIDEO ---
echo.
echo Working folder:
echo %cd%
echo.

setlocal EnableDelayedExpansion

set "segfile=%cd%\cut.txt"

if not exist "%segfile%" (
    echo cut.txt not found.
    pause
    endlocal
    goto cut_media
)

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

echo.
echo Before proceeding, create "cut.txt" file with the following content (one segment per line):
echo START END
echo hh:mm:ss hh:mm:ss

echo.
echo Example:
echo 00:00:10 00:00:20
echo 00:01:05 00:01:30
echo.

echo.
set /p pick=Select video number:

set "input=!video[%pick%]!"
if not defined input (
    echo Invalid selection.
    pause
    endlocal
    goto cut_media
)

echo Getting total duration...

for /f "delims=" %%D in ('
    cmd /c ""%FFPROBE%" -v error -show_entries format^=duration ^
    -of default^=noprint_wrappers^=1:nokey^=1 "!input!"" 
') do set "total_raw=%%D"

for /f "tokens=1 delims=." %%T in ("!total_raw!") do set "total=%%T"


if not defined total (
    echo Failed to read video duration.
    pause
    endlocal
    goto cut_media
)

set "segments="
set "prev=0"
set "idx=0"

echo.
echo Building filter segments...
echo.

for /f "usebackq tokens=1,2" %%A in ("%segfile%") do (


    if not "%%A"=="" if not "%%B"=="" (

        call :time_to_seconds %%A
        set "start=!result!"

        call :time_to_seconds %%B
        set "end=!result!"

        if defined start if defined end (

            if !start! GTR !prev! (

                set /a idx+=1

                set segments=!segments![0:v]trim=start=!prev!:end=!start!,setpts=PTS-STARTPTS[v!idx!];
                set segments=!segments![0:a]atrim=start=!prev!:end=!start!,asetpts=PTS-STARTPTS[a!idx!];
            )

            set "prev=!end!"
        )
    )
    echo DEBUG start=!start! end=!end!

)

rem === Add final segment only if needed ===
if not defined prev set "prev=0"

if !prev! LSS !total! (
    set /a idx+=1
    set segments=!segments![0:v]trim=start=!prev!:end=!total!,setpts=PTS-STARTPTS[v!idx!];
    set segments=!segments![0:a]atrim=start=!prev!:end=!total!,asetpts=PTS-STARTPTS[a!idx!];
)

if !idx! EQU 0 (
    echo No valid segments created.
    pause
    endlocal
    goto cut_media
)

set "concat="
for /l %%I in (1,1,!idx!) do (
    set concat=!concat![v%%I][a%%I]
)

set "filter_complex=!segments!!concat!concat=n=!idx!:v=1:a=1[outv][outa]"

echo.
echo Cutting video...
echo.

"%FFMPEG%" -y -i "!input!" ^
-filter_complex "!filter_complex!" ^
-map "[outv]" -map "[outa]" ^
-c:v libx264 -preset fast -crf 18 ^
-c:a aac -b:a 192k ^
cut_output.mp4

echo.
echo Done.
pause
endlocal
goto cut_media

:bulk_cut_audio
cls
echo --- BULK CUT AUDIO ---
echo.
echo Working folder:
echo %cd%
echo.

setlocal EnableDelayedExpansion

set "segfile=%cd%\cut.txt"

if not exist "%segfile%" (
    echo cut.txt not found.
    pause
    endlocal
    goto cut_media
)

echo Available AUDIOS:
set a=0
for %%A in (*.mp3 *.wav *.aac *.m4a *.flac) do (
    set /a a+=1
    for /f "delims=" %%D in ('
        cmd /c ""%FFPROBE%" -v error -show_entries format^=duration ^
        -of default^=noprint_wrappers^=1:nokey^=1 "%%A""
    ') do set "dur=%%D"

    set "dur=!dur:~0,-4!"
    echo !a!. %%A  [!dur! sec]
    set "audio[!a!]=%%~fA"
)

if %a%==0 (
    echo No audio files found.
    pause
    endlocal
    goto menu
)

echo.
echo Before proceeding, create "trim.txt" file with the following content (one segment per line):
echo START END
echo hh:mm:ss hh:mm:ss
echo.
echo Example:
echo 00:00:10 00:00:20
echo 00:01:05 00:01:30
echo.

echo.
set /p pick=Select audio number:

set "input=!audio[%pick%]!"
if not defined input (
    echo Invalid selection.
    pause
    endlocal
    goto bulk_cut_audio
)

echo Getting total duration...

for /f "delims=" %%D in ('
    cmd /c ""%FFPROBE%" -v error -show_entries format^=duration ^
    -of default^=noprint_wrappers^=1:nokey^=1 "!input!"" 
') do set "total_raw=%%D"

for /f "tokens=1 delims=." %%T in ("!total_raw!") do set "total=%%T"

set "segments="
set "prev=0"
set "idx=0"

for /f "usebackq tokens=1,2" %%A in ("%segfile%") do (

    if not "%%A"=="" if not "%%B"=="" (

        call :time_to_seconds %%A
        set "start=!result!"

        call :time_to_seconds %%B
        set "end=!result!"

        if defined start if defined end (

            rem Only create segment if valid range
            if !start! GTR !prev! (

                set /a idx+=1
                set segments=!segments![0:a]atrim=start=!prev!:end=!start!,asetpts=PTS-STARTPTS[a!idx!];
            )

            set "prev=!end!"
        )
    )
)

rem Ensure prev exists
if not defined prev set "prev=0"

rem Add final segment only if needed
if !prev! LSS !total! (
    set /a idx+=1
    set segments=!segments![0:a]atrim=start=!prev!:end=!total!,asetpts=PTS-STARTPTS[a!idx!];
)

set concat=
for /l %%I in (1,1,!idx!) do (
    set concat=!concat![a%%I]
)

set filter_complex=!segments!!concat!concat=n=!idx!:v=0:a=1[outa]

echo.
echo Cutting audio...
echo.

"%FFMPEG%" -y -i "!input!" ^
-filter_complex "!filter_complex!" ^
-map "[outa]" ^
-c:a libmp3lame -b:a 192k ^
cut_output.mp3

echo Done.
pause
endlocal
goto cut_media
