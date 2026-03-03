@echo off
echo ============================================================
echo   INTELLI-CREDIT — STARTING ALL SERVICES
echo ============================================================
echo.

echo [1/3] Starting BACKEND API (port 8000)...
start "Backend API" cmd /k "cd /d %~dp0backend && python main.py"

echo [2/3] Starting RESEARCH AGENT (port 8001)...
start "Research Agent" cmd /k "cd /d %~dp0research_agent && python -m uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload"

timeout /t 3 /nobreak >nul

echo [3/3] Starting FRONTEND (port 3000)...
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ============================================================
echo   All services starting. Open: http://localhost:3000
echo   Backend API docs:  http://localhost:8000/docs
echo   Research Agent:    http://localhost:8001/docs
echo ============================================================
pause
