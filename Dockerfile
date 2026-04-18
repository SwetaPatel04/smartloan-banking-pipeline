# ============================================================
# Dockerfile — SmartLoan Banking Pipeline
# ============================================================
# A Dockerfile is a recipe that tells Docker how to build
# a container for our application.
#
# Why Docker in banking?
#   - Every environment (dev, test, production) runs IDENTICAL code
#   - No more "it works on my machine" problems
#   - Azure, AWS, and all cloud providers run Docker containers
#   - Banks use Docker to deploy thousands of microservices
#
# Build command : docker build -t smartloan .
# Run command   : docker run -p 5000:5000 smartloan
# ============================================================

# ── Base Image ──
# We start FROM an official Python image (like a pre-built OS)
# python:3.11-slim is smaller than full Python — faster to download
# slim = stripped down Linux with just enough to run Python
FROM python:3.11-slim

# ── Metadata Labels ──
# Labels are like sticky notes on the container — for documentation
LABEL maintainer="Sweta Patel <sweta48etava@gmail.com>"
LABEL project="SmartLoan Banking Pipeline"
LABEL version="1.0"

# ── Set Working Directory ──
# All subsequent commands run inside /app inside the container
# Like doing 'cd /app' but permanently
WORKDIR /app

# ── Environment Variables ──
# These configure Python and Flask behaviour inside the container
ENV PYTHONDONTWRITEBYTECODE=1
# PYTHONDONTWRITEBYTECODE=1 stops Python creating .pyc files
# .pyc files waste space in containers

ENV PYTHONUNBUFFERED=1
# PYTHONUNBUFFERED=1 makes Python print logs immediately
# Without this, logs appear delayed — bad for debugging in production

ENV FLASK_ENV=production
# Tell Flask we are in production mode (no debug, more secure)

ENV PORT=5000
# Default port — Azure overrides this with its own value

# ── Install System Dependencies ──
# Some Python packages need system libraries to compile
# We install them here before installing Python packages
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*
# gcc = C compiler needed by some packages (scikit-learn)
# rm -rf /var/lib/apt/lists/* deletes apt cache to reduce image size

# ── Copy Requirements First ──
# We copy requirements.txt BEFORE copying the rest of the code
# Why? Docker caches each step. If requirements haven't changed,
# Docker skips reinstalling packages (much faster builds)
COPY requirements.txt .

# ── Install Python Dependencies ──
# --no-cache-dir stops pip storing download cache (saves space)
# --upgrade pip ensures we have the latest pip version
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Copy Application Code ──
# Now copy everything else into the container
# The .dockerignore file controls what gets excluded
COPY . .

# ── Create Instance Directory ──
# Flask needs this folder for the SQLite database
RUN mkdir -p instance

# ── Expose Port ──
# Tell Docker this container listens on port 5000
# This is documentation only — actual port mapping happens at runtime
EXPOSE 5000

# ── Health Check ──
# Docker periodically checks if the container is healthy
# If /api/health returns non-200, Docker marks container as unhealthy
# Banking systems use health checks for zero-downtime deployments
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" \
    || exit 1

# ── Start Command ──
# This runs when the container starts
# gunicorn is a production-grade web server (Flask's built-in server is for dev only)
# --workers 2 = 2 parallel processes to handle requests
# --bind 0.0.0.0:5000 = listen on all interfaces, port 5000
# run:app = in run.py, use the 'app' variable
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "--timeout", "120", "run:app"]