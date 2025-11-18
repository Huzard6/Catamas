@echo off
setlocal

REM Move to this script's directory
cd /d %~dp0

REM Activate virtualenv if present
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
)

REM Ensure DB is migrated
python manage.py migrate

REM Ensure TA group and add ta_debug
python manage.py init_ta_group

REM Start server
python manage.py runserver

echo.
echo ==============================
echo   Press any key to close...
echo ==============================
pause >nul
