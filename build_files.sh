#!/bin/bash
echo "Installing pip if required..."
python3 -m ensurepip --upgrade
python3 -m pip install --upgrade pip
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "Building the project..."
python3 -m pip install -r "$ROOT/requirements.txt"
echo "Make Migration..."
cd "$ROOT/src"
zensical build
python3 manage.py makemigrations --noinput
python3 manage.py migrate --noinput
echo "Collect Static..."
python3 manage.py collectstatic --noinput --clear
