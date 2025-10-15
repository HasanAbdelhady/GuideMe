# Deployment Guide

## 🚀 Railway Deployment (Production)

GuideMe is deployed on Railway using the Dockerfile.

### What Railway Uses:
- **Dockerfile** - Main deployment configuration
- **railway.json** - Railway-specific settings
- **entrypoint.sh** - Initialization script (migrations, static files)

### What Railway Provides:
- PostgreSQL database with pgvector extension
- Environment variables (set in Railway dashboard)
- Automatic deployments from GitHub

### Required Environment Variables:
```env
DATABASE_URL=<provided by Railway>
SECRET_KEY=<your secret key>
DEBUG=False
ALLOWED_HOSTS=guideme-eg.duckdns.org
GROQ_API_KEY=<your key>
GOOGLE_API_KEY=<your key>
FLASHCARD=<your key>

# Optional superuser auto-creation
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_PASSWORD=<secure password>
DJANGO_SUPERUSER_EMAIL=admin@example.com
```

## 🔄 CI/CD Pipeline

Single streamlined workflow: `.github/workflows/main.yml`

### On Pull Request:
- ✅ Linting (Black, Flake8)
- ✅ Unit tests with coverage
- ✅ Security scan (Trivy)

### On Push to Main:
- ✅ All PR checks
- ✅ Build & push Docker image to GHCR
- ✅ Deploy to Railway
- ✅ Health check

## 🐳 Docker Compose (Local/Self-Hosted Only)

Railway **does not use** docker-compose. These are for local development or self-hosted deployments:

### Local Development:
```bash
docker-compose up
```
- Hot reload enabled
- Debug mode on
- Database exposed on port 5432

### Self-Hosted Production:
```bash
docker-compose -f docker-compose.prod.yml up -d
```
- Nginx reverse proxy
- Production settings
- Persistent volumes

### Self-Hosted with SSL:
```bash
docker-compose -f docker-compose.public.yml up -d
```
- Nginx with SSL/TLS
- Certbot for Let's Encrypt
- Auto-renewal

## 📊 What Was Removed

Cleaned up **massive overkill** in CI/CD:

### Before: 7 workflows (~2000 lines)
- ci.yml (396 lines)
- deploy.yml (303 lines)
- codeql-analysis.yml (43 lines)
- hotfix.yml (299 lines)
- pr-checks.yml (280 lines)
- scheduled.yml (313 lines)
- security.yml (386 lines)

### After: 1 workflow (163 lines)
- main.yml - All essential features in one place

### Removed Features:
- ❌ Duplicate security scans
- ❌ Placeholder performance tests
- ❌ Commented-out deployment code
- ❌ Over-engineered hotfix pipeline
- ❌ Extensive PR validation
- ❌ Daily/weekly scheduled jobs
- ❌ Non-functional integration tests

## ✅ Performance Improvements

1. **Dockerfile Optimization:**
   - Using exec mode for all RUN commands
   - Multi-stage could be added if needed
   - Health check included
   - Proper logging

2. **CI/CD Optimization:**
   - Single workflow (faster, simpler)
   - Proper caching (pip, Docker layers)
   - Only essential checks
   - ~92% reduction in workflow code

3. **Docker Compose Clarity:**
   - Clear separation: dev vs prod
   - Health checks on database
   - Proper restart policies
   - Volume management

## 🔧 Quick Commands

```bash
# Local development
docker-compose up

# Run tests locally
python manage.py test

# Check code formatting
black --check .

# Build for production (Railway does this automatically)
docker build -t guideme .

# Manual Railway deployment
railway up
```

## 📝 Notes

- Railway automatically runs migrations via entrypoint.sh
- Static files collected on each deployment
- Database connections are health-checked before starting
- Superuser can be auto-created via environment variables

