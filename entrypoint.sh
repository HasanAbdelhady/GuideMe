#!/usr/bin/env bash
set -e

echo "🚀 Starting GuideMe application..."

# Set Django settings module
export DJANGO_SETTINGS_MODULE=chatgpt.settings

# Wait for database to be ready (Railway PostgreSQL)
echo "⏳ Waiting for database..."
python << END
import sys
import time
import os
from django.db import connection
from django.db.utils import OperationalError

max_attempts = 30
for i in range(max_attempts):
    try:
        connection.ensure_connection()
        print("✅ Database is ready!")
        break
    except OperationalError:
        if i == max_attempts - 1:
            print("❌ Database connection failed after 30 attempts")
            sys.exit(1)
        print(f"⏳ Database not ready, attempt {i+1}/{max_attempts}...")
        time.sleep(1)
END

# Run migrations
echo "🔄 Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Create superuser if doesn't exist (optional, for convenience)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
    echo "👤 Creating superuser..."
    python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')
    print('Superuser created')
else:
    print('Superuser already exists')
END
fi

echo "✅ Initialization complete!"
echo "🌟 Starting application server..."

# Execute the command (gunicorn)
exec "$@"
