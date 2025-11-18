$ErrorActionPreference = 'Stop'
if (-not (Test-Path .\.venv)) { py -3 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py setup_demo_safe
.\.venv\Scripts\python.exe manage.py create_debug_users
Write-Host "Starting at http://127.0.0.1:8000/ (login page has NO sidebar)"
python manage.py makemigrations
python manage.py makemigrations timesheets
python manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py runserver

python manage.py set_phd --user casual_2 --phd 1
python manage.py set_phd --user casual_debug2 --phd 1
