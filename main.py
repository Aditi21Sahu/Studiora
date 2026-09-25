"""
Studiora Root - Main Entry Point Re-export
Allows Uvicorn to load the ASGI application directly from the repository root:
- uvicorn main:app
"""
import sys
import os

# Ensure the backend directory is in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(root_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
