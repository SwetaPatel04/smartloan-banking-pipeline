# ============================================================
# run.py — Application Entry Point
# SmartLoan Banking Pipeline
# ============================================================

import os
from flask import render_template, jsonify
from app import create_app

# ── Create the Flask app ──
app = create_app()


# ── Root route — serves the dashboard HTML ──
@app.route('/')
def index():
    # render_template looks inside the templates/ folder automatically
    return render_template('index.html')


# ── Health check endpoint ──
# Used by Docker, Jenkins, and Azure to verify the app is running
# Returns HTTP 200 if healthy — any other code means something is wrong
# This is standard in ALL production banking systems
@app.route('/api/health')
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'SmartLoan Banking Pipeline',
        'version': '1.0'
    }), 200


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