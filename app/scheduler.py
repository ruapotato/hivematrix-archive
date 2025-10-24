"""
Snapshot Scheduler

Handles automated creation of billing snapshots from Ledger.
"""

from app.service_client import call_service
from extensions import db
from models import SnapshotJob, ScheduledSnapshot
from datetime import datetime
import json
import uuid


def run_scheduled_snapshots(year, month, account_numbers=None):
    """
    Create snapshots for specified period and companies.

    Args:
        year: Billing year
        month: Billing month
        account_numbers: List of account numbers, or None for all

    Returns:
        tuple: (job_id, success, message)
    """
    # Create job to track progress
    job_id = str(uuid.uuid4())
    job = SnapshotJob(
        id=job_id,
        job_type='scheduled',
        status='running',
        target_year=year,
        target_month=month,
        target_account_numbers=json.dumps(account_numbers) if account_numbers else None,
        started_at=datetime.now().isoformat(),
        triggered_by='scheduler'
    )
    db.session.add(job)
    db.session.commit()

    try:
        # Get list of companies from Codex
        if account_numbers:
            # Specific companies
            companies = []
            for acc in account_numbers:
                response = call_service('codex', f'/api/company/{acc}')
                if response.status_code == 200:
                    companies.append(response.json())
        else:
            # All companies
            response = call_service('codex', '/api/companies')
            if response.status_code != 200:
                raise Exception(f"Failed to fetch companies from Codex: {response.status_code}")
            companies = response.json()

        if not companies:
            job.status = 'completed'
            job.completed_at = datetime.now().isoformat()
            job.total_companies = 0
            job.completed_companies = 0
            job.success = True
            db.session.commit()
            return job_id, True, "No companies to snapshot"

        job.total_companies = len(companies)
        db.session.commit()

        # Create snapshots via Ledger
        success_count = 0
        failed_count = 0
        errors = []

        for company in companies:
            account_number = company.get('account_number')
            if not account_number:
                continue

            try:
                # Call Ledger to send snapshot to Archive
                payload = {
                    'account_number': account_number,
                    'year': year,
                    'month': month,
                    'notes': f'Automated snapshot via scheduler (job {job_id})'
                }

                response = call_service('ledger', '/api/bill/accept', method='POST', json=payload)

                if response.status_code == 201:
                    success_count += 1
                elif response.status_code == 409:
                    # Already archived
                    success_count += 1
                else:
                    failed_count += 1
                    errors.append(f"{account_number}: {response.text}")

            except Exception as e:
                failed_count += 1
                errors.append(f"{account_number}: {str(e)}")

            # Update progress
            job.completed_companies = success_count + failed_count
            db.session.commit()

        # Complete job
        job.status = 'completed'
        job.completed_at = datetime.now().isoformat()
        job.success = (failed_count == 0)
        job.output = json.dumps({
            'success_count': success_count,
            'failed_count': failed_count,
            'errors': errors
        })
        db.session.commit()

        # Update scheduler config
        config = ScheduledSnapshot.query.first()
        if config:
            config.last_run_count = success_count

        if failed_count > 0:
            message = f"Completed with {success_count} successes, {failed_count} failures"
            return job_id, False, message
        else:
            message = f"Successfully created {success_count} snapshots"
            return job_id, True, message

    except Exception as e:
        # Job failed
        job.status = 'failed'
        job.completed_at = datetime.now().isoformat()
        job.success = False
        job.error = str(e)
        db.session.commit()

        return job_id, False, f"Scheduler error: {str(e)}"


def get_job_status(job_id):
    """
    Get status of a snapshot job.

    Returns:
        dict: Job status information
    """
    job = SnapshotJob.query.get(job_id)

    if not job:
        return None

    output = json.loads(job.output) if job.output else {}

    return {
        'id': job.id,
        'job_type': job.job_type,
        'status': job.status,
        'target_year': job.target_year,
        'target_month': job.target_month,
        'total_companies': job.total_companies,
        'completed_companies': job.completed_companies,
        'started_at': job.started_at,
        'completed_at': job.completed_at,
        'success': job.success,
        'triggered_by': job.triggered_by,
        'output': output,
        'error': job.error
    }
