"""
Hugging Face Spaces entry point for the LLM Energy Tests Dashboard.
This file runs the Streamlit dashboard from src/build_dashboard.py.
"""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

# Import the dashboard module. Streamlit executes the app on import.
import build_dashboard  # noqa: F401
