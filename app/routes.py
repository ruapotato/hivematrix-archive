"""
Archive Service Routes

This service provides:
1. API to accept billing snapshots from Ledger
2. Historical bill search and retrieval
3. Scheduled snapshot creation (1st of month)
4. UI for viewing archived bills
"""

from flask import render_template, g, jsonify, request, Response
from app import app
from app.auth import token_required, admin_required
from app.service_client import call_service
from extensions import db
from models import BillingSnapshot, SnapshotLineItem, SnapshotJob, ScheduledSnapshot
from datetime import datetime
import json
import uuid


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'service': 'archive'}), 200


@app.route('/')
@token_required
def index():
    """Archive dashboard - shows recent snapshots and search."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    # Get recent snapshots
    recent = BillingSnapshot.query.order_by(BillingSnapshot.archived_at.desc()).limit(20).all()

    # Get summary stats
    total_snapshots = BillingSnapshot.query.count()
    total_companies = db.session.query(BillingSnapshot.company_account_number).distinct().count()

    return render_template('index.html',
        user=g.user,
        recent_snapshots=recent,
        total_snapshots=total_snapshots,
        total_companies=total_companies
    )


# ===== SNAPSHOT API ENDPOINTS =====

@app.route('/api/snapshot', methods=['POST'])
@token_required
def create_snapshot():
    """
    Accept a billing snapshot from Ledger (or other service).

    Expected JSON payload:
    {
        "company_account_number": "620547",
        "company_name": "Company Name",
        "billing_year": 2025,
        "billing_month": 10,
        "invoice_number": "620547-202510",
        "invoice_date": "2025-10-31",
        "due_date": "2025-11-30",
        "billing_plan": "MSP Platinum",
        "contract_term": "1-Year",
        "support_level": "All Inclusive",
        "total_amount": 2450.00,
        "total_user_charges": 1700.00,
        "total_asset_charges": 375.00,
        "total_backup_charges": 75.00,
        "total_ticket_charges": 300.00,
        "total_line_item_charges": 0.00,
        "user_count": 17,
        "asset_count": 26,
        "billable_hours": 3.0,
        "billing_data_json": {...},  // Complete billing breakdown
        "invoice_csv": "..."  // CSV content
        "line_items": [  // Optional - will be parsed from billing_data_json if not provided
            {
                "line_type": "user",
                "item_name": "John Doe",
                "description": "User: John Doe (Paid)",
                "quantity": 1.0,
                "rate": 100.00,
                "amount": 100.00
            },
            ...
        ],
        "created_by": "admin@company.com",  // Optional
        "notes": "Manually accepted bill"  // Optional
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    required = ['company_account_number', 'billing_year', 'billing_month',
                'invoice_number', 'total_amount', 'billing_data_json', 'invoice_csv']

    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    # Check if snapshot already exists
    existing = BillingSnapshot.query.filter_by(invoice_number=data['invoice_number']).first()
    if existing:
        return jsonify({'error': f'Snapshot already exists for invoice {data["invoice_number"]}'}), 409

    # Create snapshot
    snapshot = BillingSnapshot(
        company_account_number=data['company_account_number'],
        company_name=data.get('company_name', 'Unknown'),
        invoice_number=data['invoice_number'],
        billing_year=data['billing_year'],
        billing_month=data['billing_month'],
        invoice_date=data.get('invoice_date'),
        due_date=data.get('due_date'),
        archived_at=datetime.now().isoformat(),
        billing_plan=data.get('billing_plan'),
        contract_term=data.get('contract_term'),
        support_level=data.get('support_level'),
        total_amount=float(data['total_amount']),
        total_user_charges=float(data.get('total_user_charges', 0)),
        total_asset_charges=float(data.get('total_asset_charges', 0)),
        total_backup_charges=float(data.get('total_backup_charges', 0)),
        total_ticket_charges=float(data.get('total_ticket_charges', 0)),
        total_line_item_charges=float(data.get('total_line_item_charges', 0)),
        user_count=data.get('user_count', 0),
        asset_count=data.get('asset_count', 0),
        billable_hours=float(data.get('billable_hours', 0)),
        billing_data_json=json.dumps(data['billing_data_json']),
        invoice_csv=data['invoice_csv'],
        created_by=data.get('created_by', g.user.get('email') if hasattr(g, 'user') else 'api'),
        notes=data.get('notes')
    )

    db.session.add(snapshot)
    db.session.flush()  # Get snapshot ID

    # Create line items if provided
    if 'line_items' in data:
        for item in data['line_items']:
            line_item = SnapshotLineItem(
                snapshot_id=snapshot.id,
                line_type=item.get('line_type', 'custom'),
                item_name=item['item_name'],
                description=item.get('description'),
                quantity=float(item.get('quantity', 1.0)),
                rate=float(item['rate']),
                amount=float(item['amount'])
            )
            db.session.add(line_item)

    try:
        db.session.commit()
        return jsonify({
            'message': 'Snapshot created successfully',
            'snapshot_id': snapshot.id,
            'invoice_number': snapshot.invoice_number
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/snapshot/<invoice_number>', methods=['GET'])
@token_required
def get_snapshot(invoice_number):
    """Retrieve a specific snapshot by invoice number."""
    snapshot = BillingSnapshot.query.filter_by(invoice_number=invoice_number).first()

    if not snapshot:
        return jsonify({'error': 'Snapshot not found'}), 404

    # Return snapshot data
    data = {
        'id': snapshot.id,
        'company_account_number': snapshot.company_account_number,
        'company_name': snapshot.company_name,
        'invoice_number': snapshot.invoice_number,
        'billing_year': snapshot.billing_year,
        'billing_month': snapshot.billing_month,
        'invoice_date': snapshot.invoice_date,
        'due_date': snapshot.due_date,
        'archived_at': snapshot.archived_at,
        'billing_plan': snapshot.billing_plan,
        'contract_term': snapshot.contract_term,
        'support_level': snapshot.support_level,
        'total_amount': float(snapshot.total_amount),
        'total_user_charges': float(snapshot.total_user_charges),
        'total_asset_charges': float(snapshot.total_asset_charges),
        'total_backup_charges': float(snapshot.total_backup_charges),
        'total_ticket_charges': float(snapshot.total_ticket_charges),
        'total_line_item_charges': float(snapshot.total_line_item_charges),
        'user_count': snapshot.user_count,
        'asset_count': snapshot.asset_count,
        'billable_hours': float(snapshot.billable_hours),
        'billing_data': json.loads(snapshot.billing_data_json),
        'created_by': snapshot.created_by,
        'notes': snapshot.notes
    }

    return jsonify(data), 200


@app.route('/api/snapshot/<invoice_number>/csv', methods=['GET'])
@token_required
def download_snapshot_csv(invoice_number):
    """Download the CSV invoice for a snapshot."""
    snapshot = BillingSnapshot.query.filter_by(invoice_number=invoice_number).first()

    if not snapshot:
        return jsonify({'error': 'Snapshot not found'}), 404

    # Sanitize company name for filename
    safe_name = "".join(
        c for c in snapshot.company_name if c.isalnum() or c in (' ', '_', '-')
    ).strip().replace(' ', '_')

    filename = f"{safe_name}_{snapshot.billing_year}-{snapshot.billing_month:02d}.csv"

    return Response(
        snapshot.invoice_csv,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


@app.route('/api/snapshots/search', methods=['GET'])
@token_required
def search_snapshots():
    """
    Search archived snapshots with filters.

    Query params:
    - account_number: Filter by company
    - year: Filter by billing year
    - month: Filter by billing month
    - from_date: Filter snapshots archived after this date (YYYY-MM-DD)
    - to_date: Filter snapshots archived before this date (YYYY-MM-DD)
    - limit: Max results (default 100)
    - offset: Pagination offset
    """
    query = BillingSnapshot.query

    # Apply filters
    if request.args.get('account_number'):
        query = query.filter_by(company_account_number=request.args.get('account_number'))

    if request.args.get('year'):
        query = query.filter_by(billing_year=int(request.args.get('year')))

    if request.args.get('month'):
        query = query.filter_by(billing_month=int(request.args.get('month')))

    if request.args.get('from_date'):
        query = query.filter(BillingSnapshot.archived_at >= request.args.get('from_date'))

    if request.args.get('to_date'):
        query = query.filter(BillingSnapshot.archived_at <= request.args.get('to_date'))

    # Pagination
    limit = min(int(request.args.get('limit', 100)), 1000)
    offset = int(request.args.get('offset', 0))

    # Order by most recent first
    query = query.order_by(BillingSnapshot.archived_at.desc())

    # Get total count
    total = query.count()

    # Get results
    snapshots = query.limit(limit).offset(offset).all()

    # Build response
    results = [{
        'id': s.id,
        'company_account_number': s.company_account_number,
        'company_name': s.company_name,
        'invoice_number': s.invoice_number,
        'billing_year': s.billing_year,
        'billing_month': s.billing_month,
        'invoice_date': s.invoice_date,
        'archived_at': s.archived_at,
        'total_amount': float(s.total_amount),
        'user_count': s.user_count,
        'asset_count': s.asset_count
    } for s in snapshots]

    return jsonify({
        'total': total,
        'limit': limit,
        'offset': offset,
        'results': results
    }), 200


@app.route('/api/snapshots/company/<account_number>', methods=['GET'])
@token_required
def get_company_snapshots(account_number):
    """Get all snapshots for a specific company, ordered by date."""
    snapshots = BillingSnapshot.query.filter_by(
        company_account_number=account_number
    ).order_by(
        BillingSnapshot.billing_year.desc(),
        BillingSnapshot.billing_month.desc()
    ).all()

    results = [{
        'id': s.id,
        'invoice_number': s.invoice_number,
        'billing_year': s.billing_year,
        'billing_month': s.billing_month,
        'invoice_date': s.invoice_date,
        'archived_at': s.archived_at,
        'total_amount': float(s.total_amount),
        'billing_plan': s.billing_plan,
        'contract_term': s.contract_term
    } for s in snapshots]

    return jsonify({
        'company_account_number': account_number,
        'company_name': snapshots[0].company_name if snapshots else None,
        'total_snapshots': len(snapshots),
        'snapshots': results
    }), 200


# ===== BULK SNAPSHOT CREATION =====

@app.route('/api/snapshots/bulk/create', methods=['POST'])
@admin_required
def create_bulk_snapshots():
    """
    Create snapshots for multiple companies at once.
    Used by scheduler and manual bulk operations.

    Payload:
    {
        "year": 2025,
        "month": 10,
        "account_numbers": ["620547", "183729"]  // null/empty = all companies
    }
    """
    data = request.get_json()

    if not data or 'year' not in data or 'month' not in data:
        return jsonify({'error': 'year and month are required'}), 400

    year = data['year']
    month = data['month']
    account_numbers = data.get('account_numbers')

    # Create a job to track progress
    job_id = str(uuid.uuid4())
    job = SnapshotJob(
        id=job_id,
        job_type='bulk',
        status='running',
        target_year=year,
        target_month=month,
        target_account_numbers=json.dumps(account_numbers) if account_numbers else None,
        started_at=datetime.now().isoformat(),
        triggered_by=g.user.get('email') if hasattr(g, 'user') else 'api'
    )
    db.session.add(job)
    db.session.commit()

    # Return job ID immediately (processing happens async)
    return jsonify({
        'message': 'Bulk snapshot job started',
        'job_id': job_id
    }), 202


# ===== SCHEDULED SNAPSHOT CONFIGURATION =====

@app.route('/api/scheduler/config', methods=['GET', 'POST'])
@admin_required
def scheduler_config():
    """Get or update scheduled snapshot configuration."""
    if request.method == 'GET':
        config = ScheduledSnapshot.query.first()
        if not config:
            return jsonify({'config': None}), 200

        return jsonify({
            'config': {
                'id': config.id,
                'enabled': config.enabled,
                'day_of_month': config.day_of_month,
                'hour': config.hour,
                'snapshot_previous_month': config.snapshot_previous_month,
                'snapshot_all_companies': config.snapshot_all_companies,
                'last_run_at': config.last_run_at,
                'last_run_status': config.last_run_status,
                'last_run_count': config.last_run_count
            }
        }), 200

    # POST - update config
    data = request.get_json()
    config = ScheduledSnapshot.query.first()

    if not config:
        config = ScheduledSnapshot(created_at=datetime.now().isoformat())
        db.session.add(config)

    if 'enabled' in data:
        config.enabled = data['enabled']
    if 'day_of_month' in data:
        config.day_of_month = int(data['day_of_month'])
    if 'hour' in data:
        config.hour = int(data['hour'])
    if 'snapshot_previous_month' in data:
        config.snapshot_previous_month = data['snapshot_previous_month']
    if 'snapshot_all_companies' in data:
        config.snapshot_all_companies = data['snapshot_all_companies']

    config.updated_at = datetime.now().isoformat()

    try:
        db.session.commit()
        return jsonify({'message': 'Scheduler configuration updated'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/scheduler/jobs', methods=['GET'])
@token_required
def list_scheduler_jobs():
    """Get list of snapshot jobs."""
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))

    jobs = SnapshotJob.query.order_by(SnapshotJob.started_at.desc()).limit(limit).offset(offset).all()

    results = []
    for job in jobs:
        output = json.loads(job.output) if job.output else {}
        results.append({
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
            'success_count': output.get('success_count'),
            'failed_count': output.get('failed_count')
        })

    return jsonify({'jobs': results}), 200


@app.route('/api/scheduler/jobs/<job_id>', methods=['GET'])
@token_required
def get_job_status(job_id):
    """Get detailed status of a specific job."""
    from app.scheduler import get_job_status as get_status

    job_data = get_status(job_id)

    if not job_data:
        return jsonify({'error': 'Job not found'}), 404

    return jsonify(job_data), 200
