@echo off
chcp 65001 >nul
cd /d "%~dp0"
set LOG=%~dp0startup.log
echo [%date% %time%] start >> "%LOG%"
echo ================================================
echo  個別支援・指導計画アプリ  起動中
echo  終わるときは開いた黒い画面を2つとも閉じてください
echo  （または stop.bat をダブルクリック）
echo ================================================
where python >nul 2>nul
if errorlevel 1 (echo [エラー] pythonが見つかりません & echo python missing >> "%LOG%" & pause & exit /b 1)
where node >nul 2>nul
if errorlevel 1 (echo [エラー] Node.jsが見つかりません & echo node missing >> "%LOG%" & pause & exit /b 1)
if not exist "frontend\node_modules" (
  echo 初回のためセットアップを実行します...
  call "%~dp0setup.bat"
)
echo 様式データを準備中...
python backend\seed_niigata.py >> "%LOG%" 2>&1
echo APIサーバを起動します...
start "支援計画API（閉じると終了）" cmd /k "cd /d ""%~dp0"" && python -m uvicorn app.main:app --app-dir backend --port 8000"
echo Web画面を起動します...
start "支援計画Web（閉じると終了）" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"
echo APIの起動待ち（最大60秒）...
for /l %%i in (1,1,12) do (
  timeout /t 5 /nobreak >nul
  powershell -NoProfile -Command "try { Invoke-WebRequest -Uri http://localhost:8000/api/health -TimeoutSec 3 -UseBasicParsing | Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
  if not errorlevel 1 goto :apiok
)
echo [エラー] APIが起動しません。startup.log と黒い画面を確認してください。
echo api timeout >> "%LOG%"
pause
exit /b 1
:apiok
echo Web画面の起動待ち（最大120秒）...
for /l %%i in (1,1,24) do (
  timeout /t 5 /nobreak >nul
  powershell -NoProfile -Command "try { Invoke-WebRequest -Uri http://localhost:3000 -TimeoutSec 3 -UseBasicParsing | Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
  if not errorlevel 1 goto :webok
)
echo [注意] Web画面の確認が取れませんでした。黒い画面を確認してください。
echo web timeout >> "%LOG%"
pause
exit /b 1
:webok
echo 起動しました。ブラウザを開きます...
start http://localhost:3000
echo [%date% %time%] ready >> "%LOG%"
pause
