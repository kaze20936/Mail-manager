@echo off
chcp 65001 >nul
cd /d %~dp0
echo.
echo ====================================================
echo   Mail Manager  初回セットアップにゃ
echo ====================================================
echo.

:: ── Python 確認
python --version >nul 2>&1
if errorlevel 1 (
    echo  [エラー] Python が見つからないにゃ！
    echo.
    echo  以下のURLから Python 3.10 以上をインストールしてにゃ:
    echo    https://www.python.org/downloads/
    echo.
    echo  インストール時に「Add Python to PATH」に必ずチェックを入れてにゃ！
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  Python %PY_VER% を確認したにゃ ✓
echo.

:: ── ライブラリインストール
echo  必要なライブラリをインストール中にゃ（数分かかることがあるにゃ）...
echo.
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo.
    echo  [エラー] ライブラリのインストールに失敗したにゃ...
    echo  インターネット接続を確認してもう一度実行してにゃ。
    echo.
    pause
    exit /b 1
)
echo  ライブラリのインストール完了にゃ ✓
echo.

:: ── .env ファイル作成
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo  .env ファイルを作成したにゃ ✓
    ) else (
        echo ANTHROPIC_API_KEY=>> .env
        echo NOTION_TOKEN=>> .env
        echo NOTION_PARENT_PAGE_ID=>> .env
        echo  .env ファイルを作成したにゃ ✓
    )
) else (
    echo  .env ファイルはすでにあるにゃ ✓
)
echo.

:: ── 完了
echo ====================================================
echo   セットアップ完了にゃ！
echo.
echo   次のステップにゃ:
echo    1. start.bat をダブルクリックしてアプリを起動にゃ
echo    2. ブラウザが自動で開くにゃ
echo    3. 画面の「初期設定」タブでAPIキーを入力するにゃ
echo ====================================================
echo.
pause
