#!/usr/bin/env bash
set -euo pipefail
python3 -m venv /tmp/sentinel-verification
/tmp/sentinel-verification/bin/pip install -q -r ../backend/requirements.txt PyYAML jsonschema pip-audit
/tmp/sentinel-verification/bin/python -m compileall -q ../backend
PYTHONPATH=../backend /tmp/sentinel-verification/bin/python -m unittest discover -s ../backend/tests -v
/tmp/sentinel-verification/bin/python ../scripts/probe_providers.py
/tmp/sentinel-verification/bin/python ../scripts/probe_trader_data.py
/tmp/sentinel-verification/bin/python ../scripts/validate_blueprint.py
/tmp/sentinel-verification/bin/pip-audit -r ../backend/requirements.txt
npm audit --audit-level=high
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
/tmp/sentinel-verification/bin/python ../scripts/check_deployed_auth.py
