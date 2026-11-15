@echo off
title Make Clips
cd /d "%~dp0"

rem Find Python. "py" comes with the python.org installer, "python" with the Store one.
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)

if not defined PY (
    echo Python is not installed yet. Installing it now, one time only...
    echo If Windows asks for permission, click Yes.
    echo.
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    echo.
    echo ------------------------------------------------------------
    echo  Python setup finished. Close this window and double-click
    echo  "Make Clips" again.
    echo.
    echo  If you saw an error above instead, install Python yourself:
    echo  open the Microsoft Store, search for Python, click Get.
    echo ------------------------------------------------------------
    pause
    exit /b
)

%PY% "%~dp0make_clips.py"
echo.
pause
