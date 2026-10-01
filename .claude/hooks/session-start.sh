#!/bin/bash
# Install Python dependencies for the hockey value-bet tools (cloud sessions only).
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"
python3 -m pip install -q -r requirements.txt 2>&1 | grep -v "Running pip as the 'root' user" || true
python3 -c "import numpy, scipy" 
echo "export PYTHONPATH=\"$PWD\"" >> "${CLAUDE_ENV_FILE:-/dev/null}"
