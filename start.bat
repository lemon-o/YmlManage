@echo off
chcp 65001 >nul
title YmlManage - 节点母本维护工具

echo ==================================================
echo   ⚡ YmlManage 启动中...
echo ==================================================
python run.py
if %errorlevel% neq 0 (
    echo.
    echo 启动发生错误，请查看上方提示信息。
    pause
)
