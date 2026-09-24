@echo off
setlocal
rem Installs textmidi and its Python packages (mido, plus pytest for the tests).
rem Double-click this file, or run it from a Command Prompt.

cd /d "%~dp0"

rem Find Python: prefer the py launcher, fall back to python on PATH.
set "PY="
py --version >nul 2>&1 && set "PY=py"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo Python was not found.
    echo Install Python 3.10 or newer from https://www.python.org/downloads/
    echo then run this file again.
    goto :fail
)

%PY% -c "import sys; sys.exit(sys.version_info < (3, 10))"
if errorlevel 1 (
    echo textmidi needs Python 3.10 or newer. This computer has:
    %PY% --version
    echo Install a newer Python from https://www.python.org/downloads/
    echo then run this file again.
    goto :fail
)

echo Using:
%PY% --version
echo.

rem Old pip versions can't do the editable install below, so update it first.
echo Updating pip...
%PY% -m pip install --upgrade pip

echo.
echo Installing textmidi, mido and pytest...
%PY% -m pip install -e ".[dev]"
if errorlevel 1 (
    echo.
    echo pip could not install the packages. Check your internet connection
    echo and the messages above, then run this file again.
    goto :fail
)

rem Check from outside this folder, so it proves the install worked.
echo.
echo Checking the install...
cd /d "%USERPROFILE%"
%PY% -m textmidi --help >nul
if errorlevel 1 (
    echo textmidi was installed but would not start. See the messages above.
    goto :fail
)

echo.
echo ============================================================
echo  textmidi is ready.
echo.
echo  To turn a score into MIDI, double-click textmidi-gui.pyw
echo  in this folder, or open a Command Prompt and run:
echo      %PY% -m textmidi song.txt
echo.
echo  You can ignore any pip warning about a Scripts folder not
echo  being on PATH.
echo ============================================================
echo.
pause
exit /b 0

:fail
echo.
pause
exit /b 1
