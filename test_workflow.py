#!/usr/bin/env python3
"""
Archive Workflow Test Script

Tests the complete snapshot workflow:
1. Initialize Archive database
2. Accept a test snapshot from Ledger
3. Retrieve the snapshot
4. Download CSV
5. Search functionality
6. Scheduler configuration

Usage:
  python test_workflow.py --account 620547 --year 2025 --month 10
"""

import os
import sys
import argparse
import requests
from dotenv import load_dotenv

load_dotenv('.flaskenv')

# Service URLs
ARCHIVE_URL = os.getenv('ARCHIVE_URL', 'http://localhost:5012')
LEDGER_URL = os.getenv('LEDGER_URL', 'http://localhost:5011')

# Test service token (in production, use proper authentication)
SERVICE_TOKEN = os.getenv('SERVICE_TOKEN', 'test-token')


def test_archive_health():
    """Test Archive service is running."""
    print("\n🔍 Testing Archive service health...")
    try:
        response = requests.get(f"{ARCHIVE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Archive service is running")
            return True
        else:
            print(f"❌ Archive service returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to Archive service: {e}")
        return False


def test_ledger_health():
    """Test Ledger service is running."""
    print("\n🔍 Testing Ledger service health...")
    try:
        response = requests.get(f"{LEDGER_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Ledger service is running")
            return True
        else:
            print(f"❌ Ledger service returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to Ledger service: {e}")
        return False


def accept_bill_via_ledger(account_number, year, month):
    """Accept a bill via Ledger, which sends it to Archive."""
    print(f"\n📤 Accepting bill for {account_number} ({year}-{month:02d}) via Ledger...")

    payload = {
        'account_number': account_number,
        'year': year,
        'month': month,
        'notes': 'Test snapshot from workflow test script'
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {SERVICE_TOKEN}'
    }

    try:
        response = requests.post(
            f"{LEDGER_URL}/api/bill/accept",
            json=payload,
            headers=headers,
            timeout=30
        )

        if response.status_code == 201:
            data = response.json()
            print(f"✅ Bill accepted and archived: {data.get('invoice_number')}")
            return data.get('invoice_number')
        elif response.status_code == 409:
            data = response.json()
            print(f"⚠️  Bill already archived")
            # Extract invoice number from error message or generate it
            invoice_number = f"{account_number}-{year}{month:02d}"
            return invoice_number
        else:
            print(f"❌ Failed to accept bill: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error accepting bill: {e}")
        return None


def retrieve_snapshot(invoice_number):
    """Retrieve a snapshot from Archive."""
    print(f"\n📥 Retrieving snapshot {invoice_number}...")

    headers = {'Authorization': f'Bearer {SERVICE_TOKEN}'}

    try:
        response = requests.get(
            f"{ARCHIVE_URL}/api/snapshot/{invoice_number}",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Snapshot retrieved:")
            print(f"   Company: {data.get('company_name')}")
            print(f"   Total: ${data.get('total_amount')}")
            print(f"   Users: {data.get('user_count')}, Assets: {data.get('asset_count')}")
            print(f"   Archived: {data.get('archived_at')}")
            return data
        elif response.status_code == 404:
            print(f"❌ Snapshot not found")
            return None
        else:
            print(f"❌ Failed to retrieve snapshot: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error retrieving snapshot: {e}")
        return None


def download_csv(invoice_number):
    """Download CSV invoice."""
    print(f"\n📄 Downloading CSV for {invoice_number}...")

    headers = {'Authorization': f'Bearer {SERVICE_TOKEN}'}

    try:
        response = requests.get(
            f"{ARCHIVE_URL}/api/snapshot/{invoice_number}/csv",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            csv_content = response.text
            print(f"✅ CSV downloaded ({len(csv_content)} bytes)")
            print(f"   First line: {csv_content.split(chr(10))[0]}")
            return csv_content
        else:
            print(f"❌ Failed to download CSV: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error downloading CSV: {e}")
        return None


def test_search(account_number):
    """Test search functionality."""
    print(f"\n🔍 Searching for snapshots for account {account_number}...")

    headers = {'Authorization': f'Bearer {SERVICE_TOKEN}'}

    try:
        response = requests.get(
            f"{ARCHIVE_URL}/api/snapshots/company/{account_number}",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            count = data.get('total_snapshots', 0)
            print(f"✅ Found {count} snapshots for this company")
            if count > 0:
                print(f"   Latest: {data['snapshots'][0]['invoice_number']}")
            return data
        else:
            print(f"❌ Search failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error searching: {e}")
        return None


def test_scheduler_config():
    """Test scheduler configuration endpoint."""
    print(f"\n⚙️  Checking scheduler configuration...")

    headers = {'Authorization': f'Bearer {SERVICE_TOKEN}'}

    try:
        response = requests.get(
            f"{ARCHIVE_URL}/api/scheduler/config",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            config = data.get('config')
            if config:
                print(f"✅ Scheduler configured:")
                print(f"   Enabled: {config.get('enabled')}")
                print(f"   Schedule: Day {config.get('day_of_month')} at {config.get('hour')}:00")
                print(f"   Last run: {config.get('last_run_at') or 'Never'}")
                return config
            else:
                print(f"⚠️  No scheduler configuration found")
                return None
        else:
            print(f"❌ Failed to get scheduler config: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting scheduler config: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Test Archive workflow')
    parser.add_argument('--account', type=str, default='620547', help='Account number to test')
    parser.add_argument('--year', type=int, default=2025, help='Billing year')
    parser.add_argument('--month', type=int, default=10, help='Billing month')
    parser.add_argument('--skip-health', action='store_true', help='Skip health checks')
    parser.add_argument('--skip-create', action='store_true', help='Skip snapshot creation (test retrieval only)')

    args = parser.parse_args()

    print("=" * 80)
    print("ARCHIVE WORKFLOW TEST")
    print("=" * 80)
    print(f"\nTarget: Account {args.account}, Period {args.year}-{args.month:02d}")
    print(f"Archive URL: {ARCHIVE_URL}")
    print(f"Ledger URL: {LEDGER_URL}")

    # Health checks
    if not args.skip_health:
        archive_ok = test_archive_health()
        ledger_ok = test_ledger_health()

        if not archive_ok or not ledger_ok:
            print("\n❌ Services not ready. Start services first:")
            if not archive_ok:
                print("   cd hivematrix-archive && flask run --port=5012")
            if not ledger_ok:
                print("   cd hivematrix-ledger && flask run --port=5011")
            sys.exit(1)

    # Create snapshot via Ledger
    invoice_number = None
    if not args.skip_create:
        invoice_number = accept_bill_via_ledger(args.account, args.year, args.month)
        if not invoice_number:
            print("\n❌ Failed to create snapshot. Check Ledger logs.")
            sys.exit(1)
    else:
        invoice_number = f"{args.account}-{args.year}{args.month:02d}"

    # Retrieve snapshot
    snapshot = retrieve_snapshot(invoice_number)
    if not snapshot:
        print("\n❌ Failed to retrieve snapshot. Check Archive logs.")
        sys.exit(1)

    # Download CSV
    csv = download_csv(invoice_number)
    if not csv:
        print("\n⚠️  Failed to download CSV")

    # Test search
    search_results = test_search(args.account)

    # Test scheduler config
    scheduler = test_scheduler_config()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✅ Snapshot created/retrieved: {invoice_number}")
    print(f"✅ CSV download: {'Success' if csv else 'Failed'}")
    print(f"✅ Search: {'Success' if search_results else 'Failed'}")
    print(f"✅ Scheduler config: {'Success' if scheduler else 'Failed'}")
    print("\n🎉 Archive workflow test completed!")
    print("=" * 80)


if __name__ == '__main__':
    main()
