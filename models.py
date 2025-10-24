"""
Archive Database Models

This service stores IMMUTABLE billing snapshots for historical record-keeping.
Each snapshot represents a finalized bill that was accepted/calculated at a specific point in time.

Key Principles:
- Data is write-once, read-many
- No modifications to archived bills
- Stores complete billing breakdown as JSON
- Indexed for fast search and retrieval
"""

from extensions import db
from sqlalchemy import BigInteger, Index


class BillingSnapshot(db.Model):
    """
    A complete billing snapshot for a company for a specific period.
    This is the primary archive record.
    """
    __tablename__ = 'billing_snapshots'

    id = db.Column(db.Integer, primary_key=True)

    # Identification
    company_account_number = db.Column(db.String(50), nullable=False, index=True)
    company_name = db.Column(db.String(150), nullable=False)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)

    # Billing Period
    billing_year = db.Column(db.Integer, nullable=False, index=True)
    billing_month = db.Column(db.Integer, nullable=False, index=True)

    # Dates
    invoice_date = db.Column(db.String(50), nullable=False)  # When invoice was generated
    due_date = db.Column(db.String(50))  # Payment due date
    archived_at = db.Column(db.String(50), nullable=False)  # When snapshot was created

    # Billing Plan Info (at time of snapshot)
    billing_plan = db.Column(db.String(100))
    contract_term = db.Column(db.String(50))
    support_level = db.Column(db.String(100))

    # Totals
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    total_user_charges = db.Column(db.Numeric(10, 2), default=0.00)
    total_asset_charges = db.Column(db.Numeric(10, 2), default=0.00)
    total_backup_charges = db.Column(db.Numeric(10, 2), default=0.00)
    total_ticket_charges = db.Column(db.Numeric(10, 2), default=0.00)
    total_line_item_charges = db.Column(db.Numeric(10, 2), default=0.00)

    # Counts
    user_count = db.Column(db.Integer, default=0)
    asset_count = db.Column(db.Integer, default=0)
    billable_hours = db.Column(db.Numeric(10, 2), default=0.00)

    # Complete Billing Data (JSON)
    # This stores the ENTIRE billing calculation result from Ledger
    billing_data_json = db.Column(db.Text, nullable=False)  # JSON blob

    # CSV Invoice (stored for download)
    invoice_csv = db.Column(db.Text, nullable=False)

    # Metadata
    created_by = db.Column(db.String(100))  # User or 'auto-scheduler'
    notes = db.Column(db.Text)  # Optional notes about this snapshot

    # Indexes for common queries
    __table_args__ = (
        Index('idx_company_period', 'company_account_number', 'billing_year', 'billing_month'),
        Index('idx_archived_at', 'archived_at'),
    )


class SnapshotLineItem(db.Model):
    """
    Individual line items from a billing snapshot.
    Denormalized for easier searching and reporting.
    """
    __tablename__ = 'snapshot_line_items'

    id = db.Column(db.Integer, primary_key=True)
    snapshot_id = db.Column(db.Integer, db.ForeignKey('billing_snapshots.id'), nullable=False, index=True)

    # Line Item Details
    line_type = db.Column(db.String(50), nullable=False)  # 'user', 'asset', 'backup', 'ticket', 'custom'
    item_name = db.Column(db.String(255), nullable=False)  # User/Asset name or custom item name
    description = db.Column(db.Text)  # Full description
    quantity = db.Column(db.Numeric(10, 2), default=1.00)
    rate = db.Column(db.Numeric(10, 2), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)

    # Relationship
    snapshot = db.relationship('BillingSnapshot', backref=db.backref('line_items', lazy='dynamic'))


class ScheduledSnapshot(db.Model):
    """
    Configuration for automated snapshot creation.
    Typically runs on the 1st of each month to archive previous month.
    """
    __tablename__ = 'scheduled_snapshots'

    id = db.Column(db.Integer, primary_key=True)

    # Schedule Configuration
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    day_of_month = db.Column(db.Integer, default=1, nullable=False)  # 1-31
    hour = db.Column(db.Integer, default=2, nullable=False)  # 0-23 (2am default)

    # What to snapshot
    snapshot_previous_month = db.Column(db.Boolean, default=True)  # Archive last month's bills
    snapshot_all_companies = db.Column(db.Boolean, default=True)  # All companies or specific?

    # Last Run
    last_run_at = db.Column(db.String(50))
    last_run_status = db.Column(db.String(50))  # 'success', 'partial', 'failed'
    last_run_count = db.Column(db.Integer, default=0)  # How many snapshots created
    last_run_log = db.Column(db.Text)  # Output/errors from last run

    # Metadata
    created_at = db.Column(db.String(50), nullable=False)
    updated_at = db.Column(db.String(50))


class SnapshotJob(db.Model):
    """
    Tracks individual snapshot creation jobs (manual or scheduled).
    """
    __tablename__ = 'snapshot_jobs'

    id = db.Column(db.String(50), primary_key=True)  # UUID
    job_type = db.Column(db.String(50), nullable=False)  # 'manual', 'scheduled', 'bulk'
    status = db.Column(db.String(20), nullable=False)  # 'running', 'completed', 'failed'

    # What's being snapshotted
    target_year = db.Column(db.Integer, nullable=False)
    target_month = db.Column(db.Integer, nullable=False)
    target_account_numbers = db.Column(db.Text)  # JSON array, null = all companies

    # Progress
    total_companies = db.Column(db.Integer, default=0)
    completed_companies = db.Column(db.Integer, default=0)
    failed_companies = db.Column(db.Integer, default=0)

    # Timing
    started_at = db.Column(db.String(50), nullable=False)
    completed_at = db.Column(db.String(50))

    # Output
    output = db.Column(db.Text)  # JSON output with success/failure details
    error = db.Column(db.Text)  # Error message if failed
    success = db.Column(db.Boolean)  # Overall success status

    # Who triggered it
    triggered_by = db.Column(db.String(100))  # Username or 'scheduler'
