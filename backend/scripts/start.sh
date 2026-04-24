#!/bin/bash
# Start the BMCC backend server

echo "Activating virtual environment..."
source venv/Scripts/activate

echo "Starting server on http://127.0.0.1:8000"
echo "Press Ctrl+C to stop"
echo ""

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
