# ============================================================
# app/routes/loans.py — Loan Application Routes
# SmartLoan Banking Pipeline
# ============================================================
# This file handles all loan-related endpoints:
#   POST /api/loans/apply      → Submit a new loan application
#   GET  /api/loans/           → View all applications (loan officers)
#   GET  /api/loans/<id>       → View one specific application
#   GET  /api/loans/my         → View my own applications
#
# Every endpoint requires a valid JWT token (authentication)
# Some endpoints require specific roles (authorization)
# This separation = RBAC (Role-Based Access Control) — banking standard
# ============================================================

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
# jwt_required     → decorator that blocks requests without valid JWT token
# get_jwt_identity → gets the user_id from the token
# get_jwt          → gets all claims from the token (including role)

from datetime import datetime
import json                        # For converting decision_reasons list to JSON string

from app import db
from app.models import LoanApplication, AuditLog, User
from app.ml.risk_model import predict_loan_risk   # Our AI model (we'll build this next)
from app.routes.auth import log_audit             # Reuse our audit logging helper


loans_bp = Blueprint('loans', __name__)


# ============================================================
# HELPER: validate_loan_data
# Validates all loan application fields before processing
# OWASP A03 — validate EVERY input from users
# ============================================================
def validate_loan_data(data):
    """
    Validate loan application input data.
    Returns (True, None) if valid, (False, error_message) if not.
    Banks reject incomplete or invalid applications immediately.
    """

    # Check all required fields exist
    required_fields = [
        'annual_income', 'credit_score', 'loan_amount',
        'loan_term_months', 'existing_monthly_debt',
        'employment_months', 'loan_purpose'
    ]
    for field in required_fields:
        if field not in data:
            return False, f'Missing required field: {field}'

    # Validate annual income — must be positive number
    if not isinstance(data['annual_income'], (int, float)) or data['annual_income'] <= 0:
        return False, 'Annual income must be a positive number'

    # Validate credit score — Canadian range is 300 to 900
    if not isinstance(data['credit_score'], int) or not (300 <= data['credit_score'] <= 900):
        return False, 'Credit score must be an integer between 300 and 900'

    # Validate loan amount — must be positive, max $500,000 for this system
    if not isinstance(data['loan_amount'], (int, float)) or not (1000 <= data['loan_amount'] <= 500000):
        return False, 'Loan amount must be between $1,000 and $500,000'

    # Validate loan term — common terms: 12, 24, 36, 48, 60 months
    valid_terms = [6, 12, 18, 24, 36, 48, 60, 84]
    if data['loan_term_months'] not in valid_terms:
        return False, f'Loan term must be one of: {valid_terms} months'

    # Validate existing debt — cannot be negative
    if not isinstance(data['existing_monthly_debt'], (int, float)) or data['existing_monthly_debt'] < 0:
        return False, 'Existing monthly debt cannot be negative'

    # Validate employment months — cannot be negative
    if not isinstance(data['employment_months'], int) or data['employment_months'] < 0:
        return False, 'Employment months cannot be negative'

    # Validate loan purpose — only allow specific categories
    valid_purposes = ['car', 'home_improvement', 'debt_consolidation', 'education', 'business', 'other']
    if data['loan_purpose'] not in valid_purposes:
        return False, f'Loan purpose must be one of: {valid_purposes}'

    return True, None   # All validations passed


# ============================================================
# ENDPOINT 1: POST /api/loans/apply
# Submit a new loan application
# Requires: valid JWT token (any role can apply)
# ============================================================
@loans_bp.route('/apply', methods=['POST'])
@jwt_required()    # This decorator blocks the request if no valid JWT token is provided
def apply_for_loan():
    """
    Submit a new loan application.
    The AI model automatically scores it and returns a decision.
    """

    # ── Step 1: Get current user from JWT token ──
    current_user_id = get_jwt_identity()   # Returns the user_id we embedded when creating the token
    claims = get_jwt()                      # Returns all token claims including role

    # ── Step 2: Get and validate request data ──
    data = request.get_json(silent=True)

    if not data:
        return jsonify({'error': 'Request body must be valid JSON'}), 400

    # Run our validation helper
    is_valid, error_msg = validate_loan_data(data)
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    # ── Step 3: Calculate debt-to-income ratio ──
    # DTI = (monthly debt payments / monthly income) × 100
    # This is a key metric banks use — high DTI = high risk
    monthly_income = data['annual_income'] / 12      # Convert annual to monthly
    new_monthly_payment = data['loan_amount'] / data['loan_term_months']  # Rough payment estimate
    total_monthly_debt = data['existing_monthly_debt'] + new_monthly_payment
    debt_to_income = (total_monthly_debt / monthly_income) * 100  # As a percentage

    # ── Step 4: Run AI risk prediction ──
    # Pass all features to our ML model
    prediction = predict_loan_risk({
        'annual_income': data['annual_income'],
        'credit_score': data['credit_score'],
        'loan_amount': data['loan_amount'],
        'loan_term_months': data['loan_term_months'],
        'existing_monthly_debt': data['existing_monthly_debt'],
        'employment_months': data['employment_months'],
        'debt_to_income': debt_to_income      # Calculated feature — not from user input
    })

    # ── Step 5: Create and save the loan application ──
    application = LoanApplication(
        user_id=int(current_user_id),
        annual_income=data['annual_income'],
        credit_score=data['credit_score'],
        loan_amount=data['loan_amount'],
        loan_term_months=data['loan_term_months'],
        existing_monthly_debt=data['existing_monthly_debt'],
        employment_months=data['employment_months'],
        loan_purpose=data['loan_purpose'],
        decision=prediction['decision'],               # AI decision
        confidence_score=prediction['confidence'],     # AI confidence
        risk_level=prediction['risk_level'],           # LOW/MEDIUM/HIGH
        decision_reasons=json.dumps(prediction['reasons']),  # Store as JSON string
        status='decided',
        decided_at=datetime.utcnow()
    )

    db.session.add(application)
    db.session.commit()

    # ── Step 6: Write audit log ──
    log_audit(
        action='LOAN_APPLICATION_SUBMITTED',
        user_id=int(current_user_id),
        resource_type='loan_application',
        resource_id=application.id,
        details=json.dumps({
            'decision': prediction['decision'],
            'confidence': prediction['confidence'],
            'loan_amount': data['loan_amount']
        })
    )

    # ── Step 7: Return the decision ──
    return jsonify({
        'message': 'Loan application processed successfully',
        'application_id': application.id,
        'decision': prediction['decision'],
        'confidence_score': round(prediction['confidence'] * 100, 1),  # e.g., 87.3%
        'risk_level': prediction['risk_level'],
        'decision_reasons': prediction['reasons'],
        'debt_to_income_ratio': round(debt_to_income, 2),
        'submitted_at': application.submitted_at.isoformat()   # ISO format for frontend
    }), 201


# ============================================================
# ENDPOINT 2: GET /api/loans/my
# View the current user's own applications
# ============================================================
@loans_bp.route('/my', methods=['GET'])
@jwt_required()
def my_applications():
    """
    Get all loan applications for the currently logged-in user.
    Applicants can only see their own applications — privacy requirement.
    """

    current_user_id = get_jwt_identity()

    # Query only this user's applications, newest first
    applications = LoanApplication.query.filter_by(
        user_id=int(current_user_id)
    ).order_by(LoanApplication.submitted_at.desc()).all()
    # .all() returns a list of all matching records

    # Convert list of objects to list of dictionaries for JSON response
    return jsonify({
        'total': len(applications),
        'applications': [
            {
                'id': app.id,
                'loan_amount': app.loan_amount,
                'loan_purpose': app.loan_purpose,
                'decision': app.decision,
                'confidence_score': round(app.confidence_score * 100, 1) if app.confidence_score else None,
                'risk_level': app.risk_level,
                'decision_reasons': json.loads(app.decision_reasons) if app.decision_reasons else [],
                'status': app.status,
                'submitted_at': app.submitted_at.isoformat()
            }
            for app in applications    # List comprehension — loops through all applications
        ]
    }), 200


# ============================================================
# ENDPOINT 3: GET /api/loans/all
# View ALL applications — loan officers and admins only
# RBAC: Role-Based Access Control — not every user can see everything
# ============================================================
@loans_bp.route('/all', methods=['GET'])
@jwt_required()
def all_applications():
    """
    Get all loan applications in the system.
    Only loan_officers and admins can access this endpoint.
    """

    # ── Check role from JWT token claims ──
    claims = get_jwt()
    role = claims.get('role', 'applicant')

    # Block access if not authorized role
    if role not in ['loan_officer', 'admin']:
        return jsonify({'error': 'Access denied. Loan officer or admin role required'}), 403
    # HTTP 403 = Forbidden (authenticated but not authorized)

    # Get optional query parameters for filtering
    decision_filter = request.args.get('decision')    # e.g., ?decision=APPROVED
    limit = request.args.get('limit', 50, type=int)   # Default 50 records max

    # Build query with optional filter
    query = LoanApplication.query
    if decision_filter:
        query = query.filter_by(decision=decision_filter)

    applications = query.order_by(
        LoanApplication.submitted_at.desc()
    ).limit(limit).all()

    return jsonify({
        'total': len(applications),
        'applications': [
            {
                'id': app.id,
                'user_id': app.user_id,
                'loan_amount': app.loan_amount,
                'loan_purpose': app.loan_purpose,
                'credit_score': app.credit_score,
                'annual_income': app.annual_income,
                'decision': app.decision,
                'confidence_score': round(app.confidence_score * 100, 1) if app.confidence_score else None,
                'risk_level': app.risk_level,
                'status': app.status,
                'submitted_at': app.submitted_at.isoformat()
            }
            for app in applications
        ]
    }), 200