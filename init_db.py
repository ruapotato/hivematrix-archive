#!/usr/bin/env python3
"""
Archive Database Initialization Script
"""

import os
import sys
import configparser
import argparse
from getpass import getpass
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv

load_dotenv('.flaskenv')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from extensions import db
from models import BillingSnapshot, SnapshotLineItem, ScheduledSnapshot, SnapshotJob


def get_db_credentials(args=None):
    """Prompts for PostgreSQL connection details or uses command-line args."""
    if args and args.headless:
        # Headless mode - use defaults or command-line args
        return {
            'host': args.host or 'localhost',
            'port': args.port or '5432',
            'dbname': args.database or 'archive_db',
            'user': args.user or 'archive_user',
            'password': args.password or ''
        }
    else:
        # Interactive mode
        print("\n--- PostgreSQL Database Configuration ---")

        host = input("Host [localhost]: ") or "localhost"
        port = input("Port [5432]: ") or "5432"
        dbname = input("Database Name [archive_db]: ") or "archive_db"
        user = input("User [archive_user]: ") or "archive_user"
        password = getpass("Password: ")

        return {
            'host': host,
            'port': port,
            'dbname': dbname,
            'user': user,
            'password': password
        }


def test_db_connection(creds):
    """Tests the database connection."""
    from urllib.parse import quote_plus

    escaped_password = quote_plus(creds['password'])
    conn_string = f"postgresql://{creds['user']}:{escaped_password}@{creds['host']}:{creds['port']}/{creds['dbname']}"

    try:
        engine = create_engine(conn_string)
        with engine.connect() as connection:
            print("\n✓ Database connection successful!")
            return conn_string, True
    except OperationalError as e:
        print(f"\n✗ Connection failed: {e}", file=sys.stderr)
        return None, False


def init_db(args=None):
    """Initialize the Archive database."""
    print("\n" + "="*80)
    print("ARCHIVE DATABASE INITIALIZATION")
    print("="*80)

    instance_path = app.instance_path
    config_path = os.path.join(instance_path, 'archive.conf')

    config = configparser.RawConfigParser()

    # Database configuration
    conn_string = None
    if args and args.headless:
        # Headless mode - try once, fail if doesn't work
        creds = get_db_credentials(args)
        conn_string, success = test_db_connection(creds)
        if success:
            if not config.has_section('database'):
                config.add_section('database')
            config.set('database', 'connection_string', conn_string)
        else:
            sys.exit(1)  # Exit with error in headless mode
    else:
        # Interactive mode - retry loop
        while True:
            creds = get_db_credentials(args)
            conn_string, success = test_db_connection(creds)
            if success:
                if not config.has_section('database'):
                    config.add_section('database')
                config.set('database', 'connection_string', conn_string)
                break
            else:
                retry = input("\nWould you like to try again? (y/n): ").lower()
                if retry != 'y':
                    sys.exit("Database configuration aborted.")

    # Save configuration
    with open(config_path, 'w') as configfile:
        config.write(configfile)

    print(f"\n✓ Configuration saved to: {config_path}")

    # Initialize database schema
    with app.app_context():
        print("\nInitializing database schema...")
        db.create_all()
        print("✓ Database schema initialized successfully!")

        # Create default scheduled snapshot configuration
        existing_config = ScheduledSnapshot.query.first()
        if not existing_config:
            from datetime import datetime
            default_config = ScheduledSnapshot(
                enabled=True,
                day_of_month=1,
                hour=2,
                snapshot_previous_month=True,
                snapshot_all_companies=True,
                created_at=datetime.now().isoformat()
            )
            db.session.add(default_config)
            db.session.commit()
            print("✓ Created default scheduler configuration (1st of month at 2am)")

    print("\n" + "="*80)
    print(" 🎉 Archive Initialization Complete!")
    print("="*80)
    print("\nArchive stores immutable billing snapshots for historical record-keeping.")
    print("\nNext steps:")
    print("  1. Start the Archive service:")
    print("     → flask run --port=5012         # Development")
    print("     → python run.py                 # Production (Waitress)")
    print("\n  2. Configure Ledger to send snapshots to Archive")
    print("\n  3. Set up scheduled snapshots (automated on 1st of each month)")
    print("="*80)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Initialize Archive database',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--headless', action='store_true',
                       help='Run in non-interactive mode (for automated installs)')
    parser.add_argument('--host', default='localhost',
                       help='Database host (default: localhost)')
    parser.add_argument('--port', default='5432',
                       help='Database port (default: 5432)')
    parser.add_argument('--database', default='archive_db',
                       help='Database name (default: archive_db)')
    parser.add_argument('--user', default='archive_user',
                       help='Database user (default: archive_user)')
    parser.add_argument('--password', default='',
                       help='Database password (required for headless mode)')

    args = parser.parse_args()

    if args.headless and not args.password:
        print("Error: --password is required when using --headless mode", file=sys.stderr)
        sys.exit(1)

    init_db(args)
