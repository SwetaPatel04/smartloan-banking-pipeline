# ============================================================
# run.py — Application Entry Point
# SmartLoan Banking Pipeline
# ============================================================
# This is the file you run to start the Flask server.
# Command: python run.py
#
# In production (Azure/Docker), a WSGI server like Gunicorn
# runs this file instead: gunicorn run:app
# The 'app' in 'run:app' refers to the 'app' variable below
# ============================================================

import os
from app import create_app    # Import our application factory

# ── Create the Flask app ──
# create_app() builds the full app with all routes and database
app = create_app()

if __name__ == '__main__':
    # ── Only runs when you execute: python run.py ──
    # Not used in production — Gunicorn/Docker calls create_app() directly
    
    # Get port from environment variable or default to 5000
    # Azure sets PORT automatically — we read it here
    port = int(os.environ.get('PORT', 5000))
    
    # debug=True enables:
    #   - Auto-reload when you save code changes
    #   - Detailed error pages in the browser
    # NEVER set debug=True in production — exposes internal code
    debug_mode = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    print("=" * 60)
    print("  SmartLoan Banking Pipeline")
    print("  AI-Powered Loan Decision System")
    print(f"  Running on http://localhost:{port}")
    print(f"  Debug mode: {debug_mode}")
    print("=" * 60)
    
    app.run(
        host='0.0.0.0',      # 0.0.0.0 means accept connections from any IP
        port=port,           # Port number
        debug=debug_mode     # Debug mode based on environment
    )