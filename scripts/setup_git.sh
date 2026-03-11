#!/bin/bash

# Configuration - Change these to your details
GIT_USER="magnuscruz"  # Your GitHub username
GIT_EMAIL="magnuscruz@gmail.com"  # Your GitHub email
TOKEN_EXPIRY=86400  # Cache credentials for 24 hours (perfect for aging tests)

echo "--- Configuring Git for LLM Benchmarking ---"

# 1. Set Global Identity
git config --global user.name "$GIT_USER"
git config --global user.email "$GIT_EMAIL"

# 2. Configure Credential Helper
# This stores your Personal Access Token (PAT) in memory so the script doesn't stop
git config --global credential.helper "cache --timeout=$TOKEN_EXPIRY"

# 3. Fix line endings (Prevents diff issues between Linux/Windows logs)
git config --global core.autocrlf input

# 4. Set default branch to main
git config --global init.defaultBranch main

echo "--- Verification ---"
git config --list

echo ""
echo "IMPORTANT: The first time you run 'git push', it will ask for your Username and Password."
echo "For GitHub, use your 'Personal Access Token' (PAT) as the password."
echo "After the first login, it will stay logged in for 24 hours."
