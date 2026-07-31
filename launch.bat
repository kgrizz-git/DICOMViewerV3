@echo off
setlocal EnableDelayedExpansion
set "ROOT=%~dp0"
rem Resolve VENV: use first existing env among common names; default target for create is venv.
set "VENV="
if exist "%ROOT%venv\Scripts\python.exe" set "VENV=%ROOT%venv"
if not defined VENV if exist "%ROOT%.venv\Scripts\python.exe" set "VENV=%ROOT%.venv"
if not defined VENV if exist "%ROOT%env\Scripts\python.exe" set "VENV=%ROOT%env"
if not defined VENV if exist "%ROOT%virtualenv\Scripts\python.exe" set "VENV=%ROOT%virtualenv"
if not defined VENV set "VENV=%ROOT%venv"
set "VENV_PY=%VENV%\Scripts\python.exe"

:MENU
cls
echo ===============================
echo   DICOM Viewer V3 Launcher
echo ===============================
echo.

if exist "%VENV_PY%" (
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
    echo What is a venv? A separate folder of Python packages used only by this app.
    echo It avoids mixing versions with other Python programs on your PC and makes
    echo updates or cleanup simpler. Using one is recommended, not required.
    echo You can run with system Python instead ^(option 2 below^) if you prefer.
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
if not exist "%VENV_PY%" (
    echo ERROR: Virtual environment was created but python.exe is missing:
    echo   %VENV_PY%
    pause
    goto :END
)
call :INSTALL_REQUIREMENTS
if errorlevel 1 goto :END
goto :RUN_ACTIVATED

:REINSTALL
if not exist "%VENV_PY%" (
    echo ERROR: Virtual environment python not found:
    echo   %VENV_PY%
    pause
    goto :END
)
call :INSTALL_REQUIREMENTS
if errorlevel 1 goto :END
goto :RUN_ACTIVATED

:INSTALL_REQUIREMENTS
echo.
echo Installing requirements into:
echo   %VENV_PY%
echo This can take several minutes. Do not close this window.
rem Always use the venv interpreter explicitly. Relying on "activate" + bare
rem "pip"/"python" is fragile on Windows when pyenv or multiple Pythons are on PATH.
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip inside the virtual environment.
    pause
    exit /b 1
)
"%VENV_PY%" -m pip install -r "%ROOT%requirements.txt"
if errorlevel 1 (
    echo ERROR: Failed to install requirements into the virtual environment.
    echo The venv folder may exist but be incomplete. Choose option 2
    echo ^(Reinstall / update requirements^) after fixing the error, or delete
    echo the venv and create it again.
    pause
    exit /b 1
)
rem Canary imports: enough of the app stack that a half-finished pip install still fails.
"%VENV_PY%" -c "import pydicom, PySide6, numpy, PIL"
if errorlevel 1 (
    echo ERROR: Requirements appeared to install, but required packages are still missing.
    echo Try option 2 ^(Reinstall / update requirements^) or delete and recreate the venv.
    pause
    exit /b 1
)
echo Requirements installed successfully.
exit /b 0

:RUN
if not exist "%VENV_PY%" (
    echo ERROR: Virtual environment python not found:
    echo   %VENV_PY%
    pause
    goto :END
)
rem Recover from a half-created venv (folder exists, packages never installed).
"%VENV_PY%" -c "import pydicom, PySide6, numpy, PIL" 1>nul 2>nul
if errorlevel 1 (
    echo.
    echo Virtual environment is incomplete ^(required packages missing^).
    echo Installing requirements before starting...
    call :INSTALL_REQUIREMENTS
    if errorlevel 1 goto :END
)
goto :RUN_ACTIVATED

:RUN_ACTIVATED
echo.
echo Starting DICOM Viewer...
"%VENV_PY%" "%ROOT%run.py"
if errorlevel 1 (
    echo.
    echo DICOM Viewer exited with an error.
    pause
)
goto :END

:RUN_SYS
echo.
echo Starting DICOM Viewer (system Python)...
python "%ROOT%run.py"
if errorlevel 1 (
    echo.
    echo DICOM Viewer exited with an error.
    echo If you see ModuleNotFoundError, install requirements for this Python:
    echo   python -m pip install -r "%ROOT%requirements.txt"
    pause
)
goto :END

:DELETE
echo.
set /p "CONFIRM=Delete the virtual environment? This cannot be undone. (y/n): "
if /i "!CONFIRM!"=="y" (
    echo Deleting virtual environment...
    rmdir /s /q "%VENV%"
    echo Done.
    rem Recreate default target path after delete (may have been .venv etc.).
    set "VENV=%ROOT%venv"
    set "VENV_PY=%VENV%\Scripts\python.exe"
    pause
)
goto :MENU

:END
endlocal
