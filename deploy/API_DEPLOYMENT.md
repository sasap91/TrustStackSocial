# TrustStackSocial API Deployment Guide

## Overview

This guide covers deploying the TrustStackSocial FastAPI application with SQLite database.

## Prerequisites

- Python 3.8+
- Google Cloud VM instance (or any Linux server)
- API credentials configured

## Quick Start

### 1. Deploy Application

```bash
# On the VM, as truststack user
cd /opt/truststacksocial
./deploy/deploy-app.sh
```

### 2. Load Secrets

```bash
./deploy/load-secrets.sh
```

### 3. Set Up API Service

```bash
# As root
sudo ./deploy/setup-api.sh
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/api/v1/health
```

### Generate Posts
```bash
curl -X POST "http://localhost:8000/api/v1/posts/generate" \
  -H "Content-Type: application/json" \
  -d '{"count": 5, "temperature": 0.7}'
```

### List Posts
```bash
curl "http://localhost:8000/api/v1/posts?skip=0&limit=10"
```

### Fetch Articles
```bash
curl -X POST "http://localhost:8000/api/v1/articles/fetch" \
  -H "Content-Type: application/json" \
  -d '{"count": 10, "min_age_hours": 1, "max_age_days": 7}'
```

### Generate Comments
```bash
curl -X POST "http://localhost:8000/api/v1/comments/generate" \
  -H "Content-Type: application/json" \
  -d '{"temperature": 0.7}'
```

### Run Full Workflow
```bash
curl -X POST "http://localhost:8000/api/v1/workflows/full" \
  -H "Content-Type: application/json" \
  -d '{"post_count": 3, "article_count": 5, "post_to_mastodon": false}'
```

## API Documentation

Once the API is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Database

The SQLite database is located at:
- Default: `data/truststacksocial.db`
- Or set `DATABASE_PATH` environment variable

### Migrating from JSON

If you have existing JSON files, migrate them:

```bash
python3 -c "from src.migrate_json_to_db import migrate_all; migrate_all('output')"
```

## Service Management

```bash
# Start service
sudo systemctl start truststacksocial-api

# Stop service
sudo systemctl stop truststacksocial-api

# Check status
sudo systemctl status truststacksocial-api

# View logs
sudo journalctl -u truststacksocial-api -f

# Restart service
sudo systemctl restart truststacksocial-api
```

## Configuration

### Environment Variables

- `API_HOST`: API host (default: 0.0.0.0)
- `API_PORT`: API port (default: 8000)
- `API_RELOAD`: Enable auto-reload (default: false)
- `DATABASE_PATH`: Database file path

### Database Backup

```bash
# Backup database
cp data/truststacksocial.db data/backup_$(date +%Y%m%d_%H%M%S).db

# Or use gcloud storage
gsutil cp data/truststacksocial.db gs://your-bucket/backups/
```

## Troubleshooting

### API not starting

1. Check service logs:
   ```bash
   sudo journalctl -u truststacksocial-api -n 50
   ```

2. Check if port is in use:
   ```bash
   sudo netstat -tlnp | grep 8000
   ```

3. Test API manually:
   ```bash
   cd /opt/truststacksocial
   source venv/bin/activate
   python api_server.py
   ```

### Database errors

1. Check database file permissions:
   ```bash
   ls -la data/truststacksocial.db
   ```

2. Initialize database:
   ```bash
   python3 -c "from src.database import init_db; init_db()"
   ```

### Authentication errors

1. Verify secrets are loaded:
   ```bash
   cat .env | grep -v "^#"
   ```

2. Reload secrets:
   ```bash
   ./deploy/load-secrets.sh
   ```

## Production Considerations

1. **Reverse Proxy**: Use nginx or Apache as reverse proxy
2. **HTTPS**: Configure SSL/TLS certificates
3. **Authentication**: Add API key authentication
4. **Rate Limiting**: Implement rate limiting
5. **Monitoring**: Set up monitoring and alerting
6. **Backups**: Schedule regular database backups

## Example Nginx Configuration

```nginx
server {
    listen 80;
    server_name api.truststacksocial.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
