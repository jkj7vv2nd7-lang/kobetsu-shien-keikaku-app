@echo off
chcp 65001 >nul
echo サーバを停止します...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>nul
echo 停止しました（ポート8000・3000を使用中のプロセスを終了）。
pause
