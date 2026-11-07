@echo off
REM RepoLens startup script for Windows
REM Sets UTF-8 encoding so git output doesn't crash on repos with Unicode

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set GIT_TERMINAL_PROMPT=0

echo Starting RepoLens server...
echo API docs: http://localhost:8000/docs
echo.

call venv\Scripts\uvicorn app.main:app --reload --port 8000
