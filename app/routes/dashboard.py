# ============================================================
# app/routes/dashboard.py — Dashboard Statistics Routes
# SmartLoan Banking Pipeline
# ============================================================
# This file provides data for the frontend dashboard charts.
# Endpoints:
#   GET /api/dashboard/stats     → Overall system statistics
#   GET /api/dashboard/chart     → Data for Chart.js graphs
# ============================================================

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import func          # func lets us use SQL aggregate functions like COUNT, AVG

from app import db
from app.models import LoanApplication, User, AuditLog


dash_bp = Blueprint('dashboard', __name__)


# ============================================================
# ENDPOINT 1: GET /api/dashboard/stats
# Overall statistics for the dashboard header cards
# ============================================================
@dash_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    """
    Returns summary statistics for the dashboard.
    This powers the metric cards at the top of the dashboard.
    """

    # ── Count total applications ──
    total_apps = LoanApplication.query.count()   # COUNT(*) equivalent

    # ── Count by decision using group_by ──
    # This runs one SQL query instead of three separate ones (more efficient)
    decision_counts = db.session.query(
        LoanApplication.decision,          # Group by this column
        func.count(LoanApplication.id)     # Count records in each group
    ).group_by(LoanApplication.decision).all()

    # Convert list of tuples to dictionary: {'APPROVED': 45, 'DECLINED': 23, ...}
    decisions = {decision: count for decision, count in decision_counts if decision}

    # ── Calculate average confidence score ──
    avg_confidence = db.session.query(
        func.avg(LoanApplication.confidence_score)   # SQL AVG function
    ).scalar()   # .scalar() returns a single value instead of a list

    # ── Calculate average credit score ──
    avg_credit = db.session.query(
        func.avg(LoanApplication.credit_score)
    ).scalar()

    # ── Total loan value requested ──
    total_loan_value = db.session.query(
        func.sum(LoanApplication.loan_amount)    # SQL SUM function
    ).scalar()

    return jsonify({
        'total_applications': total_apps,
        'approved': decisions.get('APPROVED', 0),      # .get() returns 0 if key doesn't exist
        'declined': decisions.get('DECLINED', 0),
        'manual_review': decisions.get('MANUAL_REVIEW', 0),
        'approval_rate': round(
            (decisions.get('APPROVED', 0) / total_apps * 100), 1
        ) if total_apps > 0 else 0,                    # Avoid division by zero
        'avg_confidence_score': round(avg_confidence * 100, 1) if avg_confidence else 0,
        'avg_credit_score': round(avg_credit, 0) if avg_credit else 0,
        'total_loan_value_requested': round(total_loan_value, 2) if total_loan_value else 0
    }), 200


# ============================================================
# ENDPOINT 2: GET /api/dashboard/chart
# Data formatted for Chart.js on the frontend
# ============================================================
@dash_bp.route('/chart', methods=['GET'])
@jwt_required()
def get_chart_data():
    """
    Returns data formatted for Chart.js doughnut and bar charts.
    The frontend JavaScript reads this and renders the charts.
    """

    # ── Decision distribution for doughnut chart ──
    decision_data = db.session.query(
        LoanApplication.decision,
        func.count(LoanApplication.id)
    ).group_by(LoanApplication.decision).all()

    # ── Risk level distribution for bar chart ──
    risk_data = db.session.query(
        LoanApplication.risk_level,
        func.count(LoanApplication.id)
    ).group_by(LoanApplication.risk_level).all()

    # ── Loan purpose breakdown ──
    purpose_data = db.session.query(
        LoanApplication.loan_purpose,
        func.count(LoanApplication.id)
    ).group_by(LoanApplication.loan_purpose).all()

    return jsonify({
        # Decision doughnut chart data
        'decision_chart': {
            'labels': [d[0] for d in decision_data if d[0]],   # ['APPROVED', 'DECLINED', ...]
            'data': [d[1] for d in decision_data if d[0]]       # [45, 23, 12]
        },
        # Risk level bar chart data
        'risk_chart': {
            'labels': [r[0] for r in risk_data if r[0]],
            'data': [r[1] for r in risk_data if r[0]]
        },
        # Loan purpose pie chart data
        'purpose_chart': {
            'labels': [p[0] for p in purpose_data if p[0]],
            'data': [p[1] for p in purpose_data if p[0]]
        }
    }), 200