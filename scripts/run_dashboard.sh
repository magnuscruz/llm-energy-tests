#!/bin/bash
# This script runs the Streamlit dashboard for visualizing LLM energy and aging data.
# Make sure you have Streamlit installed in your Python environment before running this script.
# Usage:
#   ./run_dashboard.sh [optional_date_filter]
# Example:
#   ./run_dashboard.sh 20240601
# Check if a date filter argument is provided
if [ "$1" ]; then
    echo "Running dashboard with date filter: $1"
    streamlit run ./src/build_dashboard.py --server.port 8501 -- --date_filter "$1"
else
    echo "Running dashboard without date filter"
    streamlit run ./src/build_dashboard.py  --server.port 8501
fi