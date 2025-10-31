#!/usr/bin/env python3
"""
Archive service runner.
Uses Flask development server for local development.
For production, use Gunicorn or Waitress with proper configuration.
"""

from dotenv import load_dotenv
import os

# Load .flaskenv before importing app
load_dotenv('.flaskenv')

from app import app

if __name__ == '__main__':
    port = int(os.environ.get('SERVICE_PORT', 5012))
    # Bind to 127.0.0.1 for security (only local access)
    # Nexus reverse proxy will handle external access
    # Debug mode enables auto-reload for templates and code changes
    app.run(host='127.0.0.1', port=port, debug=True)
