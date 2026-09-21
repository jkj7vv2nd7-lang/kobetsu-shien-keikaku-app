@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo  個別支援・指導計画アプリ  初回セットアップ
echo ================================================
where python >nul 2>nul
if errorlevel 1 (echo [エラー] pythonが見つかりません。Python 3.12以上をインストールしてください。 & pause & exit /b 1)
where node >nul 2>nul
if errorlevel 1 (echo [エラー] Node.jsが見つかりません。Node.js 22以上をインストールしてください。 & pause & exit /b 1)
echo [1/3] Pythonパッケージをインストール中...
python -m pip install -r backend\requirements.txt
if errorlevel 1 (echo [エラー] インストールに失敗しました & pause & exit /b 1)
echo [2/3] Webパッケージをインストール中...（数分かかります）
cd frontend
call npm install
if errorlevel 1 (echo [エラー] インストールに失敗しました & pause & exit /b 1)
cd ..
echo [3/3] 新潟様式を登録中...
python backend\seed_niigata.py
echo.
echo 完了しました。start.bat をダブルクリックで起動できます。
pause
