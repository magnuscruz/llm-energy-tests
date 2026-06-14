#!/bin/bash

# ==============================================================================
# Deploy LLM Energy Tests Dashboard to Hugging Face Spaces via GitHub
# ==============================================================================

set -e

echo "🚀 LLM Energy Tests - Hugging Face Spaces Deployment Script"
echo "=============================================================="

# Configuration
GITHUB_REPO="magnuscruz/llm-energy-tests"
HF_SPACE_REPO="magnuscruz/llm-energy-tests"
BRANCH="main"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Step 1: Check GitHub configuration
echo ""
echo "Step 1: Verifying GitHub configuration..."
if [ -z "$(git config user.name)" ]; then
    print_error "Git user name not configured"
    echo "Run: git config --global user.name 'Your Name'"
    exit 1
fi
if [ -z "$(git config user.email)" ]; then
    print_error "Git user email not configured"
    echo "Run: git config --global user.email 'your.email@example.com'"
    exit 1
fi
print_status "Git configured as $(git config user.name)"

# Step 2: Check for uncommitted changes
echo ""
echo "Step 2: Checking for uncommitted changes..."
if ! git diff-index --quiet HEAD --; then
    print_warning "Uncommitted changes detected"
    git status
    read -p "Commit these changes? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git add .
        read -p "Enter commit message: " commit_msg
        git commit -m "$commit_msg"
        print_status "Changes committed"
    else
        print_error "Aborted: Please commit or stash changes before deploying"
        exit 1
    fi
else
    print_status "Working directory clean"
fi

# Step 3: Push to GitHub
echo ""
echo "Step 3: Pushing to GitHub ($BRANCH branch)..."
if git push origin $BRANCH; then
    print_status "Successfully pushed to GitHub"
else
    print_error "Failed to push to GitHub"
    exit 1
fi

# Step 4: Hugging Face Spaces Configuration
echo ""
echo "Step 4: Hugging Face Spaces Configuration"
echo "=========================================="
echo ""
echo "To deploy to Hugging Face Spaces, follow these steps:"
echo ""
echo "1. Create a new Space on Hugging Face:"
echo "   - Go to https://huggingface.co/new-space"
echo "   - Name: llm-energy-tests-dashboard"
echo "   - License: Choose appropriate license"
echo "   - Space SDK: Streamlit"
echo "   - Visibility: Public"
echo ""
echo "2. Connect to GitHub:"
echo "   - In the Space settings, go to 'Repository settings'"
echo "   - Enable GitHub integration"
echo "   - Connect your GitHub repository: $GITHUB_REPO"
echo "   - Auto-deploy on push to: $BRANCH"
echo ""
echo "3. Create app.py in HF Space with:"
cat > app_template.py << 'EOF'
import subprocess
import sys

# Install requirements if needed
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", "src/requirements.txt"])

# Run the dashboard
import streamlit.cli
sys.argv = ["streamlit", "run", "src/build_dashboard.py", "--logger.level=info"]
streamlit.cli.main()
EOF
echo "   (Copy content from the generated app_template.py)"
echo ""
echo "4. Update Secrets (if needed):"
echo "   - Add any API keys or secrets to Space Settings > Secrets"
echo ""

# Step 5: Create app.py template
echo ""
echo "Step 5: Creating app.py template for HF Spaces..."
if [ ! -f "app.py" ]; then
    cat > app.py << 'EOF'
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
EOF
    print_status "Created app.py"
else
    print_warning "app.py already exists"
fi

# Step 6: Create .gitignore entries for HF Spaces
echo ""
echo "Step 6: Verifying .gitignore..."
if [ -f ".gitignore" ]; then
    if ! grep -q "__pycache__" .gitignore; then
        echo "__pycache__/" >> .gitignore
    fi
    if ! grep -q ".streamlit/" .gitignore; then
        echo ".streamlit/" >> .gitignore
    fi
    print_status "Updated .gitignore"
else
    cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
*$py.class
.streamlit/
.env
.venv
env/
venv/
*.egg-info/
dist/
build/
EOF
    print_status "Created .gitignore"
fi

# Step 7: Summary
echo ""
echo "=============================================================="
print_status "Deployment preparation complete!"
echo ""
echo "Next steps:"
echo "  1. Visit: https://huggingface.co/new-space"
echo "  2. Set up your Space with Streamlit SDK"
echo "  3. Enable GitHub auto-deploy from: $GITHUB_REPO"
echo "  4. Your dashboard will auto-deploy on future pushes to $BRANCH"
echo ""
echo "Dashboard URL will be: https://huggingface.co/spaces/magnuscruz/llm-energy-tests"
echo ""
echo "For more info: https://huggingface.co/docs/hub/spaces"
