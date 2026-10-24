#!/usr/bin/env bash
set -euo pipefail
# Fail quickly on UI type errors before the longer provider/database checks.
npm run typecheck
python3 -m venv /tmp/sentinel-verification
/tmp/sentinel-verification/bin/pip install -q -r ../backend/requirements.txt PyYAML jsonschema pip-audit pgserver==0.1.4
/tmp/sentinel-verification/bin/python -m compileall -q ../backend
/tmp/sentinel-verification/bin/python ../scripts/run_backend_checks.py
/tmp/sentinel-verification/bin/python ../scripts/probe_providers.py
/tmp/sentinel-verification/bin/python ../scripts/probe_trader_data.py
/tmp/sentinel-verification/bin/python ../scripts/probe_leaderboard_contract.py
/tmp/sentinel-verification/bin/python ../scripts/probe_trader_directory.py
/tmp/sentinel-verification/bin/python ../scripts/probe_catalogue.py
/tmp/sentinel-verification/bin/python ../scripts/validate_blueprint.py
/tmp/sentinel-verification/bin/pip-audit -r ../backend/requirements.txt
npm audit --audit-level=high
# Keep browser requests same-origin through Pages Functions, regardless of Pages env.
export NEXT_PUBLIC_API_BASE=''
npm run build
npx playwright install chromium
npm run test:e2e
/tmp/sentinel-verification/bin/python ../scripts/check_deployed_auth.py


/tmp/sentinel-verification/bin/python ../scripts/probe_price_history.py
