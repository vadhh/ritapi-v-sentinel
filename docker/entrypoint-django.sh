#!/bin/sh
set -e

python manage.py migrate --no-input

python manage.py shell -c "
from django.contrib.auth import get_user_model
U = get_user_model()
if not U.objects.filter(username='admin').exists():
    U.objects.create_superuser('admin', 'admin@demo.local', 'admin123')
    print('Demo superuser created: admin / admin123')
else:
    print('Demo superuser already exists')
"

exec python manage.py runserver 0.0.0.0:8000
