# ============================================================
# tests/test_app.py — Automated Test Suite
# SmartLoan Banking Pipeline
# ============================================================
# 20 automated tests covering:
#   - Authentication (register, login, JWT tokens)
#   - Loan application submission and AI decisions
#   - Input validation and security (OWASP A03)
#   - Dashboard statistics endpoints
#   - Edge cases and error handling
#
# Run with: pytest tests/ -v
# The -v flag shows each test name and pass/fail individually
#
# Why 20 tests matters:
#   Banks require automated test suites before any code
#   reaches production. 100% pass rate = production ready.
#   This is what Jenkins checks in our CI/CD pipeline.
# ============================================================

import pytest           # pytest is the testing framework
import json             # json helps us build request bodies and parse responses
import sys
import os

# Add the project root to Python path so imports work correctly
# Without this, pytest can't find the 'app' module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db    # Import our Flask app factory and database
from app.models import User, LoanApplication, AuditLog   # Import models for direct DB checks


# ============================================================
# TEST CONFIGURATION
# ============================================================

@pytest.fixture(scope='module')
def test_client():
    """
    pytest fixture — creates a test version of the Flask app.
    
    A fixture is setup code that runs before tests.
    scope='module' means this runs ONCE for the entire test file
    (not once per test) — makes tests run faster.
    
    We use a separate SQLite test database so tests don't
    corrupt the real development database.
    """
    # Create app with test configuration
    app = create_app()

    # Override settings for testing
    app.config['TESTING'] = True          # Enables test mode (better error messages)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    # ':memory:' creates a temporary database that only exists during tests
    # It's destroyed automatically when tests finish — no cleanup needed
    app.config['JWT_SECRET_KEY'] = 'test-secret-key-for-testing-only'
    app.config['WTF_CSRF_ENABLED'] = False   # Disable CSRF for testing

    # Create all database tables in the test database
    with app.app_context():
        db.create_all()

    # yield gives the test client to each test function
    # Code after yield runs as teardown (cleanup)
    with app.test_client() as client:
        with app.app_context():
            yield client    # Tests run here

    # Teardown — drop all tables after tests complete
    with app.app_context():
        db.drop_all()


@pytest.fixture(scope='module')
def auth_token(test_client):
    """
    pytest fixture — registers a test user and returns their JWT token.
    
    Many tests need authentication. Instead of logging in
    inside every test, we do it once here and share the token.
    This is the DRY principle (Don't Repeat Yourself).
    """
    # Register a test user
    test_client.post('/api/auth/register', json={
        'username': 'testuser',
        'email': 'test@smartloan.com',
        'password': 'Test@1234',
        'role': 'applicant'
    })

    # Login and get the token
    response = test_client.post('/api/auth/login', json={
        'username': 'testuser',
        'password': 'Test@1234'
    })

    data = json.loads(response.data)
    return data['access_token']   # Return token for use in tests


# ── Helper: build auth header ──
# Every protected endpoint needs this header
def auth_header(token):
    """Returns the Authorization header dict for JWT authentication."""
    return {'Authorization': f'Bearer {token}'}


# ── Helper: valid loan payload ──
# Reusable valid loan data so we don't repeat it in every test
def valid_loan_payload():
    """Returns a complete valid loan application payload."""
    return {
        'annual_income': 75000,
        'credit_score': 720,
        'loan_amount': 25000,
        'loan_term_months': 36,
        'existing_monthly_debt': 300,
        'employment_months': 36,
        'loan_purpose': 'car'
    }


# ============================================================
# AUTHENTICATION TESTS (Tests 1-6)
# ============================================================

class TestAuthentication:
    """Tests for user registration and login endpoints."""

    def test_01_register_success(self, test_client):
        """
        TEST 1: Successful user registration.
        A new user with valid data should get HTTP 201 Created.
        """
        response = test_client.post('/api/auth/register', json={
            'username': 'newuser',
            'email': 'newuser@test.com',
            'password': 'NewUser@123',
            'role': 'applicant'
        })

        # Assert HTTP status code is 201 (Created)
        assert response.status_code == 201

        data = json.loads(response.data)
        # Assert response contains expected fields
        assert 'user_id' in data
        assert data['username'] == 'newuser'
        assert data['role'] == 'applicant'
        # Assert password is NOT returned in response (security requirement)
        assert 'password' not in data
        assert 'password_hash' not in data

    def test_02_register_duplicate_username(self, test_client):
        """
        TEST 2: Duplicate username should be rejected.
        Banking systems must prevent account duplication.
        """
        # Try to register with same username as test_01
        response = test_client.post('/api/auth/register', json={
            'username': 'newuser',        # Already exists from test_01
            'email': 'different@test.com',
            'password': 'Test@1234'
        })

        # Assert HTTP 409 Conflict
        assert response.status_code == 409
        data = json.loads(response.data)
        assert 'error' in data

    def test_03_register_weak_password(self, test_client):
        """
        TEST 3: Weak password should be rejected.
        OWASP A07 requires strong passwords for financial systems.
        """
        response = test_client.post('/api/auth/register', json={
            'username': 'weakpassuser',
            'email': 'weak@test.com',
            'password': 'password'    # No uppercase, no number, no special char
        })

        # Assert HTTP 400 Bad Request
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_04_register_missing_fields(self, test_client):
        """
        TEST 4: Missing required fields should return 400.
        OWASP A03 — always validate all required inputs.
        """
        response = test_client.post('/api/auth/register', json={
            'username': 'incomplete'
            # Missing email and password
        })

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_05_login_success(self, test_client):
        """
        TEST 5: Successful login returns JWT token.
        The token is what the frontend stores and sends with every request.
        We use 'newuser' registered in test_01 to avoid fixture conflicts.
        """
        response = test_client.post('/api/auth/login', json={
            'username': 'newuser',      # Registered in test_01
            'password': 'NewUser@123'   # Password used in test_01
        })

        assert response.status_code == 200
        data = json.loads(response.data)

        # Assert token is returned
        assert 'access_token' in data
        assert data['token_type'] == 'Bearer'

        # Assert token is a non-empty string
        assert isinstance(data['access_token'], str)
        assert len(data['access_token']) > 0

        # Assert user info is returned
        assert data['user']['username'] == 'newuser'

    def test_06_login_wrong_password(self, test_client):
        """
        TEST 6: Wrong password should return 401 Unauthorized.
        Generic error message — don't reveal which field was wrong
        (prevents username enumeration attacks).
        """
        response = test_client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'WrongPassword@999'
        })

        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data
        # Error message should be generic — not "wrong password" specifically
        assert 'Invalid' in data['error']


# ============================================================
# LOAN APPLICATION TESTS (Tests 7-13)
# ============================================================

class TestLoanApplications:
    """Tests for loan application submission and AI decisions."""

    def test_07_apply_loan_success(self, test_client, auth_token):
        """
        TEST 7: Valid loan application returns AI decision.
        Core functionality — the AI must process and return a decision.
        """
        response = test_client.post(
            '/api/loans/apply',
            json=valid_loan_payload(),
            headers=auth_header(auth_token)
        )

        assert response.status_code == 201
        data = json.loads(response.data)

        # Assert all expected fields are present
        assert 'application_id' in data
        assert 'decision' in data
        assert 'confidence_score' in data
        assert 'risk_level' in data
        assert 'decision_reasons' in data
        assert 'debt_to_income_ratio' in data

        # Assert decision is one of the valid values
        assert data['decision'] in ['APPROVED', 'MANUAL_REVIEW', 'DECLINED']

        # Assert confidence is a valid percentage (0-100)
        assert 0 <= data['confidence_score'] <= 100

        # Assert risk level is valid
        assert data['risk_level'] in ['LOW', 'MEDIUM', 'HIGH']

        # Assert we get at least one reason
        assert len(data['decision_reasons']) >= 1

    def test_08_apply_loan_no_token(self, test_client):
        """
        TEST 8: Loan application without JWT token should be rejected.
        All financial endpoints must require authentication — OWASP A01.
        """
        response = test_client.post(
            '/api/loans/apply',
            json=valid_loan_payload()
            # No Authorization header
        )

        # Assert 401 Unauthorized — not 200 or 500
        assert response.status_code == 401

    def test_09_apply_loan_invalid_credit_score(self, test_client, auth_token):
        """
        TEST 9: Credit score outside 300-900 range should be rejected.
        Input validation protects the ML model from bad data.
        """
        payload = valid_loan_payload()
        payload['credit_score'] = 1200    # Invalid — max is 900

        response = test_client.post(
            '/api/loans/apply',
            json=payload,
            headers=auth_header(auth_token)
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'credit' in data['error'].lower()   # Error mentions credit score

    def test_10_apply_loan_negative_income(self, test_client, auth_token):
        """
        TEST 10: Negative annual income should be rejected.
        Financial systems must reject impossible values.
        """
        payload = valid_loan_payload()
        payload['annual_income'] = -50000    # Impossible value

        response = test_client.post(
            '/api/loans/apply',
            json=payload,
            headers=auth_header(auth_token)
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_11_apply_loan_invalid_purpose(self, test_client, auth_token):
        """
        TEST 11: Invalid loan purpose should be rejected.
        Only pre-approved categories are allowed — prevents data corruption.
        """
        payload = valid_loan_payload()
        payload['loan_purpose'] = 'gambling'    # Not in allowed purposes

        response = test_client.post(
            '/api/loans/apply',
            json=payload,
            headers=auth_header(auth_token)
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_12_high_risk_application_declined(self, test_client, auth_token):
        """
        TEST 12: High-risk application profile should be DECLINED or MANUAL_REVIEW.
        Verifies the AI model correctly identifies risky applications.
        Low credit score + high debt + short employment = high risk.
        """
        high_risk_payload = {
            'annual_income': 30000,          # Low income
            'credit_score': 450,             # Very poor credit
            'loan_amount': 100000,           # Large loan relative to income
            'loan_term_months': 60,
            'existing_monthly_debt': 2000,   # Very high existing debt
            'employment_months': 2,          # Very new job
            'loan_purpose': 'other'
        }

        response = test_client.post(
            '/api/loans/apply',
            json=high_risk_payload,
            headers=auth_header(auth_token)
        )

        assert response.status_code == 201
        data = json.loads(response.data)

        # High risk profile should NOT be approved
        assert data['decision'] in ['DECLINED', 'MANUAL_REVIEW']
        # Risk level should be HIGH
        assert data['risk_level'] == 'HIGH'

    def test_13_excellent_profile_approved(self, test_client, auth_token):
        """
        TEST 13: Excellent financial profile should be APPROVED or MANUAL_REVIEW.
        Verifies the AI model correctly rewards strong applications.
        High credit + low debt + long employment + high income = low risk.
        """
        excellent_payload = {
            'annual_income': 150000,       # High income
            'credit_score': 820,           # Excellent credit
            'loan_amount': 20000,          # Small loan relative to income
            'loan_term_months': 36,
            'existing_monthly_debt': 200,  # Very low debt
            'employment_months': 84,       # 7 years employed
            'loan_purpose': 'home_improvement'
        }

        response = test_client.post(
            '/api/loans/apply',
            json=excellent_payload,
            headers=auth_header(auth_token)
        )

        assert response.status_code == 201
        data = json.loads(response.data)

        # Excellent profile should NOT be declined
        assert data['decision'] in ['APPROVED', 'MANUAL_REVIEW']


# ============================================================
# MY APPLICATIONS TESTS (Tests 14-15)
# ============================================================

class TestMyApplications:
    """Tests for retrieving user's own applications."""

    def test_14_get_my_applications(self, test_client, auth_token):
        """
        TEST 14: Authenticated user can retrieve their own applications.
        Tests the GET /api/loans/my endpoint.
        """
        response = test_client.get(
            '/api/loans/my',
            headers=auth_header(auth_token)
        )

        assert response.status_code == 200
        data = json.loads(response.data)

        # Assert response has correct structure
        assert 'applications' in data
        assert 'total' in data
        assert isinstance(data['applications'], list)

        # We submitted applications in tests 7, 12, 13 so there should be some
        assert data['total'] >= 1

    def test_15_get_applications_no_token(self, test_client):
        """
        TEST 15: Getting applications without token should fail.
        Privacy requirement — users can only see their own data when authenticated.
        """
        response = test_client.get('/api/loans/my')

        assert response.status_code == 401


# ============================================================
# DASHBOARD TESTS (Tests 16-17)
# ============================================================

class TestDashboard:
    """Tests for dashboard statistics endpoints."""

    def test_16_dashboard_stats(self, test_client, auth_token):
        """
        TEST 16: Dashboard stats endpoint returns correct structure.
        These numbers power the metric cards in the UI.
        """
        response = test_client.get(
            '/api/dashboard/stats',
            headers=auth_header(auth_token)
        )

        assert response.status_code == 200
        data = json.loads(response.data)

        # Assert all required stat fields are present
        required_fields = [
            'total_applications', 'approved', 'declined',
            'manual_review', 'approval_rate', 'avg_confidence_score'
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        # Assert approval rate is a valid percentage
        assert 0 <= data['approval_rate'] <= 100

        # Assert total = approved + declined + manual_review
        total_check = data['approved'] + data['declined'] + data['manual_review']
        assert data['total_applications'] == total_check

    def test_17_dashboard_chart_data(self, test_client, auth_token):
        """
        TEST 17: Chart data endpoint returns correct structure for Chart.js.
        Frontend Chart.js requires labels[] and data[] arrays.
        """
        response = test_client.get(
            '/api/dashboard/chart',
            headers=auth_header(auth_token)
        )

        assert response.status_code == 200
        data = json.loads(response.data)

        # Assert chart data has correct structure
        assert 'decision_chart' in data
        assert 'risk_chart' in data
        assert 'purpose_chart' in data

        # Each chart must have labels and data arrays
        for chart_key in ['decision_chart', 'risk_chart', 'purpose_chart']:
            assert 'labels' in data[chart_key]
            assert 'data' in data[chart_key]
            # Labels and data must be same length (each label has a value)
            assert len(data[chart_key]['labels']) == len(data[chart_key]['data'])


# ============================================================
# AI MODEL TESTS (Tests 18-19)
# ============================================================

class TestAIModel:
    """Tests for the AI risk scoring engine directly."""

    def test_18_model_returns_valid_decision(self):
        """
        TEST 18: AI model returns valid decision for any input.
        Tests the predict_loan_risk function directly (unit test).
        Direct unit tests are faster than API tests — no HTTP overhead.
        """
        from app.ml.risk_model import predict_loan_risk

        result = predict_loan_risk({
            'annual_income': 70000,
            'credit_score': 700,
            'loan_amount': 20000,
            'loan_term_months': 36,
            'existing_monthly_debt': 400,
            'employment_months': 24,
            'debt_to_income': 28.5
        })

        # Assert all required fields are present
        assert 'decision' in result
        assert 'confidence' in result
        assert 'risk_level' in result
        assert 'reasons' in result

        # Assert values are in valid ranges
        assert result['decision'] in ['APPROVED', 'MANUAL_REVIEW', 'DECLINED']
        assert 0.0 <= result['confidence'] <= 1.0
        assert result['risk_level'] in ['LOW', 'MEDIUM', 'HIGH']
        assert len(result['reasons']) >= 1

    def test_19_model_confidence_is_float(self):
        """
        TEST 19: AI confidence score must be a proper float between 0 and 1.
        Ensures the model output is correctly typed for the database.
        Type errors in financial data cause serious production issues.
        """
        from app.ml.risk_model import predict_loan_risk

        result = predict_loan_risk({
            'annual_income': 55000,
            'credit_score': 650,
            'loan_amount': 15000,
            'loan_term_months': 24,
            'existing_monthly_debt': 600,
            'employment_months': 18,
            'debt_to_income': 35.0
        })

        # Assert confidence is a Python float (not numpy float, not string)
        assert isinstance(result['confidence'], float)

        # Assert it's within valid probability range
        assert 0.0 <= result['confidence'] <= 1.0

        # Assert reasons is a list of strings
        assert isinstance(result['reasons'], list)
        for reason in result['reasons']:
            assert isinstance(reason, str)
            assert len(reason) > 0   # No empty strings


# ============================================================
# SECURITY / EDGE CASE TESTS (Test 20)
# ============================================================

class TestSecurity:
    """Security and edge case tests."""

    def test_20_sql_injection_attempt(self, test_client):
        """
        TEST 20: SQL injection attempts in login must be rejected safely.
        OWASP A03 — the most common attack on financial applications.
        
        Classic SQL injection: username = "admin' OR '1'='1"
        If the app is vulnerable, this bypasses authentication.
        Our parameterized queries (via SQLAlchemy) prevent this.
        """
        # Classic SQL injection attempt in username field
        response = test_client.post('/api/auth/login', json={
            'username': "admin' OR '1'='1",
            'password': "anything' OR '1'='1"
        })

        # Must NOT return 200 (that would mean injection succeeded)
        assert response.status_code != 200

        # Must return 401 (unauthorized) — injection was blocked
        assert response.status_code == 401

        data = json.loads(response.data)
        # Must return an error, not user data
        assert 'error' in data
        assert 'access_token' not in data