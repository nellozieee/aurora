@echo off
REM Start Aurora in native dev mode: Postgres+Redis via Docker, backend
REM (uvicorn) and frontend (Vite) each in their own window.

setlocal
set REPO_ROOT=%~dp0

if not exist "%REPO_ROOT%.env" (
    echo No .env found -- copying .env.example. Edit it before continuing.
    copy "%REPO_ROOT%.env.example" "%REPO_ROOT%.env" >nul
)

if not exist "%REPO_ROOT%backend\.venv" (
    echo backend\.venv not found. Run this first:
    echo   cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt
    exit /b 1
)

if not exist "%REPO_ROOT%frontend\node_modules" (
    echo frontend\node_modules not found. Run this first:
    echo   cd frontend ^&^& npm install
    exit /b 1
)

where docker >nul 2>nul
if %ERRORLEVEL%==0 (
    echo Starting Postgres + Redis via Docker Compose...
    pushd "%REPO_ROOT%"
    docker compose up -d postgres redis
    popd
) else (
    echo Docker not found -- make sure Postgres ^(with pgvector^) and Redis are running natively ^(see README.md^).
)

echo Starting backend (uvicorn) on http://localhost:8000 ...
start "Aurora Backend" cmd /k "cd /d "%REPO_ROOT%backend" && .venv\Scripts\activate && uvicorn app.main:app --reload"

echo Starting frontend (Vite) on http://localhost:5173 ...
start "Aurora Frontend" cmd /k "cd /d "%REPO_ROOT%frontend" && npm run dev"

echo.
echo Aurora is starting in two new windows. Close either window to stop that service.
endlocal
