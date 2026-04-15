@echo off
echo 投資判断支援アプリを起動します...
echo.
echo ブラウザで http://localhost:8501 を開いてください
echo.
cd /d "%~dp0"
streamlit run app.py
pause
