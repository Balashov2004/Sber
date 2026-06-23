@echo off
cd /d "%~dp0"
"C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" stages\stage4\scripts\build_stage4.py
echo.
echo Stage 4 report was generated in data\processed\stage4
pause
