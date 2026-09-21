@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo  個別支援・指導計画アプリ  起動中
echo  終わるときは開いた黒い画面を2つとも閉じてください
echo ================================================
where python >nul 2>nul
if errorlevel 1 (echo [エラー] pythonが見つかりません & pause & exit /b 1)
where node >nul 2>nul
if errorlevel 1 (echo [エラー] Node.jsが見つかりません & pause & exit /b 1)
if not exist "frontend\node_modules" (
  echo 初回のためセットアップを実行します...
  call "%~dp0setup.bat"
)
echo 様式データを準備中...
python backend\seed_niigata.py
echo APIサーバを起動します...
start "支援計画API（閉じると終了）" cmd /k "cd /d ""%~dp0"" && python -m uvicorn app.main:app --app-dir backend --port 8000"
echo Web画面を起動します...
start "支援計画Web（閉じると終了）" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"
echo 起動待ち（10秒）...
timeout /t 10 /nobreak >nul
start http://localhost:3000
echo.
echo ブラウザで http://localhost:3000 が開きます。
echo 開かない場合は、黒い画面にエラーが出ていないか確認してください。
echo （よくある原因：前回のサーバが残っている→黒い画面を閉じて再実行）
pause
