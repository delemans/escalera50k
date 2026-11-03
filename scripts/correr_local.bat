@echo off
cd /d %~dp0\..
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -q -e .
if not exist .env (copy .env.example .env & echo Llena el archivo .env y vuelve a correr. & pause & exit /b)
python -m escalera.bot.app
pause
