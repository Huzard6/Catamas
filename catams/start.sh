#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py setup_demo_safe
python manage.py create_debug_users
python manage.py makemigrations
python manage.py makemigrations timesheets
python manage.py migrate --noinput
python manage.py runserver

python manage.py set_phd --user casual_2 --phd 1 || true
python manage.py set_phd --user casual_debug2 --phd 1 || true
