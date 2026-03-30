#!/bin/bash
# Quick-start script for Bitrix24 Analytics app
set -e

# Create .env from example if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example — edit it with your Bitrix24 credentials."
fi

# Create venv if not exists
if [ ! -d venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

echo ""
echo "=== Bitrix24 Analytics ==="
echo ""
echo "Starting on http://localhost:5000"
echo ""
echo "To use as Bitrix24 Local App:"
echo "  1. Expose via ngrok:  ngrok http 5000"
echo "  2. In Bitrix24 -> Developer resources -> Other -> Local app"
echo "  3. Set Handler URL:   https://<ngrok-url>/install"
echo "  4. Set Permissions:   crm, user"
echo ""

python wsgi.py
