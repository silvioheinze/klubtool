#!/bin/sh

python manage.py collectstatic --noinput
python manage.py relabel_local_migrations
python manage.py migrate

exec "$@"