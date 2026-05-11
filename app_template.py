import subprocess
import sys

# Install requirements if needed
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", "src/requirements.txt"])

# Run the dashboard
import streamlit.cli
sys.argv = ["streamlit", "run", "src/build_dashboard.py", "--logger.level=info"]
streamlit.cli.main()
