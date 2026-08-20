@echo off
setlocal EnableDelayedExpansion
title AI Conversation Analyzer - Iniciar

set "ROOT=E:\Projetos\AI-Conversation-Analyzer"
set "FRONTEND_PORT=14200"
set "BACKEND_PORT=18000"
set "UV_DIR=%USERPROFILE%\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe"

echo.
echo  AI Conversation Analyzer - iniciando ambiente local...
echo.

cd /d "%ROOT%"
if errorlevel 1 (
  echo ERRO: pasta do projeto nao encontrada: %ROOT%
  pause
  exit /b 1
)

if exist "%UV_DIR%\uv.exe" set "PATH=%UV_DIR%;%PATH%"

if not exist "%ROOT%\.env" (
  echo Copiando .env.example para .env...
  copy /Y "%ROOT%\.env.example" "%ROOT%\.env" >nul
)

echo [1/5] Subindo PostgreSQL e Redis (Docker)...
cd /d "%ROOT%\docker"
docker compose up -d
if errorlevel 1 (
  echo.
  echo  Nao foi possivel preparar os bancos. Abra o Docker Desktop e tente novamente.
  echo.
  pause
  exit /b 1
)

echo Aguardando PostgreSQL ficar pronto...
set /a WAIT=0
:wait_pg
docker exec aca-postgres pg_isready -U aca -d aca >nul 2>&1
if %errorlevel%==0 goto pg_ok
set /a WAIT+=1
if %WAIT% GTR 30 (
  echo ERRO: PostgreSQL nao ficou pronto a tempo.
  pause
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait_pg
:pg_ok

echo [2/5] Aplicando migracoes...
cd /d "%ROOT%\backend"
if not exist ".venv\Scripts\alembic.exe" (
  echo Ambiente Python ausente. Executando uv sync...
  uv sync
  if errorlevel 1 (
    echo ERRO: uv sync falhou.
    pause
    exit /b 1
  )
)
.venv\Scripts\alembic.exe upgrade head
if errorlevel 1 (
  echo ERRO ao aplicar migracoes.
  pause
  exit /b 1
)

echo [3/5] Abrindo backend (porta %BACKEND_PORT%) e worker...
start "AI Conversation Analyzer - Backend" cmd /k "cd /d "%ROOT%\backend" && .venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port %BACKEND_PORT%"
start "AI Conversation Analyzer - Worker" cmd /k "cd /d "%ROOT%\backend" && .venv\Scripts\arq.exe app.workers.settings.WorkerSettings"

timeout /t 3 /nobreak >nul

echo [4/5] Abrindo frontend (porta %FRONTEND_PORT%)...
if not exist "%ROOT%\frontend\node_modules\" (
  echo node_modules ausente. Executando npm install...
  start "AI Conversation Analyzer - Frontend" cmd /k "cd /d "%ROOT%\frontend" && npm install && npm start"
) else (
  start "AI Conversation Analyzer - Frontend" cmd /k "cd /d "%ROOT%\frontend" && npm start"
)

echo [5/5] Aguardando servicos e abrindo navegador...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\dev-windows\open-dev-browser.ps1" -ProjectRoot "%ROOT%" -FrontendPort %FRONTEND_PORT% -BackendPort %BACKEND_PORT%

echo.
echo  Pronto!
echo  App:  http://localhost:%FRONTEND_PORT%
echo  API:  http://127.0.0.1:%BACKEND_PORT%/docs
echo.
echo  Feche as janelas Backend/Worker/Frontend para encerrar cada servico.
echo  Ou use "AI Conversation Analyzer - Parar.bat".
echo.
timeout /t 4 >nul
