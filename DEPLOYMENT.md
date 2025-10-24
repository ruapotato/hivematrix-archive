# Archive Service Deployment Guide

Complete step-by-step deployment guide for the Archive service.

## Overview

Archive stores immutable billing snapshots with:
- API for accepting snapshots from Ledger
- Web UI for viewing historical bills
- Scheduled automated snapshot creation
- Search and retrieval capabilities

## Prerequisites

- PostgreSQL 12+ database server
- Python 3.8+
- Codex service running (port 5010)
- Ledger service running (port 5011)
- Service-to-service authentication configured

## Deployment Steps

### 1. Environment Setup

**Create service user (production):**
```bash
sudo useradd -r -s /bin/bash -d /opt/hivematrix hivematrix
sudo mkdir -p /opt/hivematrix
sudo chown hivematrix:hivematrix /opt/hivematrix
```

**Clone repository:**
```bash
cd /opt/hivematrix
sudo -u hivematrix git clone https://github.com/yourorg/hivematrix-archive.git
cd hivematrix-archive
```

**Create virtual environment:**
```bash
sudo -u hivematrix python3 -m venv venv
sudo -u hivematrix venv/bin/pip install -r requirements.txt
```

### 2. Database Configuration

**Create PostgreSQL database and user:**
```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE archive_db;
CREATE USER archive_user WITH ENCRYPTED PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE archive_db TO archive_user;
\q
```

**Initialize database:**
```bash
sudo -u hivematrix venv/bin/python init_db.py
```

This will:
- Prompt for database connection details
- Test the connection
- Create all tables
- Set up default scheduler configuration

**Verify database:**
```bash
psql -U archive_user -d archive_db -c "SELECT tablename FROM pg_tables WHERE schemaname='public';"
```

Expected tables:
- billing_snapshots
- snapshot_line_items
- scheduled_snapshots
- snapshot_jobs

### 3. Environment Configuration

**Create .flaskenv file:**
```bash
sudo -u hivematrix nano .flaskenv
```

```bash
FLASK_APP=app
FLASK_ENV=production
SERVICE_PORT=5012
SERVICE_NAME=archive

# Service URLs
CODEX_URL=http://localhost:5010
LEDGER_URL=http://localhost:5011

# Service authentication
SERVICE_TOKEN=your-service-secret-token
ADMIN_TOKEN=your-admin-secret-token
```

**Secure the file:**
```bash
sudo chmod 600 .flaskenv
sudo chown hivematrix:hivematrix .flaskenv
```

### 4. Service Configuration

**Create systemd service file:**
```bash
sudo cp systemd/archive-snapshot.service /etc/systemd/system/
sudo cp systemd/archive-snapshot.timer /etc/systemd/system/
```

**Create Archive web service file:**
```bash
sudo nano /etc/systemd/system/archive.service
```

```ini
[Unit]
Description=Archive Billing Service
After=network.target postgresql.service

[Service]
Type=simple
User=hivematrix
Group=hivematrix
WorkingDirectory=/opt/hivematrix/hivematrix-archive
Environment="PATH=/opt/hivematrix/hivematrix-archive/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/hivematrix/hivematrix-archive/venv/bin/python3 run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start services:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable archive.service
sudo systemctl enable archive-snapshot.timer
sudo systemctl start archive.service
sudo systemctl start archive-snapshot.timer
```

**Verify services are running:**
```bash
sudo systemctl status archive.service
sudo systemctl status archive-snapshot.timer
curl http://localhost:5012/health
```

### 5. Ledger Integration

**Update Ledger configuration to include Archive:**

Edit Ledger's `instance/ledger.conf`:
```ini
[services]
codex_url = http://localhost:5010
archive_url = http://localhost:5012
```

**Restart Ledger:**
```bash
sudo systemctl restart ledger.service
```

### 6. Reverse Proxy (Production)

**Configure nginx:**
```bash
sudo nano /etc/nginx/sites-available/archive
```

```nginx
server {
    listen 443 ssl http2;
    server_name archive.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/archive.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/archive.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:5012;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Enable site:**
```bash
sudo ln -s /etc/nginx/sites-available/archive /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 7. Firewall Configuration

```bash
# Allow Archive port (if needed internally)
sudo ufw allow 5012/tcp comment 'Archive Service'

# Allow nginx (if using reverse proxy)
sudo ufw allow 'Nginx Full'
```

### 8. Testing

**Test health endpoint:**
```bash
curl http://localhost:5012/health
# Expected: {"status": "ok", "service": "archive"}
```

**Test snapshot creation (requires Ledger and Codex running):**
```bash
cd /opt/hivematrix/hivematrix-archive
venv/bin/python test_workflow.py --account 620547 --year 2025 --month 10
```

**Test scheduled snapshot manually:**
```bash
sudo -u hivematrix venv/bin/python scheduled_snapshots.py --year 2025 --month 10 --all --dry-run
```

**Check scheduler timer:**
```bash
systemctl list-timers archive-snapshot.timer
journalctl -u archive-snapshot.service -n 50
```

### 9. Monitoring

**Service logs:**
```bash
# Archive web service
sudo journalctl -u archive.service -f

# Snapshot scheduler
sudo journalctl -u archive-snapshot.service -f

# All Archive logs
sudo journalctl -u archive.service -u archive-snapshot.service -f
```

**Database monitoring:**
```bash
psql -U archive_user -d archive_db -c "SELECT COUNT(*) FROM billing_snapshots;"
psql -U archive_user -d archive_db -c "SELECT MAX(archived_at) FROM billing_snapshots;"
```

**API monitoring:**
```bash
# Get scheduler status
curl -H "Authorization: Bearer $SERVICE_TOKEN" http://localhost:5012/api/scheduler/config

# Check recent jobs
curl -H "Authorization: Bearer $SERVICE_TOKEN" http://localhost:5012/api/scheduler/jobs

# Search snapshots
curl -H "Authorization: Bearer $SERVICE_TOKEN" "http://localhost:5012/api/snapshots/search?limit=10"
```

### 10. Backup Strategy

**Database backups:**
```bash
# Create backup script
sudo nano /opt/hivematrix/backup-archive.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/hivematrix/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

pg_dump -U archive_user archive_db | gzip > $BACKUP_DIR/archive_$TIMESTAMP.sql.gz

# Keep last 30 days of backups
find $BACKUP_DIR -name "archive_*.sql.gz" -mtime +30 -delete
```

```bash
chmod +x /opt/hivematrix/backup-archive.sh
```

**Schedule daily backups:**
```bash
sudo crontab -e
```

```bash
0 3 * * * /opt/hivematrix/backup-archive.sh
```

## Verification Checklist

- [ ] PostgreSQL database created and accessible
- [ ] Archive service running on port 5012
- [ ] Health endpoint returns 200 OK
- [ ] Scheduler timer enabled and configured
- [ ] Ledger knows about Archive service
- [ ] Test snapshot creation succeeds
- [ ] Web UI accessible and showing data
- [ ] Scheduled snapshot timer configured correctly
- [ ] Reverse proxy configured (production)
- [ ] SSL certificates installed (production)
- [ ] Firewall rules configured
- [ ] Log rotation configured
- [ ] Backup strategy implemented
- [ ] Monitoring alerts configured

## Troubleshooting

### Archive service won't start

```bash
# Check logs
sudo journalctl -u archive.service -n 100

# Check database connection
psql -U archive_user -d archive_db -c "SELECT 1;"

# Check file permissions
ls -la /opt/hivematrix/hivematrix-archive/instance/

# Check port availability
sudo netstat -tlnp | grep 5012
```

### Snapshot creation fails

```bash
# Check Ledger connectivity
curl http://localhost:5011/health

# Check service authentication
# Verify SERVICE_TOKEN matches between services

# Check Codex connectivity (Ledger needs Codex)
curl http://localhost:5010/health

# Review failed job details
curl -H "Authorization: Bearer $SERVICE_TOKEN" http://localhost:5012/api/scheduler/jobs
```

### Scheduler not running

```bash
# Check timer status
systemctl status archive-snapshot.timer
systemctl list-timers

# Check service file
cat /etc/systemd/system/archive-snapshot.service

# Test manual run
sudo -u hivematrix /opt/hivematrix/hivematrix-archive/venv/bin/python3 \
  /opt/hivematrix/hivematrix-archive/scheduled_snapshots.py --dry-run

# Check scheduler configuration
curl -H "Authorization: Bearer $SERVICE_TOKEN" http://localhost:5012/api/scheduler/config
```

### Database connection issues

```bash
# Test PostgreSQL connection
psql -U archive_user -d archive_db

# Check PostgreSQL is running
sudo systemctl status postgresql

# Review PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-*.log

# Check connection string in instance/archive.conf
cat /opt/hivematrix/hivematrix-archive/instance/archive.conf
```

### High database disk usage

```bash
# Check database size
psql -U archive_user -d archive_db -c "SELECT pg_size_pretty(pg_database_size('archive_db'));"

# Check table sizes
psql -U archive_user -d archive_db -c "SELECT tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname='public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# Archive is designed to keep all data (no automatic cleanup)
# If disk space is an issue, consider:
# 1. Archiving old snapshots to cold storage
# 2. Implementing retention policies (manual)
# 3. Increasing disk space
```

## Maintenance

### Updating Archive

```bash
cd /opt/hivematrix/hivematrix-archive
sudo -u hivematrix git pull
sudo -u hivematrix venv/bin/pip install -r requirements.txt

# Run migrations if needed
sudo -u hivematrix venv/bin/python init_db.py --migrate-only

# Restart service
sudo systemctl restart archive.service
```

### Changing Scheduler Configuration

**Via API:**
```bash
curl -X POST http://localhost:5012/api/scheduler/config \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "enabled": true,
    "day_of_month": 1,
    "hour": 2,
    "snapshot_previous_month": true,
    "snapshot_all_companies": true
  }'
```

**Via Database:**
```sql
UPDATE scheduled_snapshots SET
  day_of_month = 1,
  hour = 2,
  enabled = true
WHERE id = 1;
```

### Manual Snapshot Creation

```bash
# All companies for specific month
sudo -u hivematrix /opt/hivematrix/hivematrix-archive/scheduled_snapshots.py \
  --year 2025 --month 10 --all

# Specific companies
sudo -u hivematrix /opt/hivematrix/hivematrix-archive/scheduled_snapshots.py \
  --year 2025 --month 10 --accounts 620547,183729

# Dry run to test
sudo -u hivematrix /opt/hivematrix/hivematrix-archive/scheduled_snapshots.py \
  --year 2025 --month 10 --all --dry-run
```

## Security Considerations

1. **Service Tokens**: Use strong, unique tokens for service-to-service authentication
2. **Database Credentials**: Store securely in instance/archive.conf with 0600 permissions
3. **HTTPS Only**: Use SSL certificates for production (Let's Encrypt)
4. **Network Security**: Firewall rules to limit access to Archive
5. **User Authentication**: Implement proper user authentication for web UI
6. **Audit Logging**: Archive creates audit trail automatically
7. **Backup Encryption**: Encrypt database backups

## Performance Tuning

**PostgreSQL optimization for Archive:**
```sql
-- Create indexes for common queries
CREATE INDEX idx_snapshots_company_date ON billing_snapshots(company_account_number, billing_year DESC, billing_month DESC);
CREATE INDEX idx_snapshots_archived ON billing_snapshots(archived_at DESC);

-- Analyze tables
ANALYZE billing_snapshots;
ANALYZE snapshot_line_items;
```

**Application tuning:**
- Adjust Waitress threads in run.py (default: 4)
- Configure PostgreSQL connection pooling
- Monitor slow queries with pg_stat_statements

## Support and Documentation

- Main README: `README.md`
- API Documentation: `README.md` (API Endpoints section)
- Workflow Test: `test_workflow.py`
- Architecture Overview: `../hivematrix-helm/ARCHITECTURE.md`
- Data Flow: `../hivematrix-ledger/DATA_FLOW.md`

## Production Go-Live Checklist

- [ ] All services deployed and tested
- [ ] Database backups configured and tested
- [ ] Monitoring and alerting configured
- [ ] SSL certificates installed and auto-renewal configured
- [ ] Firewall rules tested
- [ ] Service tokens rotated from defaults
- [ ] Load testing completed
- [ ] Disaster recovery plan documented
- [ ] Team trained on Archive operations
- [ ] Documentation reviewed and updated
- [ ] Runbook created for common issues
- [ ] On-call rotation established

---

**Last Updated:** 2025-10-24
**Version:** 1.0
**Maintained By:** HiveMatrix DevOps Team
