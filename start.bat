@echo off
chcp 65001 > nul
cd /d %~dp0

echo.
echo  AUDIT 로컬 웹호스트를 실행합니다.
echo.

REM ── audit.db 백업 (서버 기동 전에 한다) ─────────────────────────
REM 사본을 하나만 두면, DB가 비어버린 뒤 서버를 다시 켰을 때 그 빈 DB가
REM 멀쩡한 백업을 덮어쓴다. 3세대를 돌려 그런 경우에도 이전 상태가 남게 한다.
if exist "audit.db" (
    if exist "audit.db.bak3" del "audit.db.bak3"
    if exist "audit.db.bak2" ren "audit.db.bak2" "audit.db.bak3"
    if exist "audit.db.bak"  ren "audit.db.bak"  "audit.db.bak2"
    copy /y "audit.db" "audit.db.bak" > nul

    for %%I in ("audit.db.bak") do set BAKSIZE=%%~zI
    call echo  백업 완료 : audit.db.bak ^(%%BAKSIZE%% bytes^)
    echo             직전 2세대는 audit.db.bak2 / audit.db.bak3 에 남습니다.
) else (
    echo  audit.db 가 없어 백업을 건너뜁니다 ^(첫 실행이면 정상입니다^).
)
echo.

start "AUDIT 백엔드"    cmd /k python -m uvicorn app.main:app --reload
start "AUDIT 프론트엔드" cmd /k "cd frontend && npm run dev"

REM ── Claude Code (분석·카드뉴스용) ───────────────────────────────
REM 설치돼 있을 때만 띄운다. 없다고 서버 실행까지 막을 이유는 없다.
where claude >nul 2>&1
if errorlevel 1 (
    set CLAUDE_LINE= Claude Code: 미설치 ^(npm install -g @anthropic-ai/claude-code^)
) else (
    start "AUDIT Claude Code" cmd /k claude
    set CLAUDE_LINE= Claude Code: 별도 창에서 실행됨
)

echo  백엔드    : http://localhost:8000
echo  프론트엔드 : http://localhost:3000
call echo %%CLAUDE_LINE%%
echo.
echo  잠시 후 브라우저에서 http://localhost:3000 으로 접속하세요.
echo  종료하려면 열린 창들을 닫으면 됩니다.
echo.
pause
