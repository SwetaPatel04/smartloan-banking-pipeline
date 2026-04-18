# 🏦 SmartLoan — AI-Powered Banking Loan Pipeline

> **Portfolio Project by Sweta Patel** | Python Developer | DevOps Engineer | AI/ML Specialist

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-green)](https://flask.palletsprojects.com)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-ML-orange)](https://scikit-learn.org)
[![Docker](https://img.shields.io/badge/Docker-Container-blue)](https://docker.com)
[![Jenkins](https://img.shields.io/badge/Jenkins-CI/CD-red)](https://jenkins.io)
[![Tests](https://img.shields.io/badge/Tests-20%20Passing-brightgreen)]()

---

## 🎯 Project Overview

SmartLoan is a **production-grade AI-powered loan decision system** that demonstrates
modern banking technology: automated risk scoring, regulatory compliance, and
full DevOps automation — the same stack used by RBC, TD, and Scotiabank.

**Live Demo:** Submit a loan application and receive an AI decision in under 2 seconds,
complete with explainable reasons (OSFI B-20 compliant).

---

## 🏗️ Architecture
Loan Application Form (HTML/JS)
↓
Flask REST API (JWT Auth + OWASP Security)
↓
n8n Automation (Webhook → Validation → Notification)
↓
AI Risk Engine (Random Forest — scikit-learn)
↓
SQLite Database (Audit Trail + Applications)
↓
Chart.js Dashboard (Real-time Analytics)
↓
Jenkins CI/CD → Docker → Azure Deployment
---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Backend | Python, Flask | REST API, routing |
| AI/ML | scikit-learn, Random Forest | Loan risk scoring |
| Security | JWT, Bcrypt, OWASP A02/A03 | Auth + input validation |
| Database | SQLAlchemy, SQLite | Data + audit trail |
| Frontend | HTML, CSS, Chart.js | Live dashboard |
| Automation | n8n | Workflow automation |
| DevOps | Jenkins, Docker, GitHub Actions | CI/CD pipeline |
| Cloud | Microsoft Azure | Production deployment |
| Testing | pytest, 20 tests | Quality assurance |

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/SwetaPatel04/smartloan-banking-pipeline.git
cd smartloan-banking-pipeline

# Create virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py

# Open browser
# http://localhost:5000
```

---

## 🧪 Running Tests

```bash
# Run all 20 tests
pytest tests/ -v

# Expected output:
# 20 passed in ~8s
```

---

## 🐳 Docker

```bash
# Build container
docker build -t smartloan .

# Run container
docker run -p 5000:5000 smartloan

# Health check
curl http://localhost:5000/api/health
```

---

## 🔒 Banking Compliance Features

- **OSFI B-20**: Explainable AI decisions (3 reasons per decision)
- **FINTRAC**: Complete audit trail for every action
- **OWASP A02**: Bcrypt password hashing
- **OWASP A03**: Parameterized queries + input validation
- **PIPEDA**: No sensitive data in logs or responses

---

## 📊 AI Model Performance

- **Algorithm**: Random Forest (100 estimators)
- **Training Data**: 2,500 synthetic Canadian loan records
- **Accuracy**: 85%+ on held-out test set
- **Features**: Credit score, DTI ratio, income, employment history
- **Output**: APPROVED / MANUAL_REVIEW / DECLINED + confidence score

---

## 👩‍💻 About the Developer

**Sweta Patel** — Python Developer | DevOps Engineer | AI/ML Specialist  
