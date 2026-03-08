# Production Deployment Guide

Complete guide to deploying the UEBA cybersecurity platform to production with proper security configuration.

## 🚀 Pre-Deployment Checklist

### Code & Configuration
- [ ] All tests pass (see TESTING_GUIDE.md)
- [ ] No hardcoded secrets in code
- [ ] `.env` file excluded from Git
- [ ] `DEBUG=False` in production environment
- [ ] Unique `SECRET_KEY` generated
- [ ] Git repository cleaned and committed
- [ ] No sensitive files in public directories
- [ ] All dependencies in requirements.txt

### Database
- [ ] Database migrations applied
- [ ] Database backups configured
- [ ] User accounts created (admin user)
- [ ] Indexes created for performance
- [ ] Database connections secured
- [ ] Replication/HA configured (if applicable)

### Authentication & Security
- [ ] HTTPS/SSL certificate obtained and configured
- [ ] All OAuth credentials obtained (Google, GitHub, etc.)
- [ ] Redirect URIs configured for production domain
- [ ] CORS origins whitelisted
- [ ] Rate limiting configured
- [ ] User authentication tested end-to-end
- [ ] Password reset email service configured
- [ ] Account lockout/throttling enabled

### Infrastructure
- [ ] Server provisioned and secured
- [ ] Firewall rules configured
- [ ] Load balancer setup (if multiple servers)
- [ ] CDN configured (if needed)
- [ ] Monitoring & logging infrastructure ready
- [ ] Backup strategy implemented
- [ ] Disaster recovery plan documented
- [ ] DDoS protection enabled

### DNS & Domain
- [ ] Domain DNS configured
- [ ] DNS propagation verified
- [ ] HTTPS certificate configured
- [ ] Subdomain redirects configured
- [ ] SPF/DKIM records for email
- [ ] Security headers configured

---

## 🔒 Security Configuration

### 1. Environment Variables

Create production `.env` file:

```env
# ===== Application Config =====
SECRET_KEY=your-super-secret-key-min-32-chars-change-this
DEBUG=False
ENVIRONMENT=production
APP_NAME=UEBA Security Hub
APP_VERSION=1.0.0

# ===== Server Config =====
HOST=0.0.0.0
PORT=8000
WORKERS=4
RELOAD=False

# ===== Database Config =====
DATABASE_URL=mysql://user:password@db.production.com:3306/ueba_db
# Or PostgreSQL:
# DATABASE_URL=postgresql://user:password@db.production.com:5432/ueba_db

# ===== Security Config =====
SECURE_COOKIES=True
COOKIE_HTTPONLY=True
COOKIE_SAMESITE=strict
CORS_ORIGINS=["https://yourdomain.com", "https://www.yourdomain.com"]
ALLOWED_HOSTS=["yourdomain.com", "www.yourdomain.com"]

# ===== HTTPS Config =====
HTTPS_ENABLED=True
SSL_CERT_FILE=/etc/ssl/certs/yourdomain.crt
SSL_KEY_FILE=/etc/ssl/private/yourdomain.key

# ===== OAuth Config =====
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/google/callback

GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GITHUB_REDIRECT_URI=https://yourdomain.com/auth/github/callback

MICROSOFT_CLIENT_ID=your-azure-client-id
MICROSOFT_CLIENT_SECRET=your-azure-client-secret
MICROSOFT_REDIRECT_URI=https://yourdomain.com/auth/microsoft/callback

# ===== Email Config =====
SMTP_SERVER=smtp.sendgrid.net  # Or your email provider
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=your-sendgrid-api-key
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=UEBA Security Hub

# ===== Logging Config =====
LOG_LEVEL=INFO
LOG_FILE=/var/log/ueba/app.log
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# ===== Feature Flags =====
ENABLE_OAUTH=True
ENABLE_PASSWORD_RESET=True
ENABLE_REGISTRATION=True
ENABLE_2FA=False  # Coming in v2.0

# ===== Advanced Security =====
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=3600  # seconds
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION=900  # seconds
PASSWORD_EXPIRY_DAYS=90  # 0 = disabled
HOME_SESSION_TIMEOUT=1800  # seconds
```

**Security Notes:**
- Never commit `.env` to version control
- Use `.env.example` as template
- Rotate `SECRET_KEY` before production
- Generate strong secrets: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

### 2. HTTPS/SSL Configuration

#### Using Let's Encrypt (Free SSL)

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Certificates will be at:
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem

# Auto-renewal (runs daily)
sudo certbot renew --pre-hook "systemctl stop fastapi" --post-hook "systemctl start fastapi"
```

#### Nginx Configuration (Reverse Proxy)

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:50m;
    ssl_session_timeout 1d;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;

    # Proxy to FastAPI
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

### 3. Database Security

#### MySQL Connection String (Production)

```python
# app/database.py
from sqlalchemy import create_engine
import os

# Secure database connection
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'mysql://user:password@localhost:3306/ueba_db?charset=utf8mb4&ssl_mode=REQUIRED'
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Test connections before using
    pool_recycle=3600,   # Recycle connections hourly
    echo=False,          # No SQL logging in production
    max_overflow=20,
    pool_size=10
)
```

#### Database User Permissions

```sql
-- Create limited database user
CREATE USER 'ueba_app'@'%' IDENTIFIED BY 'strong-password-here';

-- Grant only necessary permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON ueba_db.* TO 'ueba_app'@'%';

-- Remove unnecessary permissions
REVOKE ALTER, CREATE, DROP, GRANT OPTION ON ueba_db.* FROM 'ueba_app'@'%';

-- Apply changes
FLUSH PRIVILEGES;
```

### 4. Application Hardening

Update `app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZIPMiddleware
import os

app = FastAPI(
    title="UEBA Security Hub",
    description="Enterprise cybersecurity platform",
    version="1.0.0",
    docs_url=None if os.getenv('ENVIRONMENT') == 'production' else '/docs'  # Hide in production
)

# Security Middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=os.getenv('ALLOWED_HOSTS', 'localhost').split(',')
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('CORS_ORIGINS', 'http://localhost').split(','),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=3600
)

# Compression middleware
app.add_middleware(GZIPMiddleware, minimum_size=1000)

# Security headers
from fastapi.responses import Response

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

---

## 📦 Deployment Options

### Option 1: Traditional VPS (Recommended for Beginners)

#### 1.1 DigitalOcean / Linode / Vultr Deployment

**Server Setup:**

```bash
# SSH into server
ssh root@your-server-ip

# Update system
apt-get update && apt-get upgrade -y

# Install Python and dependencies
apt-get install -y python3.9 python3-pip python3-venv
apt-get install -y nginx supervisor redis-server
apt-get install -y mysql-server mysql-client

# Create application directory
mkdir -p /var/www/ueba-app
cd /var/www/ueba-app

# Clone repository
git clone https://github.com/yourusername/ueba-project.git .
cd /var/www/ueba-app

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with production settings
nano .env

# Initialize database
python create_db.py

# Set permissions
chown -R www-data:www-data /var/www/ueba-app
chmod -R 755 /var/www/ueba-app
```

**Supervisor Configuration:**

```bash
# Create supervisor config
sudo nano /etc/supervisor/conf.d/ueba.conf
```

```ini
[program:ueba]
directory=/var/www/ueba-app
command=/var/www/ueba-app/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/ueba/app.log
environment=PATH="/var/www/ueba-app/venv/bin"

[program:ueba-worker]
directory=/var/www/ueba-app
command=/var/www/ueba-app/venv/bin/python -m celery -A app.celery worker --loglevel=info
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/ueba/worker.log
environment=PATH="/var/www/ueba-app/venv/bin"
```

**Start Services:**

```bash
# Create log directory
mkdir -p /var/log/ueba
chown www-data:www-data /var/log/ueba

# Update supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all

# Check status
sudo supervisorctl status
```

### Option 2: Docker Container Deployment

#### 2.1 Create Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 2.2 Docker Compose for Production

```yaml
version: '3.8'

services:
  db:
    image: mysql:8.0
    container_name: ueba_db
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
      MYSQL_DATABASE: ${DB_NAME}
      MYSQL_USER: ${DB_USER}
      MYSQL_PASSWORD: ${DB_PASSWORD}
    volumes:
      - db_data:/var/lib/mysql
      - ./schema.sql:/docker-entrypoint-initdb.d/schema.sql
    networks:
      - ueba_network
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: ueba_redis
    networks:
      - ueba_network
    restart: unless-stopped

  app:
    build: .
    container_name: ueba_app
    environment:
      DATABASE_URL: mysql://${DB_USER}:${DB_PASSWORD}@db:3306/${DB_NAME}
      REDIS_URL: redis://redis:6379/0
    volumes:
      - ./logs:/app/logs
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    networks:
      - ueba_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: ueba_nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - app
    networks:
      - ueba_network
    restart: unless-stopped

volumes:
  db_data:

networks:
  ueba_network:
    driver: bridge
```

#### 2.3 Build and Deploy

```bash
# Build Docker image
docker build -t ueba-app:latest .

# Tag for registry
docker tag ueba-app:latest your-registry/ueba-app:latest

# Push to registry
docker push your-registry/ueba-app:latest

# Deploy with docker-compose
docker-compose -f docker-compose.yml up -d

# Check logs
docker-compose logs -f app
```

### Option 3: Cloud Platform (AWS/Google Cloud/Azure)

#### AWS Elastic Beanstalk

```bash
# Install EB CLI
pip install awsebcli

# Initialize project
eb init -p python-3.9 ueba-app --region us-east-1

# Create environment
eb create ueba-prod

# Deploy
git push && eb deploy

# View logs
eb logs
```

#### Google Cloud App Engine

```bash
# Create app.yaml
cat > app.yaml << EOF
runtime: python39

env: standard

env_variables:
  DATABASE_URL: "cloudsql://user:pass@/database"
  ENVIRONMENT: "production"

handlers:
- url: /.*
  script: auto

EOF

# Deploy
gcloud app deploy
```

---

## 📊 Monitoring & Logging

### 1. Application Monitoring

```python
# app/main.py
from prometheus_client import Counter, Histogram, expose_metrics_app
import time

# Metrics
login_attempts = Counter('login_attempts', 'Total login attempts', ['status'])
password_resets = Counter('password_resets', 'Total password resets')
request_time = Histogram('request_duration', 'Request duration in seconds')

@app.middleware("http")
async def track_metrics(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    
    request_time.observe(duration)
    return response

# Expose metrics endpoint
expose_metrics_app(app, "/metrics")
```

### 2. Error Tracking with Sentry

```python
# app/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[
        FastApiIntegration(),
        SqlalchemyIntegration(),
    ],
    traces_sample_rate=1.0,
    environment=os.getenv("ENVIRONMENT", "production")
)
```

### 3. Structured Logging

```python
import logging
import json
from pythonjsonlogger import jsonlogger

# Configure logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)
```

---

## 📈 Performance Optimization

### 1. Database Optimization

```sql
-- Create indexes
CREATE INDEX idx_user_email ON user(email);
CREATE INDEX idx_user_created_at ON user(created_at);
CREATE INDEX idx_reset_token_user_id ON password_reset_token(user_id);
CREATE INDEX idx_reset_token_expires_at ON password_reset_token(expires_at);
CREATE INDEX idx_reset_token_used ON password_reset_token(used);
```

### 2. Caching Strategy

```python
# app/main.py
from functools import lru_cache
import redis

# Connect to Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0)

@app.get("/api/cache-stats")
async def get_cached_stats():
    # Check cache first
    cached = redis_client.get('dashboard_stats')
    if cached:
        return json.loads(cached)
    
    # Calculate if not cached
    stats = calculate_stats()
    
    # Cache for 5 minutes
    redis_client.setex('dashboard_stats', 300, json.dumps(stats))
    
    return stats
```

### 3. Database Connection Pooling

Already configured in database.py with SQLAlchemy pool settings.

---

## 🔄 Backup & Disaster Recovery

### 1. Database Backups

```bash
#!/bin/bash
# backup.sh - Daily database backup

BACKUP_DIR="/backups/ueba"
DATE=$(date +%Y%m%d_%H%M%S)
DB_USER="ueba_app"
DB_PASS="your-password"
DB_NAME="ueba_db"
DB_HOST="localhost"

# Create backup
mysqldump -h $DB_HOST -u $DB_USER -p$DB_PASS $DB_NAME > \
    $BACKUP_DIR/ueba_backup_$DATE.sql

# Compress
gzip $BACKUP_DIR/ueba_backup_$DATE.sql

# Upload to S3
aws s3 cp $BACKUP_DIR/ueba_backup_$DATE.sql.gz \
    s3://your-bucket/backups/

# Clean old backups (keep 30 days)
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

### 2. Automated Backup Schedule

```bash
# Add to crontab
crontab -e

# Run daily at 2 AM
0 2 * * * /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1
```

### 3. Recovery Procedure

```bash
# Restore from backup
gunzip < backup.sql.gz | mysql -u $DB_USER -p $DB_NAME

# Verify restore
mysql -u $DB_USER -p $DB_NAME -e "SELECT COUNT(*) FROM user;"
```

---

## 🧪 Post-Deployment Testing

### 1. Smoke Tests

```bash
#!/bin/bash
# Test basic functionality

BASE_URL="https://yourdomain.com"

# Test homepage
curl -f $BASE_URL/ || exit 1

# Test login page
curl -f $BASE_URL/login || exit 1

# Test signup page
curl -f $BASE_URL/signup || exit 1

# Test forgot password page
curl -f $BASE_URL/forgot-password || exit 1

echo "✓ All smoke tests passed"
```

### 2. Full Test Suite

```bash
# Run integration tests
python -m pytest tests/ -v

# Run load tests
locust -f tests/load/locustfile.py --host=https://yourdomain.com
```

---

## 🔐 Security Audit Checklist

Before going live:

- [ ] HTTPS/SSL working
- [ ] Security headers present
- [ ] Database credentials secure
- [ ] Secret keys unique
- [ ] No debug mode enabled
- [ ] Rate limiting working
- [ ] CORS properly configured
- [ ] Input validation in place
- [ ] SQL injection protection verified
- [ ] XSS protection verified
- [ ] CSRF tokens working
- [ ] Password hashing confirmed
- [ ] No plaintext secrets
- [ ] Backups automated
- [ ] Monitoring configured
- [ ] Error handling in place
- [ ] User authentication tested
- [ ] OAuth properly configured
- [ ] Email delivery tested
- [ ] Load testing passed

---

## 📞 Support & Rollback

### If Something Goes Wrong

1. **Check Logs:**
   ```bash
   tail -f /var/log/ueba/app.log
   ```

2. **Restart Application:**
   ```bash
   sudo systemctl restart fastapi
   # or
   docker-compose restart app
   ```

3. **Rollback Deployment:**
   ```bash
   git revert <commit-hash>
   git push
   # Redeploy
   ```

4. **Database Issues:**
   ```bash
   # Restore from last backup
   gunzip < backup.sql.gz | mysql -u user -p database
   ```

---

## 📚 Additional Resources

- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [OWASP Production Guidelines](https://owasp.org/www-project-web-security-testing-guide/)
- [SSL Configuration](https://ssl-config.mozilla.org/)
- [Docker Security](https://docs.docker.com/engine/security/)

---

## ✅ Deployment Sign-Off

- [ ] All checklist items completed
- [ ] Security audit passed
- [ ] Performance benchmarks met
- [ ] Backup/recovery tested
- [ ] Monitoring configured
- [ ] Support team trained
- [ ] Runbook documented
- [ ] Go-live approval received

**Deployed by:** ________________  
**Date:** ________________  
**Environment:** production  
**Version:** 1.0.0
