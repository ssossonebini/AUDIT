@echo off
chcp 65001 > nul
cd /d %~dp0

echo.
echo  AUDIT 로컬 웹호스트를 실행합니다.
echo.

start "AUDIT 백엔드"    cmd /k python -m uvicorn app.main:app --reload
start "AUDIT 프론트엔드" cmd /k "cd frontend && npm run dev"

echo  백엔드   : http://localhost:8000
echo  프론트엔드: http://localhost:3000
echo.
echo  잠시 후 브라우저에서 http://localhost:3000 으로 접속하세요.
echo  종료하려면 열린 두 창을 닫으면 됩니다.
echo.
pause
