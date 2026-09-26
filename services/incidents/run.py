"""
Run script for the TrackFlow Incidents Analysis Service.
Start with: uvicorn services.incidents.run:app --port 8002

This exposes REST endpoints for TRF incident analysis results
at http://localhost:8002/incidents/analyses
"""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so relative imports work
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from services.incidents.api import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.incidents.run:app", host="0.0.0.0", port=8002, reload=True)