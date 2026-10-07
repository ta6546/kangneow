@echo off
chcp 65001 > nul
cd /d "%~dp0"
python screener.py %*
echo.
echo 결과는 이 폴더의 screener_result.csv 에 저장됐어요.
pause
