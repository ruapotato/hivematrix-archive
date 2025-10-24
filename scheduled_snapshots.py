#!/usr/bin/env python3
"""
Scheduled Snapshot Creation Script

Run this script via cron to automatically create billing snapshots.
Default: 1st of each month at 2am for previous month's billing.

Usage:
  ./scheduled_snapshots.py                    # Use configured schedule
  ./scheduled_snapshots.py --year 2025 --month 10  # Specific period
  ./scheduled_snapshots.py --all              # All companies
  ./scheduled_snapshots.py --accounts 620547,183729  # Specific companies

Cron example (1st of month at 2am):
  0 2 1 * * cd /path/to/hivematrix-archive && /usr/bin/python3 scheduled_snapshots.py
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv('.flaskenv')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from app.scheduler import run_scheduled_snapshots
from extensions import db
from models import ScheduledSnapshot, SnapshotJob
import json


def main():
    parser = argparse.ArgumentParser(description='Create scheduled billing snapshots')
    parser.add_argument('--year', type=int, help='Billing year (default: auto-detect)')
    parser.add_argument('--month', type=int, help='Billing month (default: auto-detect)')
    parser.add_argument('--all', action='store_true', help='Snapshot all companies')
    parser.add_argument('--accounts', type=str, help='Comma-separated account numbers')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')

    args = parser.parse_args()

    with app.app_context():
        # Get scheduler configuration
        config = ScheduledSnapshot.query.first()

        if not config:
            print("❌ No scheduler configuration found. Run init_db.py first.")
            sys.exit(1)

        if not config.enabled and not (args.year and args.month):
            print("⚠️  Scheduler is disabled. Use --year and --month to run manually.")
            sys.exit(0)

        # Determine target period
        if args.year and args.month:
            target_year = args.year
            target_month = args.month
            print(f"📅 Manual snapshot for {target_year}-{target_month:02d}")
        else:
            # Auto-detect based on configuration
            now = datetime.now()

            if config.snapshot_previous_month:
                # Snapshot previous month's billing
                if now.month == 1:
                    target_year = now.year - 1
                    target_month = 12
                else:
                    target_year = now.year
                    target_month = now.month - 1
            else:
                # Snapshot current month
                target_year = now.year
                target_month = now.month

            print(f"📅 Scheduled snapshot for {target_year}-{target_month:02d}")

        # Determine target companies
        if args.accounts:
            account_numbers = [acc.strip() for acc in args.accounts.split(',')]
            print(f"🎯 Target companies: {', '.join(account_numbers)}")
        elif args.all or config.snapshot_all_companies:
            account_numbers = None
            print("🎯 Target: All companies")
        else:
            print("❌ No companies specified. Use --all or --accounts")
            sys.exit(1)

        if args.dry_run:
            print("\n✓ Dry run complete - no snapshots created")
            sys.exit(0)

        # Run snapshot creation
        print(f"\n🚀 Starting snapshot job...")

        job_id, success, message = run_scheduled_snapshots(
            target_year,
            target_month,
            account_numbers
        )

        if success:
            print(f"✅ {message}")
            print(f"📊 Job ID: {job_id}")

            # Update scheduler last run
            config.last_run_at = datetime.now().isoformat()
            config.last_run_status = 'success'
            db.session.commit()

            sys.exit(0)
        else:
            print(f"❌ {message}")
            print(f"📊 Job ID: {job_id}")

            config.last_run_at = datetime.now().isoformat()
            config.last_run_status = 'failed'
            db.session.commit()

            sys.exit(1)


if __name__ == '__main__':
    main()
