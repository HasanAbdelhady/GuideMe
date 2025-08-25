#!/usr/bin/env bash

#make virtual env
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
# Install dependencies
python3 -m pip install -r requirements.txt

# Apply migrations
python3 manage.py makemigrations
python3 manage.py migrate

# Start server
python3 manage.py runserver
