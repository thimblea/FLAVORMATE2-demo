@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "Flavormate服务" /min "D:\Program Files\Python311\python.exe" app.py --open
