@echo off
chcp 65001 > nul
echo ========================================
echo   CoinAI MAS - Start All Services
echo ========================================
echo.

set PYTHON=.\venv311\Scripts\python.exe

echo [1/5] MCP Time Server (port 8001)...
start "MCP Time" cmd /k "%PYTHON% mcp_servers/time_server.py"

echo [2/5] MCP Weather Server (port 8002)...
start "MCP Weather" cmd /k "%PYTHON% mcp_servers/weather_server.py"

echo [3/5] MCP Search Server (port 8003)...
start "MCP Search" cmd /k "%PYTHON% mcp_servers/search_server.py"

timeout /t 3 /nobreak > nul

echo [4/5] FastAPI Backend (port 8000)...
start "MAS Backend" cmd /k "%PYTHON% -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 2 /nobreak > nul

echo [5/5] Frontend (port 5173)...
start "MAS Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================
echo   All services started
echo ----------------------------------------
echo   MCP Time:    http://localhost:8001
echo   MCP Weather: http://localhost:8002
echo   MCP Search:  http://localhost:8003
echo   Backend API: http://localhost:8000
echo   Frontend UI: http://localhost:5173
echo   API Docs:    http://localhost:8000/docs
echo ========================================
echo.
echo To stop all services, close each window or run stop_all.bat
pause
