@echo off
echo [Melody Snake] building frontend...
cd /d "D:\melody-snake\frontend"
call npm run build
if errorlevel 1 (
  echo build failed
  exit /b 1
)
echo [Melody Snake] starting server at http://127.0.0.1:8000 ...
cd /d "D:\melody-snake\backend"
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000"
..\.venv\Scripts\python.exe -m melody_snake.main
