@echo off
title Sift
cd /d "%~dp0"
set VENV=%USERPROFILE%\PhotoWork\.venv-sift
if not exist "%VENV%\Scripts\python.exe" (
  echo First run: setting things up, this takes a minute...
  python -m venv "%VENV%"
  "%VENV%\Scripts\python.exe" -m pip install -q -r requirements.txt
)
"%VENV%\Scripts\python.exe" server.py
pause
