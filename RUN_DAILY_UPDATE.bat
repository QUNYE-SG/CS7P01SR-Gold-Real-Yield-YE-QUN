@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE="
set "PYTHON_OPTIONS="
if exist "%LocalAppData%\Programs\Python\Python314\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python314\python.exe"
if not defined PYTHON_EXE (
    where python >nul 2>&1 && set "PYTHON_EXE=python"
)
if not defined PYTHON_EXE (
    py -3 --version >nul 2>&1 && set "PYTHON_EXE=py" && set "PYTHON_OPTIONS=-3"
)
if not defined PYTHON_EXE goto no_python

"%PYTHON_EXE%" %PYTHON_OPTIONS% -B update_v2_data.py
if errorlevel 1 goto failed
echo.
echo V2 黄金和十年期实际利率已更新，结果包已重建。
if /i not "%~1"=="--scheduled" pause
endlocal
exit /b 0

:no_python
echo 找不到可用的 Python。请使用已安装 IBKR TWS API 的 Python 3.10 或更高版本。
if /i not "%~1"=="--scheduled" pause
endlocal
exit /b 1

:failed
echo 更新未完成。请查看 output\update_logs\v2_data_update.log，并确认 FRED 密钥和 TWS 登录状态。
if /i not "%~1"=="--scheduled" pause
endlocal
exit /b 1
