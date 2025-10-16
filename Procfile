web: bash entrypoint.sh gunicorn chatgpt.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --threads 2 --timeout 60 --access-logfile - --error-logfile -

