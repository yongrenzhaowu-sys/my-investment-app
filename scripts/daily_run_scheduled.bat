@echo off
REM ========================================
REM 日次自動化システム - Task Scheduler用
REM ========================================
REM
REM このバッチファイルはWindows Task Schedulerから実行されます。
REM
REM 設定:
REM   - タスク名: DailyQuants
REM   - 実行時刻: 毎日 06:00
REM   - プログラム: cmd
REM   - 引数: /c "C:\Users\yongr\claude project\workspace\scripts\daily_run_scheduled.bat"
REM
REM 作成日: 2026-02-21
REM ========================================

REM 作業ディレクトリに移動
cd /d "C:\Users\yongr\claude project\workspace"

REM 環境変数チェック
if "%JQUANTS_API_KEY%"=="" (
    echo [ERROR] JQUANTS_API_KEY environment variable is not set
    echo Please set the system environment variable JQUANTS_API_KEY
    exit /b 1
)

REM 実行開始ログ
echo ========================================
echo Daily Automation Started: %DATE% %TIME%
echo ========================================

REM Python実行
python scripts\daily_run.py

REM 終了コードを保存
set EXIT_CODE=%ERRORLEVEL%

REM 実行終了ログ
echo ========================================
echo Daily Automation Finished: %DATE% %TIME%
echo Exit Code: %EXIT_CODE%
echo ========================================

REM 終了コードをそのまま返す
exit /b %EXIT_CODE%
