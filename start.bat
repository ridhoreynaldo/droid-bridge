@echo off
cd /d %~dp0
if not exist .env (
  copy .env.example .env >nul
  echo .env dibuat dari .env.example - isi BRIDGE_TOKEN dulu kalau mau di-expose ke internet
)
echo Buka http://localhost:3000 di Chrome
python bridge.py
pause
