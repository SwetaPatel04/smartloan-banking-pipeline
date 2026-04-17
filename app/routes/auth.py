# ============================================================
# app/routes/auth.py — Authentication Routes
# SmartLoan Banking Pipeline
# ============================================================
# This file handles two endpoints:
#   POST /api/auth/register → Create a new user account
#   POST /api/auth/login    → Login and receive a JWT token
#
# Why JWT tokens? Banks use token-based auth because:
#   1. Stateless — server doesn't store sessions (scales better)
#   2. Expiry — tokens auto-expire (OWASP A02 requirement)
#   3. Portable — same token works across microservices
# ============================================================

from flask import Blueprint, request, jsonify          # Blueprint groups related routes together
from flask_jwt_extended import create_access_token     # Creates a signed JWT token after login
from datetime import datetime                          # For timestamp in audit log
import re                                              # Regular expressions for input validation

from app import db, bcrypt                             # Import database and password hasher
from app.models import User, AuditLog                  # Import our database models


# ── Create a Blueprint ──
# A Blueprint is like a mini Flask app — it groups related routes
# url_prefix='/api/auth' is set in app/__init__.py
# So every route here automatically starts with /api/auth/
auth_bp = Blueprint('auth', __name__)


# ============================================================
# HELPER FUNCTION: log_audit
# Records every important action to the AuditLog table
# This is called after every register/login attempt
# Required for FINTRAC compliance in Canadian banking
# ============================================================
def log_audit(action, user_id=None, resource_type=None, resource_id=None, details=None):
    """
    Write an entry to the audit log table.
    Every login, failed login, registration is recorded here.
    In a real bank, auditors query this table during investigations.
    """
    # Get the client's IP address from the request
    # X-Forwarded-For header is used when behind a proxy/load balancer (Azure, AWS)
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    # Create a new audit log record
    log = AuditLog(
        user_id=user_id,           # Who did this action
        action=action,             # What they did (e.g., 'USER_REGISTERED')
        resource_type=resource_type, # What type of thing was affected
        resource_id=resource_id,   # Which specific record was affected
        details=details,           # Extra JSON details
        ip_address=ip,             # Where the request came from
        timestamp=datetime.utcnow() # Exact time — UTC is banking standard
    )

    db.session.add(log)    # Stage the log record for saving
    db.session.commit()    # Save it to the database permanently


# ============================================================
# HELPER FUNCTION: validate_password
# Enforces strong password rules — OWASP A07 requirement
# Banks require strong passwords to protect financial accounts
# ============================================================
def validate_password(password):
    """
    Check password meets banking security standards.
    Returns (True, None) if valid, (False, error_message) if not.
    """
    # Minimum 8 characters
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    # Must contain at least one uppercase letter
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"

    # Must contain at least one number
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"

    # Must contain at least one special character
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"

    return True, None   # Password passes all checks


# ============================================================
# ENDPOINT 1: POST /api/auth/register
# Creates a new user account
# ============================================================
@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user.
    Expects JSON body: { username, email, password, role }
    Returns: success message + user_id, or error message
    """

    # ── Step 1: Get JSON data from request body ──
    # request.get_json() parses the incoming JSON
    # silent=True means return None instead of crashing if JSON is malformed
    data = request.get_json(silent=True)

    # ── Step 2: OWASP A03 Input Validation ──
    # Validate BEFORE touching the database — never trust user input
    if not data:
        return jsonify({'error': 'Request body must be valid JSON'}), 400

    # Check all required fields are present
    required_fields = ['username', 'email', 'password']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Extract and strip whitespace from inputs
    username = data['username'].strip()    # .strip() removes leading/trailing spaces
    email = data['email'].strip().lower()  # .lower() normalises email (Bank@TD.com = bank@td.com)
    password = data['password']            # Don't strip password — spaces might be intentional
    role = data.get('role', 'applicant')   # Default role is applicant if not provided

    # Validate username length
    if len(username) < 3 or len(username) > 80:
        return jsonify({'error': 'Username must be between 3 and 80 characters'}), 400

    # Validate email format using regex
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return jsonify({'error': 'Invalid email format'}), 400

    # Validate password strength
    is_valid, error_msg = validate_password(password)
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    # Validate role — only allow specific roles (prevent privilege escalation)
    allowed_roles = ['applicant', 'loan_officer', 'admin']
    if role not in allowed_roles:
        return jsonify({'error': f'Invalid role. Must be one of: {allowed_roles}'}), 400

    # ── Step 3: Check if user already exists ──
    # Query database to see if username or email is taken
    existing_user = User.query.filter(
        (User.username == username) | (User.email == email)  # OR condition
    ).first()   # .first() returns the first match or None

    if existing_user:
        # Be vague about which one exists — prevents user enumeration attacks
        return jsonify({'error': 'Username or email already registered'}), 409

    # ── Step 4: Hash the password ──
    # bcrypt.generate_password_hash converts plain password to secure hash
    # e.g., "MyPass123!" becomes "$2b$12$LQv3c1yqBWVHxkd..."
    # The hash is ONE-WAY — you can never reverse it to get the original password
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    # .decode('utf-8') converts bytes to string so it can be stored in database

    # ── Step 5: Create and save the new user ──
    new_user = User(
        username=username,
        email=email,
        password_hash=password_hash,   # Store hash, NEVER the plain password
        role=role
    )

    db.session.add(new_user)      # Stage the new user for saving
    db.session.commit()           # Save to database permanently

    # ── Step 6: Write to audit log ──
    log_audit(
        action='USER_REGISTERED',
        user_id=new_user.id,
        resource_type='user',
        resource_id=new_user.id,
        details=f'{{"username": "{username}", "role": "{role}"}}'
    )

    # ── Step 7: Return success response ──
    # HTTP 201 = "Created" — correct status code for successful resource creation
    return jsonify({
        'message': 'Account created successfully',
        'user_id': new_user.id,
        'username': new_user.username,
        'role': new_user.role
    }), 201


# ============================================================
# ENDPOINT 2: POST /api/auth/login
# Authenticates user and returns a JWT token
# ============================================================
@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login with username and password.
    Expects JSON body: { username, password }
    Returns: JWT access token (valid for 1 hour)
    """

    # ── Step 1: Get and validate request data ──
    data = request.get_json(silent=True)

    if not data:
        return jsonify({'error': 'Request body must be valid JSON'}), 400

    if 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Username and password are required'}), 400

    username = data['username'].strip()
    password = data['password']

    # ── Step 2: Find user in database ──
    user = User.query.filter_by(username=username).first()

    # ── Step 3: Verify password ──
    # bcrypt.check_password_hash compares plain password against stored hash
    # Returns True if they match, False if not
    # We check BOTH conditions together — prevents timing attacks
    # (timing attack = attacker measures response time to guess if user exists)
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        # Log failed login attempt — important for fraud detection
        log_audit(
            action='LOGIN_FAILED',
            details=f'{{"username": "{username}", "reason": "invalid_credentials"}}'
        )
        # Return generic error — don't reveal whether username or password was wrong
        return jsonify({'error': 'Invalid username or password'}), 401

    # ── Step 4: Create JWT token ──
    # identity is what gets embedded in the token — we use user_id
    # additional_claims adds extra data to the token payload
    access_token = create_access_token(
        identity=str(user.id),    # User ID as string (JWT standard)
        additional_claims={
            'username': user.username,
            'role': user.role      # Role embedded in token — for authorization checks
        }
    )

    # ── Step 5: Log successful login ──
    log_audit(
        action='LOGIN_SUCCESS',
        user_id=user.id,
        resource_type='user',
        resource_id=user.id,
        details=f'{{"username": "{username}", "role": "{user.role}"}}'
    )

    # ── Step 6: Return token ──
    # HTTP 200 = OK
    return jsonify({
        'message': 'Login successful',
        'access_token': access_token,   # Client stores this and sends with every request
        'token_type': 'Bearer',         # Standard token type — sent as "Authorization: Bearer <token>"
        'user': {
            'id': user.id,
            'username': user.username,
            'role': user.role
        }
    }), 200