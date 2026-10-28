@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD=python"
set "PYTHON_MODE=system"
set "CODEX_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
python --version >nul 2>&1
if errorlevel 1 (
    py -3 --version >nul 2>&1
    if errorlevel 1 (
        if not exist "%CODEX_PYTHON%" goto no_python
        set "PYTHON_MODE=codex"
    ) else (
        set "PYTHON_CMD=py -3"
    )
)

if /i "%PYTHON_MODE%"=="codex" (
    "%CODEX_PYTHON%" build_top2_package.py
) else (
    %PYTHON_CMD% build_top2_package.py
)
if errorlevel 1 goto failed

start "" "%~dp0output\top2_pine5_20261004\index.html"
echo.
echo V2 historical upward-probability results (70%% and above) generated. Press any key to close.
pause >nul
endlocal
exit /b 0

:no_python
echo Python is not available. Install Python 3.10 or newer, then try again.
pause
endlocal
exit /b 1

:failed
echo Failed to generate the V2 probability results. Check the Python output above and the recalculated input CSV.
pause
endlocal
exit /b 1
