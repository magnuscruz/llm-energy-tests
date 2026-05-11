"""
Hugging Face Spaces entry point for LLM Energy Tests Dashboard
Automatically loads the Streamlit dashboard with required dependencies
"""
import subprocess
import sys
import os

# Ensure we're in the correct directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Install requirements
print("📦 Installing dependencies...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", "src/requirements.txt"])

# Run Streamlit app
print("🚀 Starting dashboard...")
import streamlit.cli
sys.argv = ["streamlit", "run", "src/build_dashboard.py", "--logger.level=info"]
streamlit.cli.main()
