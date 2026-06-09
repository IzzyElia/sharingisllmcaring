#!/bin/bash
set -e  # exit on any error

echo "Updating..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

git clean -fd
git pull

source venv/bin/activate
pip install -r requirements.txt

echo "Done."
