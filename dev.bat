@echo off
start "melody-backend" cmd /k "cd /d D:\melody-snake\backend && ..\.venv\Scripts\python.exe -m melody_snake.main"
start "melody-frontend" cmd /k "cd /d D:\melody-snake\frontend && npm run dev"
echo [Melody Snake] dev mode: backend on :8000, frontend on :5173
