# Archive Service - Startup Checklist

This checklist ensures Archive starts correctly via Helm's start.sh and systemd.

## Automatic Startup Requirements

### ✅ Files Required for Helm Auto-Discovery

- [x] `run.py` - Entry point script
- [x] `pyenv/` - Virtual environment with dependencies
- [x] `services.json` - Symlink to ../hivematrix-helm/services.json
- [x] `.flaskenv` - Environment configuration
- [x] `instance/archive.conf` - Database configuration

### ✅ Helm Integration

**services.json entry:**
```json
{
  "archive": {
    "url": "http://localhost:5012",
    "path": "../hivematrix-archive",
    "port": 5012,
    "python_bin": "pyenv/bin/python",
    "run_script": "run.py",
    "visible": true
  }
}
```

**How Helm discovers Archive:**
1. `start.sh` scans for `hivematrix-*/run.py` files
2. Finds `hivematrix-archive/run.py`
3. Starts via `python cli.py start archive`
4. Service binds to `127.0.0.1:5012`

### ✅ Service Configuration

**Port binding:**
- Archive runs on port `5012`
- Binds to `127.0.0.1` (localhost only)
- Nexus reverse proxy handles external access

**Environment variables (.flaskenv):**
```bash
FLASK_APP=app
FLASK_ENV=development
SERVICE_NAME=archive
SERVICE_PORT=5012
CORE_SERVICE_URL=http://localhost:5000
HELM_SERVICE_URL=http://localhost:5004
CODEX_SERVICE_URL=http://localhost:5010
LEDGER_SERVICE_URL=http://localhost:5030
```

## Startup Verification Steps

### 1. Run install.sh
```bash
cd hivematrix-archive
./install.sh
```

Expected output:
- ✓ Virtual environment created
- ✓ Dependencies installed
- ✓ Linked to Helm services.json
- ✓ Scripts are executable

### 2. Initialize Database
```bash
source pyenv/bin/activate
python init_db.py
```

Expected:
- Creates `instance/archive.conf`
- Creates all database tables
- Sets up default scheduler configuration

### 3. Test Manual Startup
```bash
source pyenv/bin/activate
python run.py
```

Expected output:
```
 * Serving Flask app 'app'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment.
 * Running on http://127.0.0.1:5012
```

Verify:
```bash
curl http://127.0.0.1:5012/health
# Expected: {"status": "ok", "service": "archive"}
```

### 4. Test Helm Startup
```bash
cd ../hivematrix-helm
./start.sh
```

Expected in output:
```
================================================================
  Detecting Additional Services
================================================================

  Found: archive

================================================================
  Starting Additional Services
================================================================

Starting archive...
  ✓ Service started successfully
  PID: XXXXX
  Port: 5012
```

Verify Archive is running:
```bash
# From Helm directory
python cli.py status
```

Expected:
```
ARCHIVE
  Status:  running
  Health:  healthy
  Port:    5012
  PID:     XXXXX
```

### 5. Test Service-to-Service Communication

From Archive, test calling Codex:
```bash
cd hivematrix-archive
source pyenv/bin/activate
python -c "
from app import app
with app.app_context():
    from app.service_client import call_service
    response = call_service('codex', '/health')
    print(f'Codex health: {response.json()}')
"
```

Expected: `Codex health: {'status': 'ok', 'service': 'codex'}`

## Troubleshooting

### Archive Not Found by Helm

**Symptom:** Archive not listed in "Detecting Additional Services"

**Causes:**
- Missing `run.py` file
- `run.py` not executable
- Directory not named `hivematrix-archive`

**Fix:**
```bash
cd hivematrix-archive
ls -la run.py  # Should exist and be readable
chmod +x run.py
```

### Archive Fails to Start

**Symptom:** "already running or failed" message

**Check logs:**
```bash
cd hivematrix-helm
tail -f logs/archive.stdout.log
tail -f logs/archive.stderr.log
```

**Common issues:**
1. **Port already in use:**
   ```bash
   lsof -i :5012
   kill <PID>
   ```

2. **Database not initialized:**
   ```bash
   cd hivematrix-archive
   source pyenv/bin/activate
   python init_db.py
   ```

3. **Missing dependencies:**
   ```bash
   cd hivematrix-archive
   ./install.sh
   ```

4. **services.json not found:**
   ```bash
   cd hivematrix-archive
   ls -la services.json  # Should be symlink to ../hivematrix-helm/services.json
   ./install.sh  # Recreate symlink
   ```

### Service-to-Service Calls Fail

**Symptom:** "Service 'codex' not found in configuration"

**Cause:** services.json not loaded

**Fix:**
```bash
cd hivematrix-archive
ls -la services.json
# If missing or broken:
ln -sf ../hivematrix-helm/services.json services.json
```

**Check configuration:**
```bash
python -c "
from app import app
print('Services configured:', list(app.config.get('SERVICES', {}).keys()))
"
```

Expected: `Services configured: ['keycloak', 'helm', 'core', 'nexus', 'codex', 'ledger', 'knowledgetree', 'brainhair', 'archive']`

### Health Check Returns 404

**Symptom:** `curl http://localhost:5012/health` returns 404

**Cause:** Middleware prefix applied

**Fix:** Archive should handle `/health` without prefix. Check if middleware is interfering.

**Workaround:**
```bash
curl http://localhost:5012/archive/health
```

### Database Connection Fails

**Symptom:** "Connection refused" or "database does not exist"

**Check database:**
```bash
psql -U archive_user -d archive_db -h localhost
```

**If fails, recreate database:**
```bash
sudo -u postgres psql
CREATE DATABASE archive_db;
CREATE USER archive_user WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE archive_db TO archive_user;
\c archive_db
GRANT ALL ON SCHEMA public TO archive_user;
\q

# Then reinitialize
cd hivematrix-archive
source pyenv/bin/activate
python init_db.py
```

## Production Deployment

For systemd deployment:

1. **Helm systemd service starts all services:**
   ```bash
   sudo systemctl start hivematrix.service
   ```

2. **Archive starts automatically** via Helm's auto-discovery

3. **Verify Archive is running:**
   ```bash
   sudo systemctl status hivematrix.service
   curl http://localhost:5012/health
   ```

4. **Check logs:**
   ```bash
   journalctl -u hivematrix.service -f
   ```

## Security Checklist

- [ ] Archive binds to 127.0.0.1 (not 0.0.0.0)
- [ ] Nexus reverse proxy configured for external access
- [ ] PostgreSQL only accepts local connections
- [ ] Database credentials secure (600 permissions on archive.conf)
- [ ] Firewall blocks direct access to port 5012
- [ ] Only ports 22 (SSH) and 443 (HTTPS) exposed externally

## Performance Verification

Test Archive under load:
```bash
# Create 100 snapshots
for i in {1..100}; do
    curl -X POST http://localhost:5030/api/bill/accept \
      -H "Content-Type: application/json" \
      -d "{\"account_number\": \"620547\", \"year\": 2025, \"month\": 10}"
    sleep 1
done

# Verify all stored
curl http://localhost:5012/api/snapshots/search | jq '.total'
```

## Success Criteria

All checks passing:
- ✅ Archive detected by Helm
- ✅ Service starts without errors
- ✅ Health endpoint returns 200 OK
- ✅ Can call Codex and Ledger services
- ✅ Database connection working
- ✅ Symlink to services.json exists
- ✅ Binds to 127.0.0.1 only
- ✅ Shows in `python cli.py status`
- ✅ Logs appear in `logs/archive.stdout.log`

---

**Last Updated:** 2025-10-24
**Maintained By:** HiveMatrix DevOps Team
