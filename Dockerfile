
# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Expose port 8000
EXPOSE 8000

# Run the application (Heroku provides $PORT)
ENV PORT=8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["sh","-c","gunicorn chatgpt.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --threads 2 --timeout 60"]