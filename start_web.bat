@echo off
chcp 65001 >nul
title TalkToYou - AI语音第二人代发服务
echo ====================================================
echo        TalkToYou - AI 语音第二人代发系统
echo ====================================================
echo.
echo 正在启动 Web 服务...
echo 打开浏览器访问: http://127.0.0.1:8086
echo.
python server.py
if errorlevel 1 (
    echo 正在使用备用 Python 环境启动...
    D:\AI\ComfyUI-aki-v3\python\python.exe server.py
)
pause
