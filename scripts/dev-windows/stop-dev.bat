@echo off
setlocal
title AI Conversation Analyzer - Parar

echo.
echo  AI Conversation Analyzer - encerrando API, worker e frontend...
echo.

taskkill /FI "WINDOWTITLE eq AI Conversation Analyzer - Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AI Conversation Analyzer - Worker*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AI Conversation Analyzer - Frontend*" /T /F >nul 2>&1

powershell -NoProfile -Command ^
  "foreach ($port in 18000, 14200) { $pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if (-not $pids) { Write-Host ('Nenhum processo na porta ' + $port + '.'); continue }; foreach ($procId in $pids) { try { Stop-Process -Id $procId -Force -ErrorAction Stop; Write-Host ('Porta ' + $port + ': processo ' + $procId + ' encerrado.') } catch { Write-Host ('Falha ao encerrar ' + $procId + ': ' + $_.Exception.Message) } } }"

echo.
echo  Bancos Docker (aca-postgres / aca-redis) foram mantidos no ar.
echo  Concluido.
echo.
pause
