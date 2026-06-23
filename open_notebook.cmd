@echo off
cd /d "%~dp0"
".venv\Scripts\jupyter-lab.exe" notebooks\final_sber_procurement_report.ipynb
pause
