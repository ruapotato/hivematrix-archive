# Archive Installation Quick Reference

## Automated Installation

### 1. Run Install Script
```bash
cd hivematrix-archive
./install.sh
```

This will:
- ✅ Check Python 3.8+ is installed
- ✅ Create `pyenv/` virtual environment
- ✅ Install all Python dependencies from requirements.txt
- ✅ Create `instance/` directory for configuration
- ✅ Create minimal `.flaskenv` file
- ✅ Make scripts executable (scheduled_snapshots.py, test_workflow.py)
- ✅ Symlink services.json from Helm (if available)

### 2. Initialize Database
```bash
source pyenv/bin/activate
python init_db.py
```

Follow the prompts to:
- Enter PostgreSQL connection details
- Test database connection
- Create all tables
- Set up default scheduler configuration

### 3. Start Archive Service

**Development:**
```bash
source pyenv/bin/activate
flask run --port=5012
```

**Production:**
```bash
source pyenv/bin/activate
python run.py
```

### 4. Verify Installation
```bash
# Check health endpoint
curl http://localhost:5012/health

# Run workflow test
source pyenv/bin/activate
python test_workflow.py --account 620547 --year 2025 --month 10
```

## What Gets Installed

### Python Packages
- Flask 3.0.0 - Web framework
- Flask-SQLAlchemy 3.1.1 - Database ORM
- psycopg2-binary 2.9.9 - PostgreSQL driver
- python-dotenv 1.0.0 - Environment variable management
- waitress 2.1.2 - Production WSGI server
- requests 2.31.0 - HTTP client for service-to-service calls

### Directory Structure
```
hivematrix-archive/
├── pyenv/              # Virtual environment (created by install.sh)
├── instance/           # Config directory (created by install.sh)
│   └── archive.conf    # Database config (created by init_db.py)
├── .flaskenv           # Flask environment vars (created by install.sh)
├── app/                # Application code
├── models.py           # Database models
├── extensions.py       # Flask extensions
├── init_db.py          # Database setup script
├── run.py              # Production server
├── scheduled_snapshots.py  # Cron script (executable)
├── test_workflow.py    # Test script (executable)
├── systemd/            # Systemd service files
├── requirements.txt    # Python dependencies
└── install.sh          # This installation script
```

## Manual Steps After Installation

### 1. Configure Ledger Integration
Edit Ledger's `instance/ledger.conf`:
```ini
[services]
archive_url = http://localhost:5012
```

Restart Ledger:
```bash
sudo systemctl restart ledger.service
```

### 2. Set Up Scheduled Snapshots (Production)

Copy systemd files:
```bash
sudo cp systemd/archive-snapshot.service /etc/systemd/system/
sudo cp systemd/archive-snapshot.timer /etc/systemd/system/
```

Edit service file paths (if needed):
```bash
sudo nano /etc/systemd/system/archive-snapshot.service
# Update WorkingDirectory and ExecStart paths
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable archive-snapshot.timer
sudo systemctl start archive-snapshot.timer
```

Verify:
```bash
systemctl status archive-snapshot.timer
systemctl list-timers
```

### 3. Configure Reverse Proxy (Production)

See `DEPLOYMENT.md` for nginx/Apache configuration examples.

## Reinstallation

To reinstall from scratch:

```bash
# Remove virtual environment
rm -rf pyenv/

# Remove instance configuration
rm -rf instance/

# Remove .flaskenv
rm .flaskenv

# Run install again
./install.sh
python init_db.py
```

## Troubleshooting

### Python Not Found
```bash
# Install Python 3.8+
sudo apt-get update
sudo apt-get install python3 python3-venv python3-pip
```

### Permission Denied
```bash
chmod +x install.sh
./install.sh
```

### Dependencies Fail to Install
```bash
# Install system dependencies
sudo apt-get install build-essential python3-dev libpq-dev

# Try again
./install.sh
```

### PostgreSQL Not Available
```bash
# Install PostgreSQL
sudo apt-get install postgresql postgresql-contrib

# Start service
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

## Next Steps

After installation:

1. **Read Full Documentation**
   - `README.md` - Usage and API reference
   - `DEPLOYMENT.md` - Production deployment guide

2. **Configure Services**
   - Ensure Codex is running (port 5010)
   - Ensure Ledger is running (port 5011)
   - Configure service authentication tokens

3. **Test Integration**
   - Run `test_workflow.py` to verify end-to-end functionality
   - Accept a test bill in Ledger
   - Verify snapshot appears in Archive

4. **Production Setup**
   - Configure systemd services
   - Set up reverse proxy with SSL
   - Configure monitoring and alerts
   - Set up database backups

## Support

For detailed information:
- Installation: This file
- Usage: `README.md`
- Deployment: `DEPLOYMENT.md`
- Architecture: `../hivematrix-helm/ARCHITECTURE.md`
- Data Flow: `../hivematrix-ledger/DATA_FLOW.md`
