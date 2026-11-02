pipeline {
    agent any

    environment {
        PYTHON_ENV = 'python3'
        VENV_DIR = '.venv'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Environment Setup & Install') {
            steps {
                sh '''
                    python3 -m venv ${VENV_DIR}
                    . ${VENV_DIR}/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                    pip install -r requirements-dev.txt
                '''
            }
        }

        stage('Linting & Static Analysis') {
            steps {
                sh '''
                    . ${VENV_DIR}/bin/activate
                    flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
                '''
            }
        }

        stage('Automated Regression & Unit Tests') {
            steps {
                sh '''
                    . ${VENV_DIR}/bin/activate
                    python run_tests.py
                    pytest --cov=trade_store --cov-report=xml --cov-report=term-missing tests/
                '''
            }
            post {
                always {
                    junit testResults: '**/test-*.xml', allowEmptyResults: true
                }
            }
        }

        stage('OSS Vulnerability Scan') {
            steps {
                sh '''
                    . ${VENV_DIR}/bin/activate
                    echo "Executing pip-audit OSS vulnerability scanning..."
                    # Fails the build if any Critical or High vulnerability is found
                    pip-audit --desc on --strict

                    echo "Executing Bandit static application security scan..."
                    bandit -r trade_store/ -ll -ii
                '''
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    docker build -t trade-store-api:${BUILD_NUMBER} .
                    docker tag trade-store-api:${BUILD_NUMBER} trade-store-api:latest
                '''
            }
        }
    }

    post {
        success {
            echo "CI/CD Pipeline build and security verification succeeded!"
        }
        failure {
            echo "CI/CD Pipeline failed! Check logs for test failures or critical security vulnerabilities."
        }
        cleanup {
            sh "rm -rf ${VENV_DIR}"
        }
    }
}
