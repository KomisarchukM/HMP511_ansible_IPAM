#!/bin/sh
set -e

python manage.py migrate --noinput

exec gunicorn ipam.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --access-logfile - \
  --error-logfile -
