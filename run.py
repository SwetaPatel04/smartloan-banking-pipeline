# ============================================================
# run.py — Application Entry Point
# SmartLoan Banking Pipeline
# ============================================================
# This file starts the Flask server AND serves the frontend.
# We added a root route '/' that returns the dashboard HTML.
# Without this route, Flask doesn't know what to show at /
# ============================================================

import os
from flask import render_template   # render_template reads HTML from templates/ folder
from app import create_app

# ── Create the Flask app ──
app = create_app()

# ── Root route — serves the dashboard HTML ──
# When someone visits http://localhost:5000 in their browser,
# Flask calls this function and returns index.html
@app.route('/')
def index():
    # render_template looks inside the templates/ folder automatically
    # This is why we put index.html in templates/ and not the root folder
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV', 'development') == 'development'

    print("=" * 60)
    print("  SmartLoan Banking Pipeline")
    print("  AI-Powered Loan Decision System")
    print(f"  Running on http://localhost:{port}")
    print(f"  Debug mode: {debug_mode}")
    print("=" * 60)

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode
    )