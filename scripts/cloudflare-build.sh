#!/usr/bin/env bash
set -euo pipefail
python3 -m venv /tmp/sentinel-verification
/tmp/sentinel-verification/bin/pip install -q -r ../backend/requirements.txt
PYTHONPATH=../backend /tmp/sentinel-verification/bin/python -m unittest discover -s ../backend/tests -v
npm audit --omit=dev --audit-level=high
npm run typecheck
npm run build
