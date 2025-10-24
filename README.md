# Archive Service

**Immutable billing snapshot storage for historical record-keeping**

Archive stores finalized billing snapshots sent from Ledger. It provides:
- Permanent storage of accepted bills
- Historical bill lookup and search
- CSV invoice downloads
- Scheduled automated snapshot creation
- Audit trail of billing history

## Quick Start

```bash
# 1. Install PostgreSQL and create database
sudo apt-get install postgresql postgresql-contrib
sudo -u postgres psql -c "CREATE DATABASE archive_db;"
sudo -u postgres psql -c "CREATE USER archive_user WITH PASSWORD 'Integotec@123';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE archive_db TO archive_user;"

# 2. Grant schema permissions (PostgreSQL 15+ REQUIRED)
sudo -u postgres psql -d archive_db -c "GRANT ALL ON SCHEMA public TO archive_user;"
sudo -u postgres psql -d archive_db -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO archive_user;"
sudo -u postgres psql -d archive_db -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO archive_user;"

# 3. Run installation script
./install.sh

# 4. Initialize database schema
source pyenv/bin/activate
python init_db.py
# Press Enter for all prompts to use defaults (localhost, port 5432, etc.)

# 5. Start service
python run.py
# Or for development: flask run --port=5012

# 6. Verify
curl http://localhost:5012/health
```

## Architecture

```
Ledger → Archive ← Scheduler
  ↓         ↓
 API    Database
```

- **Ledger** sends finalized bills via "Accept Bill" button
- **Scheduler** automatically creates snapshots on 1st of month
- **Archive** stores immutable snapshots with full billing data
- **Search API** enables historical bill retrieval

## Setup

### 0. Prerequisites

**Install PostgreSQL:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 1. Create Database and User

**Switch to postgres user and create database:**
```bash
sudo -u postgres psql
```

**Run these SQL commands:**
```sql
-- Create database
CREATE DATABASE archive_db;

-- Create user with password
CREATE USER archive_user WITH ENCRYPTED PASSWORD 'Integotec@123';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE archive_db TO archive_user;

-- Exit psql
\q
```

**IMPORTANT: Grant schema permissions** (PostgreSQL 15+)
```bash
# These commands MUST be run to allow archive_user to create tables
sudo -u postgres psql -d archive_db -c "GRANT ALL ON SCHEMA public TO archive_user;"
sudo -u postgres psql -d archive_db -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO archive_user;"
sudo -u postgres psql -d archive_db -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO archive_user;"

# Optional: Set default privileges for future tables
sudo -u postgres psql -d archive_db -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO archive_user;"
sudo -u postgres psql -d archive_db -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO archive_user;"
```

**Test the connection:**
```bash
psql -U archive_user -d archive_db -h localhost
# Enter password when prompted
# Type \q to exit
```

### 2. Run Installation Script

```bash
./install.sh
```

This will:
- Check Python 3.8+ is installed
- Create virtual environment in `pyenv/`
- Install all Python dependencies
- Create `instance/` directory
- Create minimal `.flaskenv` file

### 3. Initialize Database Schema

```bash
source pyenv/bin/activate
python init_db.py
```

This will:
- Prompt for PostgreSQL connection details (database, user, password, host, port)
- Test the database connection
- Create all required tables
- Set up default scheduler configuration (1st of month at 2am)
- Save configuration to `instance/archive.conf`

### 4. Start the Service

**Development:**
```bash
source pyenv/bin/activate
flask run --port=5012
```

**Production (Waitress):**
```bash
source pyenv/bin/activate
python run.py
```

**Verify service is running:**
```bash
curl http://localhost:5012/health
# Expected: {"status": "ok", "service": "archive"}
```

### 5. Configure Scheduled Snapshots (Production)

Copy systemd service files:
```bash
sudo cp systemd/archive-snapshot.service /etc/systemd/system/
sudo cp systemd/archive-snapshot.timer /etc/systemd/system/
```

Update paths in service file if needed:
```bash
sudo nano /etc/systemd/system/archive-snapshot.service
# Update WorkingDirectory and ExecStart paths
```

Enable and start the timer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable archive-snapshot.timer
sudo systemctl start archive-snapshot.timer
```

Check timer status:
```bash
sudo systemctl status archive-snapshot.timer
sudo systemctl list-timers
```

### 6. Configure Ledger Integration

In Ledger's service configuration, ensure Archive is registered:
```bash
# Edit Ledger's instance/ledger.conf
nano /path/to/hivematrix-ledger/instance/ledger.conf

# Add or update:
[services]
archive_url = http://localhost:5012
```

Restart Ledger service:
```bash
# If using systemd
sudo systemctl restart ledger.service

# Or if running manually
cd /path/to/hivematrix-ledger
source pyenv/bin/activate
python run.py
```

## API Endpoints

### Snapshot Management

**Create Snapshot** (from Ledger)
```bash
POST /api/snapshot
Content-Type: application/json

{
  "company_account_number": "620547",
  "billing_year": 2025,
  "billing_month": 10,
  "invoice_number": "620547-202510",
  "total_amount": 2450.00,
  "billing_data_json": {...},
  "invoice_csv": "...",
  "line_items": [...]
}

Response: 201 Created
{
  "message": "Snapshot created successfully",
  "invoice_number": "620547-202510"
}
```

**Get Snapshot**
```bash
GET /api/snapshot/{invoice_number}

Response: 200 OK
{
  "invoice_number": "620547-202510",
  "company_name": "Company Name",
  "billing_year": 2025,
  "billing_month": 10,
  "total_amount": 2450.00,
  "billing_data": {...}
}
```

**Download CSV Invoice**
```bash
GET /api/snapshot/{invoice_number}/csv

Response: CSV file download
```

### Search

**Search Snapshots**
```bash
GET /api/snapshots/search?account_number=620547&year=2025&month=10

Response: 200 OK
{
  "total": 1,
  "results": [...]
}
```

**Get Company Snapshots**
```bash
GET /api/snapshots/company/{account_number}

Response: 200 OK
{
  "company_account_number": "620547",
  "total_snapshots": 12,
  "snapshots": [...]
}
```

### Scheduler

**Get Scheduler Configuration**
```bash
GET /api/scheduler/config

Response: 200 OK
{
  "config": {
    "enabled": true,
    "day_of_month": 1,
    "hour": 2,
    "snapshot_previous_month": true,
    "snapshot_all_companies": true,
    "last_run_at": "2025-10-01T02:00:00",
    "last_run_status": "success",
    "last_run_count": 45
  }
}
```

**Update Scheduler Configuration**
```bash
POST /api/scheduler/config
Content-Type: application/json

{
  "enabled": true,
  "day_of_month": 1,
  "hour": 2,
  "snapshot_previous_month": true,
  "snapshot_all_companies": true
}
```

**List Snapshot Jobs**
```bash
GET /api/scheduler/jobs

Response: 200 OK
{
  "jobs": [
    {
      "id": "uuid",
      "job_type": "scheduled",
      "status": "completed",
      "target_year": 2025,
      "target_month": 9,
      "total_companies": 45,
      "completed_companies": 45,
      "success_count": 45,
      "failed_count": 0
    }
  ]
}
```

## Manual Snapshot Creation

You can manually trigger snapshot creation for specific periods or companies:

**All companies for October 2025:**
```bash
./scheduled_snapshots.py --year 2025 --month 10 --all
```

**Specific companies:**
```bash
./scheduled_snapshots.py --year 2025 --month 10 --accounts 620547,183729
```

**Dry run (show what would be done):**
```bash
./scheduled_snapshots.py --year 2025 --month 10 --all --dry-run
```

## Workflow

### Accepting a Bill in Ledger

1. User views billing details for a company/period in Ledger
2. User clicks "Accept Bill & Archive" button
3. Ledger sends complete billing snapshot to Archive
4. Archive stores immutable snapshot with:
   - Full billing breakdown
   - CSV invoice
   - Line items
   - Metadata (who accepted it, when, notes)
5. Button changes to "✓ Already Archived"

### Automated Monthly Snapshots

1. Timer triggers on 1st of month at 2am
2. Scheduler queries Codex for all companies
3. For each company:
   - Scheduler calls Ledger's `/api/bill/accept` endpoint
   - Ledger calculates billing and sends to Archive
   - Archive stores snapshot
4. Job status tracked in database
5. Summary available via `/api/scheduler/jobs`

### Viewing Historical Bills

**Via Web UI:**
- Navigate to Archive homepage
- Use search filters (company, year, month)
- Click "View JSON" or "Download CSV"

**Via API:**
- Search: `GET /api/snapshots/search?account_number=620547`
- Get specific: `GET /api/snapshot/620547-202510`
- Download CSV: `GET /api/snapshot/620547-202510/csv`

## Database Schema

**billing_snapshots** - Immutable billing records
- invoice_number (unique)
- company_account_number
- billing_year/month
- total amounts (users, assets, backup, tickets, line items)
- billing_data_json (complete breakdown)
- invoice_csv (downloadable CSV)
- archived_at timestamp
- created_by, notes

**snapshot_line_items** - Denormalized line items for searching
- snapshot_id (foreign key)
- line_type (user/asset/backup/ticket/custom)
- item_name, description, quantity, rate, amount

**scheduled_snapshots** - Scheduler configuration
- enabled, day_of_month, hour
- snapshot_previous_month, snapshot_all_companies
- last_run_at, last_run_status, last_run_count

**snapshot_jobs** - Job tracking
- job_id, job_type, status
- target_year/month
- progress tracking
- output/errors

## Data Retention

Snapshots are **immutable** and **permanent**. Archive does not provide:
- Snapshot deletion (by design - audit trail)
- Snapshot modification (immutable records)
- Automatic cleanup (keep all history)

If you need to remove snapshots, you must manually delete from the database (with proper authorization and audit logging).

## Security

- All endpoints require authentication (service tokens or user tokens)
- Admin endpoints (`/api/scheduler/config`) require admin role
- Service-to-service calls use shared secrets
- Database credentials stored in instance/archive.conf

## Monitoring

**Check scheduler status:**
```bash
curl http://localhost:5012/api/scheduler/config
```

**View recent jobs:**
```bash
curl http://localhost:5012/api/scheduler/jobs
```

**Check systemd timer:**
```bash
systemctl status archive-snapshot.timer
journalctl -u archive-snapshot.service -n 50
```

## Troubleshooting

**Database initialization fails with "permission denied for schema public":**

This is a common PostgreSQL 15+ issue. Fix with:
```bash
# Run these commands to grant schema permissions
sudo -u postgres psql -d archive_db -c "GRANT ALL ON SCHEMA public TO archive_user;"
sudo -u postgres psql -d archive_db -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO archive_user;"
sudo -u postgres psql -d archive_db -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO archive_user;"

# Then re-run init_db.py
source pyenv/bin/activate
python init_db.py
```

**Table "billing_snapshots" does not exist:**

Database schema not initialized. Run:
```bash
source pyenv/bin/activate
python init_db.py
```

**Scheduler not running:**
- Check timer: `systemctl status archive-snapshot.timer`
- Check service logs: `journalctl -u archive-snapshot.service`
- Verify configuration: `GET /api/scheduler/config`
- Test manually: `./scheduled_snapshots.py --year 2025 --month 10 --all`

**Snapshot creation fails:**
- Check Ledger service is running
- Verify service-to-service authentication
- Check Codex connectivity (Ledger needs Codex data)
- Review job details: `GET /api/scheduler/jobs/{job_id}`

**Database connection errors:**
- Check PostgreSQL is running: `sudo systemctl status postgresql`
- Verify connection string in `instance/archive.conf`
- Test connection manually: `psql -U archive_user -d archive_db -h localhost`
- Check database exists: `sudo -u postgres psql -l | grep archive_db`

## Integration with Other Services

**Codex** → Archive (indirect)
- Archive does not directly call Codex
- Codex data flows through Ledger

**Ledger** → Archive
- Manual: "Accept Bill" button sends snapshot
- Automated: Scheduler triggers Ledger to send snapshots

**Archive** → Ledger (none)
- Archive is write-only from Ledger's perspective
- Archive does not call Ledger

## Development

**Run tests:**
```bash
python -m pytest tests/
```

**Rebuild database (dev only):**
```bash
python init_db.py --force-rebuild
```

**Check snapshot creation manually:**
```bash
curl -X POST http://localhost:5012/api/snapshot \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d @test_snapshot.json
```

## Production Deployment

1. Set up PostgreSQL database
2. Run `init_db.py` for initial setup
3. Configure systemd service and timer
4. Set up reverse proxy (nginx/Apache) for HTTPS
5. Configure service discovery in Ledger
6. Test manual snapshot creation
7. Enable and start timer
8. Monitor first scheduled run

## Support

For issues or questions, check:
- Archive logs: `journalctl -u archive.service`
- Scheduler logs: `journalctl -u archive-snapshot.service`
- Database connectivity: `psql -U archive_user -d archive_db`
- API health: `curl http://localhost:5012/health`
