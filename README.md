# HiveMatrix Archive

Immutable billing snapshot storage service for HiveMatrix.

Archive takes billing exports from Ledger as permanent snapshots:
- **Permanent billing records** - Immutable snapshots of accepted bills
- **Historical lookup** - Search past bills by company, year, month
- **CSV downloads** - Export invoices for accounting
- **Automated snapshots** - Scheduled monthly billing captures
- **Audit trail** - Complete history of billing changes

When a bill is "accepted" in Ledger, Archive stores a permanent, unchangeable snapshot of that billing period.

## Documentation

For installation, configuration, and architecture documentation, please visit:

**[HiveMatrix Documentation](https://ruapotato.github.io/hivematrix-docs/ARCHITECTURE/)**

## Quick Start

This service is installed and managed by HiveMatrix Helm. See the documentation link above for setup instructions.
