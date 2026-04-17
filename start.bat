@echo off
chcp 65001 >nul
cd /d %~dp0
echo.
echo ====================================================
echo   Mail Manager を起動するにゃ
echo ====================================================
echo.

:: ── Python 確認
python --version >nul 2>&1
if errorlevel 1 (
    echo  [エラー] Python が見つからないにゃ！
    echo.
    echo  setup.bat を先に実行してにゃ。
    echo.
    pause
    exit /b 1
)

:: ── ライブラリ確認（streamlit がなければ案内）
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo  [エラー] 必要なライブラリがインストールされていないにゃ！
    echo.
    echo  setup.bat を先に実行してにゃ。
    echo.
    pause
    exit /b 1
)

:: ── .env 確認（なければ作成して続行）
if not exist .env (
    echo  .env ファイルがないにゃ → 自動で作成するにゃ
    echo ANTHROPIC_API_KEY=>> .env
    echo NOTION_TOKEN=>> .env
    echo NOTION_PARENT_PAGE_ID=>> .env
)

echo  起動準備完了にゃ ✓
echo.
echo  少し待つとブラウザが自動で開くにゃ...
echo  （開かない場合は http://localhost:8501 をブラウザで開いてにゃ）
echo.
echo  終了するときはこのウィンドウを閉じるか Ctrl+C を押してにゃ
echo.

:: ── ブラウザを少し遅延して開く（アプリ起動後に開くため）
timeout /t 3 /nobreak >nul
start "" http://localhost:8501

:: ── アプリ起動
python -m streamlit run app.py --server.headless true --browser.gatherUsageStats false
pause
