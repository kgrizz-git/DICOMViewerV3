@echo off
setlocal EnableDelayedExpansion
set "ROOT=%~dp0"
set "VENV=%ROOT%venv"

:MENU
cls
echo ===============================
echo   DICOM Viewer V3 Launcher
echo ===============================
echo.

if exist "%VENV%\Scripts\activate.bat" (
    echo Virtual environment: FOUND
    echo.
    echo   1  Run DICOM Viewer
    echo   2  Reinstall / update requirements
    echo   3  Delete virtual environment
    echo   4  Exit
    echo.
    set /p "CHOICE=Choose [1-4]: "
    if "!CHOICE!"=="1" goto :RUN
    if "!CHOICE!"=="2" goto :REINSTALL
    if "!CHOICE!"=="3" goto :DELETE
    if "!CHOICE!"=="4" goto :END
    goto :MENU
) else (
    echo Virtual environment: NOT FOUND
    echo.
    echo   1  Create venv, install requirements, then run
    echo   2  Run using system Python ^(no venv^)
    echo   3  Exit
    echo.
    set /p "CHOICE=Choose [1-3]: "
    if "!CHOICE!"=="1" goto :SETUP
    if "!CHOICE!"=="2" goto :RUN_SYS
    if "!CHOICE!"=="3" goto :END
    goto :MENU
)

:SETUP
echo.
echo Creating virtual environment...
python -m venv "%VENV%"
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    echo Make sure Python is installed and on your PATH.
    pause
    goto :END
)
call "%VENV%\Scripts\activate.bat"
echo Installing requirements...
pip install -r "%ROOT%requirements.txt"
if errorlevel 1 (
    echo ERROR: Failed to install requirements.
    pause
    goto :END
)
goto :RUN_ACTIVATED

:REINSTALL
call "%VENV%\Scripts\activate.bat"
echo Updating requirements...
pip install -r "%ROOT%requirements.txt"
if errorlevel 1 (
    echo ERROR: Failed to install requirements.
    pause
    goto :END
)
goto :RUN_ACTIVATED

:RUN
call "%VENV%\Scripts\activate.bat"
:RUN_ACTIVATED
echo.
echo Starting DICOM Viewer...
python "%ROOT%run.py"
goto :END

:RUN_SYS
echo.
echo Starting DICOM Viewer (system Python)...
python "%ROOT%run.py"
goto :END

:DELETE
echo.
set /p "CONFIRM=Delete the virtual environment? This cannot be undone. (y/n): "
if /i "!CONFIRM!"=="y" (
    echo Deleting virtual environment...
    rmdir /s /q "%VENV%"
    echo Done.
    pause
)
goto :MENU

:END
endlocal
