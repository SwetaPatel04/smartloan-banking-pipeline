// ============================================================
// Jenkinsfile — CI/CD Pipeline Definition
// SmartLoan Banking Pipeline
// ============================================================
// This file defines our automated pipeline.
// Every time code is pushed to GitHub, Jenkins:
//   1. Pulls the latest code
//   2. Installs dependencies
//   3. Runs all 20 pytest tests
//   4. Builds a Docker image
//   5. Deploys to Azure (if tests pass)
//
// Why Jenkins in banking?
//   Banks cannot manually deploy code — too risky, too slow.
//   Jenkins automates the entire process so every deployment
//   is identical, tested, and traceable (audit requirement).
//
// This is called a "Declarative Pipeline" — the modern standard.
// ============================================================

pipeline {

    // ── Agent ──
    // 'any' means run on any available Jenkins worker
    // In production banks, specific agents have specific tools
    agent any

    // ── Environment Variables ──
    // Available to all stages as environment.VARIABLE_NAME
    environment {
        // Application settings
        APP_NAME        = 'smartloan-banking-pipeline'
        PYTHON_VERSION  = '3.11'

        // Docker settings
        DOCKER_IMAGE    = "smartloan:${BUILD_NUMBER}"
        // BUILD_NUMBER is auto-incremented by Jenkins for every build
        // This gives every Docker image a unique tag (smartloan:1, smartloan:2...)

        // Flask settings for testing
        FLASK_ENV       = 'testing'
        SECRET_KEY      = 'jenkins-test-secret-key'
        JWT_SECRET_KEY  = 'jenkins-test-jwt-key'
    }

    // ── Options ──
    options {
        // Cancel build if it takes more than 20 minutes
        // Prevents stuck builds from blocking the pipeline
        timeout(time: 20, unit: 'MINUTES')

        // Keep only last 10 builds — saves disk space on Jenkins server
        buildDiscarder(logRotator(numToKeepStr: '10'))

        // Add timestamps to every log line — required for audit trails
        timestamps()
    }

    // ── Stages ──
    // Each stage is a step in the pipeline
    // If any stage fails, Jenkins stops and marks the build as FAILED
    stages {

        // ── STAGE 1: Checkout ──
        // Pull the latest code from GitHub
        stage('Checkout') {
            steps {
                echo '============================================'
                echo 'STAGE 1: Pulling latest code from GitHub'
                echo '============================================'

                // checkout scm = get code from the GitHub repo
                // Jenkins knows which repo from its configuration
                checkout scm

                // Print the commit hash for traceability
                // Banks need to know EXACTLY which code version is deployed
                sh 'git log --oneline -1'
            }
        }

        // ── STAGE 2: Setup Python Environment ──
        // Create virtual environment and install dependencies
        stage('Setup Environment') {
            steps {
                echo '============================================'
                echo 'STAGE 2: Setting up Python environment'
                echo '============================================'

                sh '''
                    # Create virtual environment
                    python3 -m venv venv

                    # Activate and install dependencies
                    . venv/bin/activate

                    # Upgrade pip first
                    pip install --upgrade pip

                    # Install all project dependencies
                    pip install -r requirements.txt

                    # Show installed packages for audit trail
                    pip list
                '''
            }
        }

        // ── STAGE 3: Run Tests ──
        // This is the most critical stage
        // If ANY test fails, the pipeline stops here — code does NOT deploy
        stage('Run Tests') {
            steps {
                echo '============================================'
                echo 'STAGE 3: Running 20 automated pytest tests'
                echo '============================================'

                sh '''
                    # Activate virtual environment
                    . venv/bin/activate

                    # Run all tests with verbose output and JUnit XML report
                    # --tb=short shows shortened traceback on failure
                    # --junit-xml creates a report Jenkins can read
                    pytest tests/ -v --tb=short --junit-xml=test-results.xml
                '''
            }

            post {
                // always runs whether tests pass or fail
                always {
                    // Publish test results in Jenkins UI
                    // This creates a nice test report dashboard in Jenkins
                    junit 'test-results.xml'
                }

                failure {
                    echo 'TESTS FAILED — Deployment blocked!'
                    echo 'Fix failing tests before code can reach production'
                }

                success {
                    echo 'All 20 tests passed — proceeding to deployment'
                }
            }
        }

        // ── STAGE 4: Build Docker Image ──
        // Package the application into a Docker container
        stage('Build Docker Image') {
            steps {
                echo '============================================'
                echo "STAGE 4: Building Docker image ${DOCKER_IMAGE}"
                echo '============================================'

                sh '''
                    # Build the Docker image using our Dockerfile
                    # -t tags the image with our name and build number
                    # . means use the current directory as build context
                    docker build -t ${DOCKER_IMAGE} .

                    # Also tag as 'latest' for easy reference
                    docker tag ${DOCKER_IMAGE} smartloan:latest

                    # Show image size — banks care about container efficiency
                    docker images smartloan
                '''
            }
        }

        // ── STAGE 5: Security Scan ──
        // Basic security check before deployment
        stage('Security Check') {
            steps {
                echo '============================================'
                echo 'STAGE 5: Running security checks'
                echo '============================================'

                sh '''
                    . venv/bin/activate

                    # pip-audit checks for known security vulnerabilities
                    # in our Python dependencies
                    # Banks must check for CVEs before deploying
                    pip install pip-audit
                    pip-audit --requirement requirements.txt || true
                    # || true prevents pipeline failure if audit finds issues
                    # In production you would remove || true to enforce security
                '''
            }
        }

        // ── STAGE 6: Deploy ──
        // Run the Docker container (simulates Azure deployment)
        stage('Deploy') {
            steps {
                echo '============================================'
                echo 'STAGE 6: Deploying SmartLoan application'
                echo '============================================'

                sh '''
                    # Stop and remove existing container if running
                    # || true prevents error if container doesn't exist yet
                    docker stop smartloan-app || true
                    docker rm smartloan-app || true

                    # Run new container with the fresh image
                    # -d = detached (runs in background)
                    # -p 5000:5000 = map host port 5000 to container port 5000
                    # --name = give container a memorable name
                    # --restart=unless-stopped = auto-restart on server reboot
                    docker run -d \
                        -p 5000:5000 \
                        --name smartloan-app \
                        --restart=unless-stopped \
                        -e FLASK_ENV=production \
                        -e SECRET_KEY=${SECRET_KEY} \
                        -e JWT_SECRET_KEY=${JWT_SECRET_KEY} \
                        ${DOCKER_IMAGE}

                    # Wait for app to start
                    echo "Waiting for application to start..."
                    sleep 15

                    # Verify deployment by calling health check endpoint
                    # curl returns exit code 0 if HTTP 200, non-zero otherwise
                    curl -f http://localhost:5000/api/health || exit 1

                    echo "Deployment successful!"
                    echo "SmartLoan is running at http://localhost:5000"
                '''
            }
        }
    }

    // ── Post Pipeline Actions ──
    // These run after ALL stages complete (pass or fail)
    post {

        success {
            echo '============================================'
            echo 'PIPELINE SUCCESS!'
            echo "Build #${BUILD_NUMBER} deployed successfully"
            echo 'SmartLoan Banking Pipeline is live'
            echo '============================================'
        }

        failure {
            echo '============================================'
            echo 'PIPELINE FAILED!'
            echo "Build #${BUILD_NUMBER} was NOT deployed"
            echo 'Check the logs above for details'
            echo '============================================'
        }

        always {
            echo "Pipeline completed. Build #${BUILD_NUMBER}"

            // Clean up virtual environment to save disk space
            sh 'rm -rf venv || true'
        }
    }
}