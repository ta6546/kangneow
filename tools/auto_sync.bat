@echo off
rem kangneow notes auto-sync: commit docs changes, pull, push
cd /d "%~dp0.."
git add -A docs CLAUDE.md
git diff --cached --quiet || git commit -q -m "Auto-save notes %date% %time:~0,5%"
git pull --rebase --autostash -q
if errorlevel 1 (
  git rebase --abort
  echo Sync stopped: notes changed in two places. Ask Claude to merge them.>> "%~dp0sync_error.log"
  exit /b 1
)
git push -q
