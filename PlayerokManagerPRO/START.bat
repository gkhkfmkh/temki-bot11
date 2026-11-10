@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Сначала создай окружение и установи зависимости. Инструкция: README_RU.md
  pause
  exit /b 1
)
".venv\Scripts\python.exe" bot.py
pause
