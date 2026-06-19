@echo off
setlocal
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist release rmdir /s /q release
mkdir release
.venv\Scripts\python scripts\package_release.py
set EXIT_CODE=%ERRORLEVEL%
endlocal & exit /b %EXIT_CODE%
