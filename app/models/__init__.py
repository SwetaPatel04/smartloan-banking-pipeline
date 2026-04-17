# ============================================================
# app/models/__init__.py — Database Table Definitions
# SmartLoan Banking Pipeline
# ============================================================
# Models define the structure of our database tables.
# SQLAlchemy lets us write Python classes instead of raw SQL.
# Each class = one table. Each attribute = one column.
# Banking systems need at minimum: Users, Applications, AuditLog
# ============================================================

from datetime import datetime   # datetime stamps every record — required for banking audit trails
from app import db               # Import the db instance we created in app/__init__.py


# ============================================================
# TABLE 1: User
# Stores bank system users (loan officers, applicants, admins)
# OWASP A02: passwords are NEVER stored as plain text — only bcrypt hashes
# ============================================================
class User(db.Model):
    __tablename__ = 'users'   # Explicit table name — good practice, avoids SQLAlchemy naming surprises

    # Primary key — unique identifier for every user
    # autoincrement=True means database assigns the number automatically
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Username — must be unique (no two users with same username)
    # nullable=False means this field is REQUIRED — cannot be empty
    username = db.Column(db.String(80), unique=True, nullable=False)

    # Email — must be unique, used for notifications and password reset
    email = db.Column(db.String(120), unique=True, nullable=False)

    # Password hash — NEVER the real password, always a bcrypt hash
    # Length 255 because bcrypt hashes are long strings
    password_hash = db.Column(db.String(255), nullable=False)

    # Role — controls what the user can do (applicant vs loan_officer vs admin)
    # Default is 'applicant' — least privileged role (OWASP principle of least privilege)
    role = db.Column(db.String(20), nullable=False, default='applicant')

    # Timestamp — when the account was created
    # server_default means the database fills this in automatically
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship — one user can have many loan applications
    # backref='applicant' lets us do loan.applicant to get the user
    # lazy=True means applications are only loaded when accessed (performance)
    applications = db.relationship('LoanApplication', backref='applicant', lazy=True)

    def __repr__(self):
        # __repr__ controls how this object prints — useful for debugging
        return f'<User {self.username} | Role: {self.role}>'


# ============================================================
# TABLE 2: LoanApplication
# Every loan application submitted through the system
# This is the core table of a banking loan processing system
# FINTRAC/OSFI compliance: every application must be stored permanently
# ============================================================
class LoanApplication(db.Model):
    __tablename__ = 'loan_applications'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Foreign key — links this application to the user who submitted it
    # ondelete='RESTRICT' means you CANNOT delete a user who has applications
    # Banking systems never delete financial records — regulatory requirement
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)

    # ── Applicant Financial Profile ──
    # These are the features our ML model uses to predict loan risk

    # Annual income in Canadian dollars
    annual_income = db.Column(db.Float, nullable=False)

    # Credit score (300-900 range in Canada)
    credit_score = db.Column(db.Integer, nullable=False)

    # Loan amount requested in Canadian dollars
    loan_amount = db.Column(db.Float, nullable=False)

    # Loan term in months (e.g., 12, 24, 36, 60)
    loan_term_months = db.Column(db.Integer, nullable=False)

    # Monthly debt payments (car loan, credit cards, etc.)
    existing_monthly_debt = db.Column(db.Float, nullable=False)

    # How long the applicant has been employed (months)
    employment_months = db.Column(db.Integer, nullable=False)

    # Loan purpose — car, home_improvement, debt_consolidation, education, other
    loan_purpose = db.Column(db.String(50), nullable=False)

    # ── AI Decision Fields ──
    # These are filled in by our ML model after the application is submitted

    # Decision: APPROVED, MANUAL_REVIEW, or DECLINED
    decision = db.Column(db.String(20), nullable=True)

    # How confident the model is (0.0 to 1.0 — e.g., 0.87 = 87% confident)
    confidence_score = db.Column(db.Float, nullable=True)

    # Risk level: LOW, MEDIUM, HIGH
    risk_level = db.Column(db.String(10), nullable=True)

    # Top 3 reasons for the decision (stored as JSON string)
    # e.g., '["Low credit score", "High debt ratio", "Short employment"]'
    decision_reasons = db.Column(db.Text, nullable=True)

    # ── Status and Timestamps ──
    # Application status in the workflow pipeline
    status = db.Column(db.String(20), nullable=False, default='pending')

    # When the application was submitted
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    # When the AI decision was made
    decided_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<LoanApplication #{self.id} | User:{self.user_id} | {self.decision}>'


# ============================================================
# TABLE 3: AuditLog
# Records EVERY important action in the system
# This is a LEGAL REQUIREMENT in Canadian banking (FINTRAC/OSFI)
# If something goes wrong, auditors trace back using this table
# ============================================================
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Who performed the action (user_id — nullable for system actions)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # What action was performed (e.g., 'LOGIN', 'LOAN_SUBMITTED', 'DECISION_MADE')
    action = db.Column(db.String(100), nullable=False)

    # Which resource was affected (e.g., 'loan_application', 'user_account')
    resource_type = db.Column(db.String(50), nullable=True)

    # The ID of the specific resource (e.g., loan application #42)
    resource_id = db.Column(db.Integer, nullable=True)

    # Additional details stored as JSON string
    # e.g., '{"decision": "APPROVED", "confidence": 0.92}'
    details = db.Column(db.Text, nullable=True)

    # IP address of the request — required for fraud investigation
    ip_address = db.Column(db.String(45), nullable=True)   # 45 chars supports IPv6

    # Exact timestamp — microsecond precision for audit trails
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<AuditLog {self.action} by User:{self.user_id} at {self.timestamp}>'