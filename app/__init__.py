# ============================================================
# app/__init__.py — Application Factory
# SmartLoan Banking Pipeline
# ============================================================
# This file creates and configures the entire Flask application.
# We use the "Application Factory" pattern — a professional
# standard in banking/fintech systems because it allows us to
# create different versions of the app for testing vs production.
# ============================================================

import os                          # os lets us read environment variables (secret keys, DB paths)
from flask import Flask            # Flask is our web framework — handles HTTP requests/responses
from flask_sqlalchemy import SQLAlchemy   # SQLAlchemy connects Flask to our database (SQLite/MySQL)
from flask_bcrypt import Bcrypt           # Bcrypt hashes passwords — OWASP A02 requirement
from flask_jwt_extended import JWTManager # JWT manages authentication tokens — like a bank session

# ── Create extension instances (not yet attached to any app) ──
# We create these OUTSIDE the factory function so other files
# can import them directly (e.g. from app import db)
db = SQLAlchemy()    # Database extension — handles all SQL operations
bcrypt = Bcrypt()    # Password hashing — stores passwords as irreversible hash, never plain text
jwt = JWTManager()   # JWT token manager — issues and verifies login tokens


def create_app():
    """
    Application Factory Function.
    Call this function to get a fully configured Flask app.
    Banks use this pattern so the same codebase can run in
    development, testing, and production with different configs.
    """

    # ── Create the Flask application instance ──
    # __name__ tells Flask where to look for templates and static files
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    # ── Security Configuration ──
    # SECRET_KEY encrypts session cookies — if stolen, attackers can forge sessions
    # We read from environment variable first (production), fall back to dev key
    # NEVER hardcode a real secret key in production code — OWASP A02
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'smartloan-dev-secret-key-2024')

    # ── JWT Configuration ──
    # JWT_SECRET_KEY signs our authentication tokens
    # A different key from SECRET_KEY adds an extra layer of security
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'smartloan-jwt-secret-2024')

    # ── Database Configuration ──
    # We use SQLite for development (no setup needed, single file)
    # In production (Azure), this would be replaced with MySQL/PostgreSQL
    # The database file will be created at instance/smartloan.db
    basedir = os.path.abspath(os.path.dirname(__file__))  # Get absolute path of this file's folder
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL',                                    # Use env variable in production
        'sqlite:///' + os.path.join(basedir, '..', 'instance', 'smartloan.db')  # SQLite in dev
    )

    # ── Disable SQLAlchemy modification tracking ──
    # This feature is deprecated and wastes memory — banks care about performance
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ── OWASP A02: JWT token expiry ──
    # Tokens expire after 1 hour — banking standard
    # This limits damage if a token is stolen (attacker can only use it for 1 hour)
    from datetime import timedelta
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)

    # ── Attach extensions to this app instance ──
    # Now we connect the database, bcrypt, and JWT to our specific app
    db.init_app(app)      # Connect database to app
    bcrypt.init_app(app)  # Connect password hasher to app
    jwt.init_app(app)     # Connect JWT manager to app

    # ── Register Blueprints (API route groups) ──
    # Blueprints are how Flask organises routes into logical groups
    # Each blueprint is a separate file with related endpoints
    # Banking systems separate concerns: auth routes ≠ loan routes ≠ admin routes

    from app.routes.auth import auth_bp        # Authentication routes (register, login)
    from app.routes.loans import loans_bp      # Loan application routes (apply, view, predict)
    from app.routes.dashboard import dash_bp   # Dashboard data routes (stats, charts)

    app.register_blueprint(auth_bp, url_prefix='/api/auth')      # All auth routes start with /api/auth
    app.register_blueprint(loans_bp, url_prefix='/api/loans')    # All loan routes start with /api/loans
    app.register_blueprint(dash_bp, url_prefix='/api/dashboard') # All dashboard routes start with /api/dashboard

    # ── Create database tables ──
    # This checks if tables exist and creates them if they don't
    # Safe to run multiple times — won't duplicate tables
    with app.app_context():
        os.makedirs(os.path.join(basedir, '..', 'instance'), exist_ok=True)  # Create instance/ folder
        db.create_all()   # Create all tables defined in our models

    return app  # Return the fully configured app