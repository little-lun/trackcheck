@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title PVZ trackcheck - 出怪沙盘

rem 强制 UTF-8，跟下面的 chcp 65001 对齐（不依赖外部环境变量）
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

rem 优先用托管 Python；找不到就退回系统 python
set "PY=C://Users//Welun_Laptop//.workbuddy//binaries//python//versions//3.13.12//python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" -c "import sys" >nul 2>&1
if errorlevel 1 goto nopython

echo.
echo  正在启动出怪沙盘…… 浏览器会自动打开 http://127.0.0.1:8765/
echo  关掉这个窗口 = 结束服务。
echo.
"%PY%" -m tools.trackcheck.app --port 8765
if errorlevel 1 pause
goto :eof

:nopython
echo.
echo  [错误] 没找到可用的 Python。
echo  请右键这个文件 - 编辑，把 PY= 后面改成你的 python.exe 全路径。
echo.
pause
