from pathlib import Path
import httpx
import yaml
from jsonschema.validators import validator_for
root=Path(__file__).resolve().parents[1]
response=httpx.get('https://render.com/schema/render.yaml.json',timeout=30)
response.raise_for_status()
schema=response.json()
kind=validator_for(schema)
kind.check_schema(schema)
errors=list(kind(schema).iter_errors(yaml.safe_load((root/'render.yaml').read_text())))
for error in errors:
    print('Blueprint error at '+'.'.join(map(str,error.path))+': '+error.message)
if errors:raise SystemExit(1)
print('Render Blueprint schema validation passed')
