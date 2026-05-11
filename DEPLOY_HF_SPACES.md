# Hugging Face Spaces Deployment Guide

This guide explains how to deploy the LLM Energy Tests Dashboard to Hugging Face Spaces with automatic GitHub integration.

## Quick Start

### 1. Run the Deployment Script

```bash
./scripts/deploy_hf_spaces.sh
```

This script will:
- ✅ Verify your Git configuration
- ✅ Commit any uncommitted changes
- ✅ Push to GitHub
- ✅ Create necessary files for HF Spaces (`app.py`)
- ✅ Update `.gitignore`
- ✅ Provide setup instructions

### 2. Create a Hugging Face Space

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Fill in the form:
   - **Space name**: `llm-energy-tests-dashboard`
   - **License**: Select appropriate license (e.g., MIT, Apache 2.0)
   - **Space SDK**: Select **Streamlit**
   - **Visibility**: Public (for sharing) or Private
3. Click **Create Space**

### 3. Connect GitHub Auto-Deploy

1. In your Space, go to **Settings** (⚙️ icon)
2. Click on **Repository settings**
3. Enable **GitHub integration**
4. Authorize Hugging Face with GitHub
5. Select your repository: `your-username/llm-energy-tests`
6. Set auto-deploy branch: `main`
7. Save settings

### 4. Verify Deployment

Once connected:
- Your Space will automatically build and deploy when you push to the `main` branch
- You'll see a build log in the Space's **Logs** tab
- Once successful, your dashboard will be live at:
  ```
  https://huggingface.co/spaces/your-hf-username/llm-energy-tests-dashboard
  ```

## File Structure

```
llm-energy-tests/
├── app.py                    # HF Spaces entry point (automatically created)
├── src/
│   ├── build_dashboard.py   # Main Streamlit application
│   └── requirements.txt      # Python dependencies
├── logs/
│   └── [experiment folders]  # Data files
└── scripts/
    └── deploy_hf_spaces.sh   # Deployment automation script
```

## Configuration Files

### `app.py` (Entry Point)
- Automatically installs dependencies from `src/requirements.txt`
- Runs the Streamlit dashboard from `src/build_dashboard.py`
- Created by the deployment script

### `src/requirements.txt`
- Lists all Python dependencies:
  - `streamlit`: Dashboard framework
  - `pandas`: Data processing
  - `plotly`: Interactive visualizations

## Environment Secrets (Optional)

If your dashboard needs API keys or secrets:

1. Go to Space **Settings** → **Secrets**
2. Add your secrets (e.g., `API_KEY=your_value`)
3. Access in your code via `os.environ.get('API_KEY')`

Example in `build_dashboard.py`:
```python
import os
api_key = os.environ.get('HF_API_KEY')
```

## Troubleshooting

### Build fails: "ModuleNotFoundError"
- Ensure all dependencies are in `src/requirements.txt`
- Check the Space's build logs for details

### Dashboard loads but no data
- Verify `logs/` folder path is accessible
- Check file permissions: `logs/` should be included in your Git repository
- Consider using a data URL if logs are too large (alternative: symlink or use external storage)

### Auto-deploy not triggering
- Verify GitHub integration is enabled in Space settings
- Check that you're pushing to the correct branch (`main` by default)
- Review the Space's **Logs** tab for build errors

### Port/Connection Issues
- HF Spaces automatically manages ports
- Streamlit runs on port 8501 by default (handled by Spaces)
- No configuration needed

## Managing Large Datasets

If your `logs/` folder is too large for Git:

### Option 1: Use Git LFS (Recommended)
```bash
git lfs install
git lfs track "logs/**/*.csv"
git add .gitattributes
git commit -m "Setup Git LFS for large CSV files"
git push
```

### Option 2: Use HF Datasets
```bash
# Create a dataset on HF Hub instead of storing in Git
# Reference it in your code:
from datasets import load_dataset
dataset = load_dataset("your-username/llm-energy-logs")
```

### Option 3: Skip Large Files
Add to `.gitignore`:
```
logs/**/*.csv
```
Note: Your Space won't have data without one of the above solutions.

## Advanced: Custom Secrets in GitHub Actions

For CI/CD triggered deployments:

1. Add secrets to your GitHub repository
2. Create `.github/workflows/deploy.yml`:
```yaml
name: Deploy to HF Spaces
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Verify build
        run: python -m pip install -q -r src/requirements.txt
      - name: Test dashboard loads
        run: python -c "import streamlit; print('✓ Streamlit OK')"
```

## Support

- **Hugging Face Spaces Docs**: https://huggingface.co/docs/hub/spaces
- **Streamlit Docs**: https://docs.streamlit.io/
- **Community**: https://discuss.huggingface.co/c/spaces/

---

**Deployed Dashboard**: Will be available at `https://huggingface.co/spaces/<your-username>/llm-energy-tests-dashboard`
