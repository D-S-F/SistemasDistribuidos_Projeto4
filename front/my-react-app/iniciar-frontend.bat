@echo off
echo Iniciando servidor de desenvolvimento do frontend...
cd /d %~dp0
call npm run dev
pause

