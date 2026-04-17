# ============================================================
# app/ml/risk_model.py — AI Loan Risk Scoring Engine
# SmartLoan Banking Pipeline
# ============================================================
# This file does three things:
#   1. Generates realistic synthetic training data (2000+ loans)
#   2. Trains a Random Forest classifier on that data
#   3. Provides predict_loan_risk() function used by the API
#
# Why Random Forest?
#   - Handles mixed data types (income, credit score, months)
#   - Naturally provides feature importance (explainability)
#   - Resistant to overfitting — reliable on real-world data
#   - Used by real banks for credit scoring (interpretable ML)
#
# Why explainability matters in banking:
#   Canadian OSFI B-20 guidelines require lenders to explain
#   WHY a loan was declined. Black-box models are not allowed
#   for consumer lending decisions.
# ============================================================

import numpy as np                          # numpy handles numerical arrays efficiently
import pandas as pd                         # pandas manages tabular data (like spreadsheets)
from sklearn.ensemble import RandomForestClassifier   # Our ML model
from sklearn.model_selection import train_test_split  # Splits data into train/test sets
from sklearn.preprocessing import StandardScaler      # Normalises feature values
from sklearn.metrics import classification_report     # Shows model accuracy per class
import pickle                               # pickle saves the trained model to disk
import os                                   # os handles file paths
import logging                              # logging records model training info

# Set up logging — records model training events to console and log files
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)   # __name__ = 'app.ml.risk_model'

# ── File path where trained model is saved ──
# We save the model so we don't retrain it on every API request
# Retraining takes seconds but would slow down every loan application
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'risk_model.pkl')
SCALER_PATH = os.path.join(os.path.dirname(__file__), 'scaler.pkl')


# ============================================================
# FUNCTION 1: generate_training_data
# Creates 2000+ realistic synthetic Canadian loan records
# We use synthetic data because real bank data is confidential
# The patterns we build in mirror real credit scoring logic
# ============================================================
def generate_training_data(n_samples=2500):
    """
    Generate synthetic but realistic Canadian loan application data.
    
    The data follows real-world credit scoring patterns:
    - Higher credit score → more likely to approve
    - Lower debt-to-income → more likely to approve  
    - Longer employment → more likely to approve
    - Higher income → more likely to approve
    
    Returns: pandas DataFrame with features and labels
    """
    
    logger.info(f"Generating {n_samples} synthetic loan records...")
    
    # Set random seed for reproducibility
    # Same seed = same data every time = consistent model training
    np.random.seed(42)
    
    # ── Generate individual features ──
    
    # Annual income: normally distributed around $65,000 CAD
    # Most Canadians earn between $35k-$120k
    annual_income = np.random.normal(65000, 25000, n_samples)
    annual_income = np.clip(annual_income, 20000, 250000)   # clip() enforces min/max limits
    
    # Credit score: Canadian range 300-900, most people 600-750
    credit_score = np.random.normal(680, 80, n_samples)
    credit_score = np.clip(credit_score, 300, 900).astype(int)   # Must be integer
    
    # Loan amount: $5,000 to $100,000
    loan_amount = np.random.exponential(25000, n_samples)   # exponential = more small loans
    loan_amount = np.clip(loan_amount, 1000, 500000)
    
    # Loan term: weighted towards common terms (36, 60 months)
    loan_term_options = [12, 24, 36, 48, 60, 84]
    loan_term_months = np.random.choice(
        loan_term_options,
        n_samples,
        p=[0.05, 0.15, 0.30, 0.20, 0.25, 0.05]   # probability weights — 30% choose 36 months
    )
    
    # Existing monthly debt: $0 to $3,000
    existing_monthly_debt = np.random.exponential(400, n_samples)
    existing_monthly_debt = np.clip(existing_monthly_debt, 0, 3000)
    
    # Employment months: 0 to 360 months (30 years)
    employment_months = np.random.exponential(48, n_samples)
    employment_months = np.clip(employment_months, 0, 360).astype(int)
    
    # ── Calculate derived features ──
    # These are features the model computes from raw inputs
    # Derived features often have stronger predictive power
    
    # Monthly income
    monthly_income = annual_income / 12
    
    # Estimated new monthly payment
    new_monthly_payment = loan_amount / loan_term_months
    
    # Debt-to-income ratio (DTI) — KEY metric in lending
    # DTI = total monthly debt / monthly income × 100
    total_monthly_debt = existing_monthly_debt + new_monthly_payment
    debt_to_income = (total_monthly_debt / monthly_income) * 100
    
    # Loan-to-income ratio — how big is the loan relative to annual income
    loan_to_income = loan_amount / annual_income
    
    # ── Generate labels (the "answer" the model learns to predict) ──
    # We create labels using a realistic scoring function
    # This mimics how a real bank underwriter would decide
    
    labels = []
    for i in range(n_samples):
        # Start with a base score
        score = 0
        
        # Credit score contribution (most important factor — 35% weight in real banks)
        if credit_score[i] >= 750:
            score += 40    # Excellent credit
        elif credit_score[i] >= 700:
            score += 30    # Good credit
        elif credit_score[i] >= 650:
            score += 15    # Fair credit
        elif credit_score[i] >= 600:
            score += 0     # Poor credit — neutral
        else:
            score -= 25    # Very poor credit — strong negative
        
        # Debt-to-income contribution (second most important — 30% weight)
        if debt_to_income[i] < 20:
            score += 30    # Very low debt burden
        elif debt_to_income[i] < 35:
            score += 15    # Manageable debt
        elif debt_to_income[i] < 43:
            score += 0     # OSFI guideline: 43% DTI is the stress test threshold
        elif debt_to_income[i] < 50:
            score -= 15    # High debt burden
        else:
            score -= 30    # Dangerous debt levels
        
        # Employment stability contribution (15% weight)
        if employment_months[i] >= 24:
            score += 15    # 2+ years = stable employment
        elif employment_months[i] >= 12:
            score += 5     # 1 year — acceptable
        elif employment_months[i] >= 6:
            score -= 5     # Less than a year — some risk
        else:
            score -= 15    # Very new job — high risk
        
        # Income contribution (10% weight)
        if annual_income[i] >= 100000:
            score += 10
        elif annual_income[i] >= 60000:
            score += 5
        elif annual_income[i] >= 40000:
            score += 0
        else:
            score -= 10
        
        # Loan-to-income ratio (10% weight)
        if loan_to_income[i] < 1.0:
            score += 10    # Loan less than annual income — low risk
        elif loan_to_income[i] < 2.5:
            score += 0     # Reasonable
        elif loan_to_income[i] < 4.0:
            score -= 10    # Stretching
        else:
            score -= 20    # Very large loan relative to income
        
        # Add realistic noise — real decisions aren't perfectly deterministic
        score += np.random.normal(0, 5)
        
        # Convert score to label
        if score >= 35:
            labels.append('APPROVED')
        elif score >= 10:
            labels.append('MANUAL_REVIEW')   # Borderline cases go to human review
        else:
            labels.append('DECLINED')
    
    # ── Build DataFrame ──
    # DataFrame = table where each row is a loan, each column is a feature
    df = pd.DataFrame({
        'annual_income': annual_income,
        'credit_score': credit_score,
        'loan_amount': loan_amount,
        'loan_term_months': loan_term_months,
        'existing_monthly_debt': existing_monthly_debt,
        'employment_months': employment_months,
        'debt_to_income': debt_to_income,           # Derived feature
        'loan_to_income': loan_to_income,           # Derived feature
        'label': labels                             # Target variable
    })
    
    logger.info(f"Data generated. Distribution: {df['label'].value_counts().to_dict()}")
    return df


# ============================================================
# FUNCTION 2: train_model
# Trains the Random Forest classifier
# Called once when the app starts if no saved model exists
# ============================================================
def train_model():
    """
    Train the Random Forest model on synthetic loan data.
    Saves the trained model and scaler to disk for reuse.
    Returns: trained model, scaler, feature names
    """
    
    logger.info("Training loan risk model...")
    
    # ── Generate training data ──
    df = generate_training_data(2500)
    
    # ── Separate features (X) from labels (y) ──
    # X = the input data the model learns patterns from
    # y = the correct answers the model tries to predict
    feature_columns = [
        'annual_income', 'credit_score', 'loan_amount',
        'loan_term_months', 'existing_monthly_debt',
        'employment_months', 'debt_to_income', 'loan_to_income'
    ]
    
    X = df[feature_columns].values   # .values converts DataFrame to numpy array
    y = df['label'].values            # Target labels array
    
    # ── Split into training and testing sets ──
    # 80% for training, 20% for testing
    # test_size=0.2 means 20% held back for evaluation
    # random_state=42 ensures same split every time (reproducibility)
    # stratify=y ensures all classes are proportionally represented in both sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # ── Scale features ──
    # StandardScaler normalises each feature to mean=0, std=1
    # Example: income of $65,000 and credit score of 680 are on very different scales
    # Without scaling, large numbers (income) dominate small numbers (credit score)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)   # fit() learns the scale, transform() applies it
    X_test_scaled = scaler.transform(X_test)          # Only transform() — use training set's scale
    
    # ── Train Random Forest ──
    model = RandomForestClassifier(
        n_estimators=100,      # 100 decision trees — more trees = more reliable but slower
        max_depth=10,          # Each tree can be at most 10 levels deep — prevents overfitting
        min_samples_split=5,   # Need at least 5 samples to split a node — prevents overfitting
        min_samples_leaf=2,    # Each leaf must have at least 2 samples
        class_weight='balanced', # Handles imbalanced classes (more APPROVED than DECLINED)
        random_state=42        # Reproducibility
    )
    
    model.fit(X_train_scaled, y_train)   # This is where actual learning happens
    
    # ── Evaluate the model ──
    y_pred = model.predict(X_test_scaled)
    report = classification_report(y_test, y_pred)
    logger.info(f"Model Performance:\n{report}")
    
    # Calculate and log accuracy
    accuracy = (y_pred == y_test).mean() * 100
    logger.info(f"Overall Accuracy: {accuracy:.1f}%")
    
    # ── Save model and scaler to disk ──
    # pickle serialises Python objects to binary files
    # This means we train once and load for every prediction
    with open(MODEL_PATH, 'wb') as f:    # 'wb' = write binary
        pickle.dump(model, f)
    
    with open(SCALER_PATH, 'wb') as f:
        pickle.dump(scaler, f)
    
    logger.info(f"Model saved to {MODEL_PATH}")
    
    return model, scaler, feature_columns


# ============================================================
# FUNCTION 3: load_model
# Loads the saved model from disk
# If no saved model exists, trains a new one first
# ============================================================
def load_model():
    """
    Load trained model from disk.
    If model file doesn't exist, train a new one.
    This is called once when the Flask app starts.
    """
    
    if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
        # Model already trained — just load it
        logger.info("Loading existing model from disk...")
        with open(MODEL_PATH, 'rb') as f:    # 'rb' = read binary
            model = pickle.load(f)
        with open(SCALER_PATH, 'rb') as f:
            scaler = pickle.load(f)
    else:
        # No saved model — train a new one
        logger.info("No saved model found. Training new model...")
        model, scaler, _ = train_model()
    
    return model, scaler


# ── Feature column names — must match training order exactly ──
FEATURE_COLUMNS = [
    'annual_income', 'credit_score', 'loan_amount',
    'loan_term_months', 'existing_monthly_debt',
    'employment_months', 'debt_to_income', 'loan_to_income'
]

# ── Human-readable feature names for the explanation ──
# These are shown to the applicant explaining the decision
FEATURE_NAMES = {
    'annual_income': 'Annual income',
    'credit_score': 'Credit score',
    'loan_amount': 'Loan amount requested',
    'loan_term_months': 'Loan term length',
    'existing_monthly_debt': 'Existing monthly debt',
    'employment_months': 'Employment history length',
    'debt_to_income': 'Debt-to-income ratio',
    'loan_to_income': 'Loan-to-income ratio'
}

# ── Load model at module import time ──
# This runs once when the Flask app starts
# All subsequent predictions use this loaded model (fast)
_model, _scaler = load_model()


# ============================================================
# FUNCTION 4: predict_loan_risk  ← THIS IS CALLED BY THE API
# Takes a loan application and returns a risk decision
# This is the main function called by app/routes/loans.py
# ============================================================
def predict_loan_risk(application_data):
    """
    Predict loan risk for a single application.
    
    Args:
        application_data: dict with keys matching FEATURE_COLUMNS
        
    Returns:
        dict with keys:
            decision       → 'APPROVED', 'MANUAL_REVIEW', or 'DECLINED'
            confidence     → float 0.0 to 1.0
            risk_level     → 'LOW', 'MEDIUM', or 'HIGH'
            reasons        → list of 3 human-readable explanation strings
    """
    
    # ── Step 1: Calculate derived features ──
    # loan_to_income is not sent by the user — we calculate it
    loan_to_income = application_data['loan_amount'] / application_data['annual_income']
    
    # ── Step 2: Build feature array in correct order ──
    # Order MUST match the order used during training
    features = np.array([[
        application_data['annual_income'],
        application_data['credit_score'],
        application_data['loan_amount'],
        application_data['loan_term_months'],
        application_data['existing_monthly_debt'],
        application_data['employment_months'],
        application_data['debt_to_income'],
        loan_to_income
    ]])
    # Double brackets [[...]] because sklearn expects shape (1, n_features)
    # Single bracket would give shape (n_features,) which causes an error
    
    # ── Step 3: Scale the features ──
    # Must use the SAME scaler that was used during training
    features_scaled = _scaler.transform(features)
    
    # ── Step 4: Get prediction and probability ──
    decision = _model.predict(features_scaled)[0]   # [0] gets first (only) result
    
    # predict_proba returns probability for each class
    # e.g., [0.05, 0.12, 0.83] for [APPROVED, DECLINED, MANUAL_REVIEW]
    probabilities = _model.predict_proba(features_scaled)[0]
    
    # Get confidence = probability of the predicted class
    class_index = list(_model.classes_).index(decision)
    confidence = probabilities[class_index]
    
    # ── Step 5: Determine risk level ──
    # Risk level is separate from the decision
    # A MANUAL_REVIEW can be LOW risk (borderline good) or HIGH risk (borderline bad)
    dti = application_data['debt_to_income']
    credit = application_data['credit_score']
    
    if credit >= 720 and dti < 30:
        risk_level = 'LOW'
    elif credit >= 650 and dti < 43:
        risk_level = 'MEDIUM'
    else:
        risk_level = 'HIGH'
    
    # ── Step 6: Generate explanation reasons ──
    # This is what makes our model OSFI-compliant
    # We use feature importances to find which factors drove the decision
    
    # Get feature importances from the Random Forest
    # importances[i] = how much feature i contributes to decisions (0 to 1)
    importances = _model.feature_importances_
    
    # Pair each feature with its value and importance score
    feature_values = features[0]   # Original unscaled values
    feature_info = list(zip(FEATURE_COLUMNS, feature_values, importances))
    
    # Sort by importance — most important features first
    feature_info.sort(key=lambda x: x[2], reverse=True)
    
    # Generate human-readable reasons based on top features
    reasons = []
    for feature_name, value, importance in feature_info[:4]:   # Top 4 features
        reason = _generate_reason(feature_name, value, decision)
        if reason:
            reasons.append(reason)
        if len(reasons) >= 3:   # We only show top 3 reasons
            break
    
    # Ensure we always have at least one reason
    if not reasons:
        reasons = [f"Application {decision.lower()} based on overall financial profile"]
    
    return {
        'decision': decision,
        'confidence': round(float(confidence), 4),   # float() converts numpy float to Python float
        'risk_level': risk_level,
        'reasons': reasons
    }


# ============================================================
# HELPER: _generate_reason
# Converts a feature name and value into a plain English sentence
# This is what gets shown to the applicant and auditors
# ============================================================
def _generate_reason(feature_name, value, decision):
    """
    Generate a human-readable explanation for a feature's impact.
    Returns a string explaining the factor, or None if not significant.
    """
    
    # Credit score explanations
    if feature_name == 'credit_score':
        if value >= 750:
            return f"Excellent credit score ({int(value)}) demonstrates strong repayment history"
        elif value >= 700:
            return f"Good credit score ({int(value)}) indicates reliable credit management"
        elif value >= 650:
            return f"Fair credit score ({int(value)}) suggests some credit risk"
        elif value >= 600:
            return f"Below-average credit score ({int(value)}) indicates elevated credit risk"
        else:
            return f"Low credit score ({int(value)}) significantly increases lending risk"
    
    # Debt-to-income ratio explanations
    elif feature_name == 'debt_to_income':
        dti = round(value, 1)
        if value < 20:
            return f"Low debt-to-income ratio ({dti}%) shows manageable debt obligations"
        elif value < 35:
            return f"Moderate debt-to-income ratio ({dti}%) is within acceptable range"
        elif value < 43:
            return f"Debt-to-income ratio ({dti}%) is near the OSFI stress test threshold of 43%"
        else:
            return f"High debt-to-income ratio ({dti}%) exceeds recommended lending thresholds"
    
    # Employment history explanations
    elif feature_name == 'employment_months':
        years = round(value / 12, 1)
        if value >= 24:
            return f"Stable employment history ({years} years) reduces income risk"
        elif value >= 12:
            return f"Employment history of {years} years is acceptable"
        elif value >= 6:
            return f"Limited employment history ({int(value)} months) indicates some income instability"
        else:
            return f"Very short employment history ({int(value)} months) presents income risk"
    
    # Annual income explanations
    elif feature_name == 'annual_income':
        income_k = round(value / 1000, 0)
        if value >= 100000:
            return f"Strong annual income (${income_k:.0f}K) supports loan repayment capacity"
        elif value >= 60000:
            return f"Adequate annual income (${income_k:.0f}K) for requested loan amount"
        elif value >= 40000:
            return f"Moderate income (${income_k:.0f}K) relative to requested loan amount"
        else:
            return f"Lower income (${income_k:.0f}K) limits loan repayment capacity"
    
    # Loan-to-income ratio
    elif feature_name == 'loan_to_income':
        lti = round(value, 2)
        if value < 1.0:
            return f"Loan amount is proportionate to annual income (ratio: {lti})"
        elif value < 2.5:
            return f"Loan-to-income ratio of {lti} is within standard lending parameters"
        else:
            return f"High loan-to-income ratio ({lti}) indicates significant borrowing relative to income"
    
    return None   # Return None for features we don't have a specific explanation for