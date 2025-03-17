@echo off
cd /d "%~dp0"
setlocal enabledelayedexpansion

rem Remove any old temp file if it exists
del temp.txt 2>nul

REM for /r %%f in (*) do (
    REM echo Found file: %%f
REM )
REM pause


rem Recursively iterate over all files from this script’s directory
for /r %%f in (*) do (
    set "FullName=%%f"

    rem Skip any path containing "venv" or "__pycache__"
    if /i "!FullName:venv=!"=="!FullName!" if /i "!FullName:__pycache__=!"=="!FullName!" if /i "!FullName:.git=!"=="!FullName!" if /i "!FullName:.vscode=!"=="!FullName!" if /i "!FullName:.env=!"=="!FullName!" if /i "!FullName:.git=!"=="!FullName!" if /i "!FullName:.bat=!"=="!FullName!" (
        rem Write a marker line showing which file we're about to include
		echo !FullName!
		
        echo ### !FullName! >> temp.txt
		REM echo Found file: %%f
        REM rem Append the file contents
        type "%%f" >> temp.txt
        echo. >> temp.txt
        echo. >> temp.txt
    )
)

rem Put the entire collected text into the clipboard
type temp.txt | clip

rem Clean up
REM del temp.txt
endlocal
