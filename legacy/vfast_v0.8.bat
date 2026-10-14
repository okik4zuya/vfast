@echo off
setlocal EnableDelayedExpansion
title Vfast Video Tool
color 0A

:: ================================
:: TOOL PATH SETUP
:: ================================
set "TOOL_DIR=%~dp0"
set "FFMPEG=%TOOL_DIR%bin\ffmpeg.exe"
set "FFPROBE=%TOOL_DIR%bin\ffprobe.exe"
set "PYTHON_EXE=%TOOL_DIR%venv\Scripts\python.exe"

:: ================================
:: SELECT PROJECT FOLDER
:: ================================
cls
echo ================================
echo        Vfast Video Tool
echo ================================
echo.

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

if not exist "%PROJECT_DIR%\" (
    echo.
    echo Folder not found!
    pause
    exit /b
)

set "PROJECT_DIR=%PROJECT_DIR:"=%"

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
echo 8. Screen recording
echo 9. Transcribe video
echo 0. Exit
echo.
set /p choice=Select option:

if "%choice%"=="1" goto merge_menu
if "%choice%"=="2" goto change_speed
if "%choice%"=="3" goto merge_video_audio
if "%choice%"=="4" goto remove_audio
if "%choice%"=="5" goto extract_audio
if "%choice%"=="6" goto trim_media
if "%choice%"=="7" goto cut_media
if "%choice%"=="8" goto screen_record
if "%choice%"=="9" goto transcribe_video
if "%choice%"=="0" goto exit_tool
goto menu

:: ================================
:: EXIT
:: ================================
:exit_tool
popd
exit

:: ================================
:: REUSABLE MEDIA LIST FUNCTION
:: ================================
:list_media
set "type=%~1"
set i=0

if /i "%type%"=="video" (
    set "ext=*.mp4 *.mkv *.mov *.avi"
    set "notfound=No videos found."
)

if /i "%type%"=="audio" (
    set "ext=*.mp3 *.wav *.aac *.m4a *.flac"
    set "notfound=No audios found."
)

for %%F in (%ext%) do (
    set /a i+=1

    for /f "delims=" %%D in ('
        cmd /c ""%FFPROBE%" -v error -show_entries format^=duration ^
        -of default^=noprint_wrappers^=1:nokey^=1 "%%F""
    ') do set "dur=%%D"

    set "dur=!dur:~0,-4!"
    echo !i!. %%~nxF  [!dur! sec]
    set "media[!i!]=%%~fF"
)

if !i! EQU 0 (
    echo !notfound!
    pause
    goto menu
)

set media_count=!i!
exit /b




:: ================================
:: MERGE MENU
:: ================================
:merge_menu
cls
echo --- Concatenate Media ---
echo.
echo Working folder:
echo %PROJECT_DIR%
echo.
echo 1. Merge VIDEOS
echo 2. Merge AUDIOS
echo 0. Back
echo.

set /p choice=Select option:

if "%choice%"=="1" goto merge_videos
if "%choice%"=="2" goto merge_audios
if "%choice%"=="0" goto menu

echo Invalid choice.
pause
goto merge_menu


:: ================================
:: MERGE VIDEOS
:: ================================
:merge_videos
cls
echo --- Merge VIDEOS ---
echo.

call :list_media video

echo.
echo Enter numbers to merge (space-separated, order matters)
set /p picks=Selection:

if "%picks%"=="" goto merge_videos

del filelist.txt 2>nul

set valid=0

for %%N in (%picks%) do (
    set "file="
    call set "file=%%media[%%N]%%"

    if defined file (
        echo file '!file!'>> filelist.txt
        set /a valid+=1
    )
)

if !valid! EQU 0 (
    echo No valid selections.
    pause
    goto merge_videos
)

rem "%FFMPEG%" -f concat -safe 0 -i filelist.txt -c copy merged_video.mp4
"%FFMPEG%" -f concat -safe 0 -i filelist.txt -c:v libx264 -c:a aac merged_video.mp4



echo.
echo Done!
echo Output: %PROJECT_DIR%\merged_video.mp4
pause
goto menu


:: ================================
:: MERGE AUDIOS
:: ================================
:merge_audios
cls
echo --- Merge AUDIOS ---
echo.

call :list_media audio

echo.
echo Enter numbers to merge (space-separated, order matters)
set /p picks=Selection:

if "%picks%"=="" goto merge_audios

del filelist.txt 2>nul

set valid=0

for %%N in (%picks%) do (
    set "file="
    call set "file=%%media[%%N]%%"

    if defined file (
        echo file '!file!'>> filelist.txt
        set /a valid+=1
    )
)

if !valid! EQU 0 (
    echo No valid selections.
    pause
    goto merge_audios
)

"%FFMPEG%" -f concat -safe 0 -i filelist.txt -c:a libmp3lame -b:a 192k merged_audio.mp3

echo.
echo Done!
echo Output: %PROJECT_DIR%\merged_audio.mp3
pause
goto menu



:: ================================
:: 2. CHANGE VIDEO SPEED
:: ================================
:change_speed
cls
echo --- Change Video Speed ---
echo.
echo Working folder:
echo %PROJECT_DIR%
echo.
echo 0. Back
echo.

echo Available VIDEOS:
call :list_media video

echo "!media[1]!"

echo.
echo Select video number
set /p pick=Selection:

if "%pick%"=="0" goto menu

set "input="
call set "input=%%media[%pick%]%%"

if not defined input (
    echo Invalid selection.
    pause
    goto change_speed
)



echo.
set /p speed=Speed multiplier (e.g. 0.5 slow, 1 normal, 2 fast):

if "%speed%"=="" (
    echo Invalid speed.
    pause
    goto change_speed
)

for %%F in ("%input%") do (
    set "name=%%~nF"
    set "ext=%%~xF"
)

"%FFMPEG%" -i "%input%" ^
-filter_complex "[0:v]setpts=PTS/%speed%[v];[0:a]atempo=%speed%[a]" ^
-map "[v]" -map "[a]" "speed_%speed%_%name%%ext%"

echo.
echo Done!
echo Output: %PROJECT_DIR%\speed_%speed%_%name%%ext%
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



:: ================================
:: #4. REMOVE AUDIO FROM VIDEO
:: ================================
:remove_audio
cls
echo --- Remove Audio from Video ---
echo.

setlocal EnableDelayedExpansion

:: -------------------------
:: LIST VIDEOS
:: -------------------------
call :list_media video

if "!media_count!"=="0" (
    echo No video files found.
    pause
    endlocal
    goto menu
)

echo.
echo 0. Back
echo.
set /p pick=Select video number:

if "!pick!"=="0" (
    endlocal
    goto menu
)

if "!media[%pick%]!"=="" (
    echo Invalid selection.
    pause
    endlocal
    goto remove_audio
)

set "input=!media[%pick%]!"

:: -------------------------
:: OUTPUT NAME
:: -------------------------
for %%F in ("!input!") do (
    set "vname=%%~nF"
    set "vext=%%~xF"
)

echo.
echo Removing audio...
"%FFMPEG%" -i "!input!" -c:v copy -an "noaudio_!vname!!vext!"

echo.
echo Done!
echo Output: %PROJECT_DIR%\noaudio_!vname!!vext!"
pause
endlocal
goto menu



:: ================================
:: #5. EXTRACT AUDIO FROM VIDEO
:: ================================
:extract_audio
cls
echo --- Extract Audio from Video ---
echo.

setlocal EnableDelayedExpansion

:: -------------------------
:: LIST VIDEOS
:: -------------------------
call :list_media video

if "!media_count!"=="0" (
    echo No video files found.
    pause
    endlocal
    goto menu
)

echo.
echo 0. Back
echo.
set /p pick=Select video number:

if "!pick!"=="0" (
    endlocal
    goto menu
)

if "!media[%pick%]!"=="" (
    echo Invalid selection.
    pause
    endlocal
    goto extract_audio
)

set "input=!media[%pick%]!"

:: -------------------------
:: OUTPUT NAME
:: -------------------------
for %%F in ("!input!") do (
    set "vname=%%~nF"
)

echo.
echo Choose output mode:
echo 1. Copy original audio stream (fast, no quality loss)
echo 2. Convert to MP3 (compatible format)
echo.
set /p mode=Select option (1 or 2):

if "!mode!"=="1" goto extract_copy
if "!mode!"=="2" goto extract_mp3

echo Invalid option.
pause
endlocal
goto menu


:extract_copy
"%FFMPEG%" -i "!input!" -vn -c:a copy "audio_!vname!.m4a"
goto extract_done


:extract_mp3
"%FFMPEG%" -i "!input!" -vn -c:a libmp3lame -b:a 192k "audio_!vname!.mp3"
goto extract_done


:extract_done
echo.
echo Done!
if "!mode!"=="1" echo Output: %PROJECT_DIR%\audio_!vname!.m4a
if "!mode!"=="2" echo Output: %PROJECT_DIR%\audio_!vname!.mp3
pause
endlocal
goto menu



:: ================================
:: 6. TRIM VIDEO / AUDIO
:: ================================
:trim_media
cls
echo --- Trim Media ---
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

:: ================================
:: #6.1 TRIM VIDEO
:: ================================

:trim_video_only
cls
echo --- Trim VIDEO ---
echo.

setlocal EnableDelayedExpansion

call :list_media video

if "!media_count!"=="0" (
    echo No video files found.
    pause
    endlocal
    goto menu
)

echo.
echo 0. Back
set /p pick=Select video number:

if "!pick!"=="0" (
    endlocal
    goto trim_media
)

if "!media[%pick%]!"=="" (
    echo Invalid selection.
    pause
    endlocal
    goto trim_video_only
)

set "input=!media[%pick%]!"

echo.
set /p start=Enter START time:
set /p end=Enter END time:

if "!start!"=="" if "!end!"=="" (
    echo Invalid time range.
    pause
    endlocal
    goto trim_video_only
)

for %%F in ("!input!") do set "vname=%%~nF"

echo.
echo Trimming...

"%FFMPEG%" -ss !start! -to !end! -i "!input!" ^
-c:v libx264 -preset fast -crf 18 ^
-c:a aac -b:a 192k ^
-movflags +faststart ^
"trimmed_!vname!.mp4"

echo.
echo Done!
echo Output: %PROJECT_DIR%\trimmed_!vname!.mp4
pause
endlocal
goto menu

:: ================================
:: #6.2 TRIM AUDIO
:: ================================
:trim_audio_only
cls
echo --- Trim AUDIO ---
echo.

setlocal EnableDelayedExpansion

call :list_media audio

if "!media_count!"=="0" (
    echo No audio files found.
    pause
    endlocal
    goto menu
)

echo.
echo 0. Back
set /p pick=Select audio number:

if "!pick!"=="0" (
    endlocal
    goto trim_media
)

if "!media[%pick%]!"=="" (
    echo Invalid selection.
    pause
    endlocal
    goto trim_audio_only
)

set "input=!media[%pick%]!"

echo.
set /p start=Enter START time:
set /p end=Enter END time:

echo.
echo 1. MP3
echo 2. M4A
set /p fmt=Select format:

for %%F in ("!input!") do set "aname=%%~nF"

if "!fmt!"=="1" (
    "%FFMPEG%" -ss !start! -to !end! -i "!input!" ^
    -vn -c:a libmp3lame -b:a 192k ^
    "trimmed_!aname!.mp3"
    set "outfile=trimmed_!aname!.mp3"
) else if "!fmt!"=="2" (
    "%FFMPEG%" -ss !start! -to !end! -i "!input!" ^
    -vn -c:a aac -b:a 192k ^
    "trimmed_!aname!.m4a"
    set "outfile=trimmed_!aname!.m4a"
) else (
    echo Invalid format.
    pause
    endlocal
    goto trim_audio_only
)

echo.
echo Done!
echo Output: %PROJECT_DIR%\!outfile!
pause
endlocal
goto menu


:: ================================
:: #6.3 BULK TRIM VIDEO
:: ================================
:bulk_trim_video
cls
echo --- BULK TRIM VIDEO ---
echo.

setlocal EnableDelayedExpansion

call :list_media video

if "!media_count!"=="0" (
    echo No video files found.
    pause
    endlocal
    goto menu
)

echo.
set /p pick=Select video number:

if "!media[%pick%]!"=="" (
    echo Invalid selection.
    pause
    endlocal
    goto trim_media
)

set "input=!media[%pick%]!"
set "segfile=%cd%\trim.txt"

if not exist "!segfile!" (
    echo trim.txt not found.
    pause
    endlocal
    goto trim_media
)

set count=0

for /f "usebackq tokens=1,2" %%A in ("!segfile!") do (
    if not "%%A"=="" if not "%%B"=="" (
        set /a count+=1
        "%FFMPEG%" -ss %%A -to %%B -i "!input!" ^
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

:: ================================
:: #6.4 BULK TRIM AUDIO
:: ================================
:bulk_trim_audio
cls
echo --- BULK TRIM AUDIO ---
echo.

setlocal EnableDelayedExpansion

call :list_media audio

if "!media_count!"=="0" (
    echo No audio files found.
    pause
    endlocal
    goto menu
)

echo.
set /p pick=Select audio number:

if "!media[%pick%]!"=="" (
    echo Invalid selection.
    pause
    endlocal
    goto trim_media
)

set "input=!media[%pick%]!"
set "segfile=%cd%\trim.txt"

if not exist "!segfile!" (
    echo trim.txt not found.
    pause
    endlocal
    goto trim_media
)

echo.
echo 1. MP3
echo 2. M4A
set /p fmt=Select format:

set count=0

for /f "usebackq tokens=1,2" %%A in ("!segfile!") do (
    if not "%%A"=="" if not "%%B"=="" (
        set /a count+=1

        if "!fmt!"=="1" (
            "%FFMPEG%" -ss %%A -to %%B -i "!input!" ^
            -vn -c:a libmp3lame -b:a 192k ^
            "clip_!count!.mp3"
        ) else if "!fmt!"=="2" (
            "%FFMPEG%" -ss %%A -to %%B -i "!input!" ^
            -vn -c:a aac -b:a 192k ^
            "clip_!count!.m4a"
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

:time_to_milliseconds
set "t=%~1"

rem Split HH:MM:SS.mmm
for /f "tokens=1-4 delims=:." %%a in ("%t%") do (
    set /a hh=%%a
    set /a mm=%%b
    set /a ss=%%c
    set ms=%%d
)

rem If milliseconds not provided → default 0
if not defined ms set ms=0

rem Normalize ms to 3 digits (pad if needed)
if 1%ms% LSS 1000 set ms=00%ms%
if 1%ms% LSS 100  set ms=0%ms%

rem Calculate total milliseconds
set /a result=(hh*3600000)+(mm*60000)+(ss*1000)+ms

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

rem Convert duration float → milliseconds
for /f "tokens=1,2 delims=." %%A in ("!total_raw!") do (
    set "sec_part=%%A"
    set "ms_part=%%B"
)

if not defined ms_part set "ms_part=0"

set "ms_part=!ms_part!000"
set "ms_part=!ms_part:~0,3!"

set /a total=(sec_part*1000)+ms_part

if not defined total (
    echo Failed to read video duration.
    pause
    endlocal
    goto cut_media
)

rem Check if video has audio
set "has_audio="

"%FFPROBE%" -v error -select_streams a -show_entries stream=index -of csv=p=0 "!input!" > temp_audio_check.txt

for /f %%A in (temp_audio_check.txt) do set "has_audio=1"

del temp_audio_check.txt

rem Building filter segments
set "segments="
set "prev=0"
set "idx=0"

echo.
echo Building filter segments...
echo.


for /f "usebackq tokens=1,2" %%A in ("%segfile%") do (

    if not "%%A"=="" if not "%%B"=="" (

        call :time_to_milliseconds %%A
        set "start=!result!"

        call :time_to_milliseconds %%B
        set "end=!result!"

        if defined start if defined end (

            if !start! GTR !prev! (

                rem Convert ms → decimal seconds for ffmpeg
                set /a s1=!prev!/1000
                set /a ms1=!prev!%%1000

                set /a s2=!start!/1000
                set /a ms2=!start!%%1000

                set "t1=!s1!.!ms1!"
                set "t2=!s2!.!ms2!"

                set /a idx+=1

                set segments=!segments![0:v]trim=start=!t1!:end=!t2!,setpts=PTS-STARTPTS[v!idx!];
                if defined has_audio (
                    set segments=!segments![0:a]atrim=start=!t1!:end=!t2!,asetpts=PTS-STARTPTS[a!idx!];
                )
            )

            set "prev=!end!"
        )
    )
)

rem === Add final segment ===
if not defined prev set "prev=0"

if !prev! LSS !total! (

    set /a s1=!prev!/1000
    set /a ms1=!prev!%%1000

    set /a s2=!total!/1000
    set /a ms2=!total!%%1000

    set "t1=!s1!.!ms1!"
    set "t2=!s2!.!ms2!"

    set /a idx+=1

    set segments=!segments![0:v]trim=start=!t1!:end=!t2!,setpts=PTS-STARTPTS[v!idx!];
    if defined has_audio (
        set segments=!segments![0:a]atrim=start=!t1!:end=!t2!,asetpts=PTS-STARTPTS[a!idx!];
    )
)

if !idx! EQU 0 (
    echo No valid segments created.
    pause
    endlocal
    goto cut_media
)

rem === Build concat section safely ===
set "concat="

if defined has_audio (

    for /l %%I in (1,1,!idx!) do (
        set concat=!concat![v%%I][a%%I]
    )

    set "filter_complex=!segments!!concat!concat=n=!idx!:v=1:a=1[outv][outa]"

) else (

    for /l %%I in (1,1,!idx!) do (
        set concat=!concat![v%%I]
    )

    set "filter_complex=!segments!!concat!concat=n=!idx!:v=1:a=0[outv]"
)

echo.
echo Cutting video...
echo "%has_audio%"
echo.

if defined has_audio (

    "%FFMPEG%" -y -i "!input!" ^
    -filter_complex "!filter_complex!" ^
    -map "[outv]" -map "[outa]" ^
    -c:v libx264 -preset fast -crf 18 ^
    -c:a aac -b:a 192k ^
    cut_output.mp4

) else (

    "%FFMPEG%" -y -i "!input!" ^
    -filter_complex "!filter_complex!" ^
    -map "[outv]" ^
    -c:v libx264 -preset fast -crf 18 ^
    cut_output.mp4

)

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
echo Before proceeding, create "cut.txt" file with the following content (one segment per line):
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

rem Convert total duration (float seconds) → milliseconds
for /f "tokens=1,2 delims=." %%A in ("!total_raw!") do (
    set "sec_part=%%A"
    set "ms_part=%%B"
)

if not defined ms_part set "ms_part=0"

rem Normalize ms to 3 digits
set "ms_part=!ms_part!000"
set "ms_part=!ms_part:~0,3!"

set /a total=(sec_part*1000)+ms_part


set "segments="
set "prev=0"
set "idx=0"

for /f "usebackq tokens=1,2" %%A in ("%segfile%") do (

    if not "%%A"=="" if not "%%B"=="" (

        call :time_to_milliseconds %%A
        set "start=!result!"

        call :time_to_milliseconds %%B
        set "end=!result!"

        if defined start if defined end (

            rem Only create segment if valid
            if !start! GTR !prev! (

                rem Convert prev and start back to decimal seconds
                set /a s1=!prev!/1000
                set /a ms1=!prev!%%1000

                set /a s2=!start!/1000
                set /a ms2=!start!%%1000

                set "t1=!s1!.!ms1!"
                set "t2=!s2!.!ms2!"

                set /a idx+=1
                set segments=!segments![0:a]atrim=start=!t1!:end=!t2!,asetpts=PTS-STARTPTS[a!idx!];
            )

            set "prev=!end!"
        )
    )
)

rem Add final segment if needed
if !prev! LSS !total! (

    set /a s1=!prev!/1000
    set /a ms1=!prev!%%1000

    set /a s2=!total!/1000
    set /a ms2=!total!%%1000

    set "t1=!s1!.!ms1!"
    set "t2=!s2!.!ms2!"

    set /a idx+=1
    set segments=!segments![0:a]atrim=start=!t1!:end=!t2!,asetpts=PTS-STARTPTS[a!idx!];
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




:: =============================
::  #8 SCREEN RECORDING
:: =============================
:screen_record
cls
echo ===============================
echo        SCREEN RECORDING
echo ===============================
echo.

setlocal EnableDelayedExpansion

rem =========================================
rem STEP 1 — LIST AUDIO DEVICES
rem =========================================

echo Detecting audio devices...
echo.

ffmpeg -list_devices true -f dshow -i dummy 2> device_list.txt

echo Available Microphone Devices:
echo.

set /a mic_index=0

for /f "tokens=1,* delims=]" %%A in ('findstr /i "Microphone" device_list.txt') do (
    set /a mic_index+=1
    set "mic!mic_index!=%%B"
    echo !mic_index!. %%B
)


if !mic_index! EQU 0 (
    echo.
    echo No microphone devices found.
    pause
    del device_list.txt
    endlocal
    goto main_menu
)
echo.
echo =======================
echo.
echo Type selected microphone based on the list.
echo Example: Microphone (Web Camera)
echo.
set /p selected_mic=Device name: 


if "%selected_mic%"=="" (
    echo No device entered.
    pause
    exit /b
)

@REM echo.
@REM set /p mic_choice=Select microphone number:

@REM if not defined mic%mic_choice% (
@REM     echo Invalid selection.
@REM     pause
@REM     del device_list.txt
@REM     endlocal
@REM     goto main_menu
@REM )

@REM set "selected_mic=!mic%mic_choice%!"

echo.
echo Selected Microphone:
echo !selected_mic!
echo.

rem =========================================
rem STEP 2 — ASK OUTPUT NAME
rem =========================================

echo Enter output file name (without extension):
set /p outfile=

if "%outfile%"=="" set "outfile=screen_record"

echo.
echo Recording will start in 3 seconds...
timeout /t 3 >nul

echo.
echo Press Q to stop recording.
echo.

rem =========================================
rem STEP 3 — RECORD SCREEN + MIC
rem =========================================

ffmpeg ^
-f gdigrab -framerate 30 -i desktop ^
-f dshow -i audio="%selected_mic%" ^
-map 0:v -map 1:a ^
-c:v libx264 -preset veryfast -crf 23 ^
-c:a aac -b:a 192k ^
-pix_fmt yuv420p ^
"%outfile%.mp4"

echo.
echo Recording saved as %outfile%.mp4
pause
endlocal
goto main_menu


:: =============================
::  #9 TRANSCRIBE VIDEO
:: =============================
:transcribe_video
cls
echo ================================
echo        TRANSCRIBE VIDEO
echo ================================
echo.
echo 1. Transcribe from YouTube
echo 2. Transcribe from video file
echo 0. Back
echo.
set /p choice=Select option:

if "%choice%"=="1" goto transcribe_youtube
if "%choice%"=="2" goto transcribe_file
if "%choice%"=="0" goto menu

echo Invalid choice.
pause
goto transcribe_video

:transcribe_youtube
cls
echo --- Transcribe from YouTube ---
echo.
echo Enter YouTube URL or Video ID:
set /p yt_input=

if "%yt_input%"=="" (
    echo No input provided.
    pause
    goto transcribe_video
)

echo.
echo Transcribing...
"%PYTHON_EXE%" "%TOOL_DIR%modules\transcribe.py" "%TOOL_DIR%" "%PROJECT_DIR%" ""%yt_input%""

echo.
echo Done!
pause
goto menu

:transcribe_file
cls
echo --- Transcribe from Video File ---
echo.

setlocal EnableDelayedExpansion

call :list_media video

if "!media_count!"=="0" (
    echo No video files found.
    pause
    endlocal
    goto menu
)

echo.
echo 0. Back
echo.
set /p pick=Select video number:

if "!pick!"=="0" (
    endlocal
    goto transcribe_video
)

if "!media[%pick%]!"=="" (
    echo Invalid selection.
    pause
    endlocal
    goto transcribe_file
)

set "input=!media[%pick%]!"
echo "!input!"

echo.
echo Transcribing...
"%PYTHON_EXE%" "%TOOL_DIR%modules\transcribe_yt.py" "!input!"

echo.
echo Done!
pause
endlocal
goto menu
